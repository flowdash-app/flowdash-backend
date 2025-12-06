import json
import logging
import uuid
from typing import Optional, Dict, Any
from datetime import datetime
import redis
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError
from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisCache:
    """Redis-backed cache for rate limiting and n8n API responses"""
    
    def __init__(self):
        """Initialize Redis cache (lazy connection)"""
        self._client: Optional[redis.Redis] = None
        self._connection_params: Optional[Dict[str, Any]] = None
        self._connected = False
        self._connecting = False  # Flag to prevent recursive connection attempts
    
    def _get_connection_params(self) -> Dict[str, Any]:
        """Get Redis connection parameters"""
        if self._connection_params is None:
            try:
                # Parse Redis URL if provided, otherwise use individual settings
                redis_url = getattr(settings, 'redis_url', None)
                redis_password = getattr(settings, 'redis_password', None)
                
                if redis_url:
                    # Use redis.from_url() to properly parse the URL
                    # This handles all Redis URL formats correctly (redis://, rediss://, etc.)
                    try:
                        # Create a temporary client to extract connection info
                        # We'll use decode_responses=False to match our actual client config
                        temp_client = redis.from_url(
                            redis_url,
                            decode_responses=False,
                            socket_connect_timeout=1,
                            socket_timeout=1,
                        )
                        
                        # Extract connection parameters from the client's connection pool
                        pool = temp_client.connection_pool
                        host = pool.connection_kwargs.get('host', 'localhost')
                        port = pool.connection_kwargs.get('port', 6379)
                        db = pool.connection_kwargs.get('db', getattr(settings, 'redis_db', 0))
                        url_password = pool.connection_kwargs.get('password')
                        
                        # Prefer settings.redis_password if URL password is empty/missing
                        # Normalize empty string to None
                        if url_password:
                            password = url_password
                        elif redis_password:
                            password = redis_password
                        else:
                            password = None
                        
                        # Clean up temp client
                        temp_client.close()
                        
                        self._connection_params = {
                            'host': host,
                            'port': port,
                            'db': db,
                            'password': password,
                            'redis_url': redis_url,  # Store URL for use in _connect()
                        }
                        
                        # Log connection info (without password)
                        logger.debug(f"RedisCache: Connection params - host={host}, port={port}, db={db}, password={'***' if password else 'None'}")
                    except (ValueError, AttributeError, TypeError) as e:
                        logger.warning(f"RedisCache: Failed to parse Redis URL with redis.from_url(), falling back to individual settings: {e}")
                        # Fallback to individual settings
                        password = redis_password if redis_password else None
                        db = getattr(settings, 'redis_db', 0)
                        host = 'localhost'
                        port = 6379
                        
                        self._connection_params = {
                            'host': host,
                            'port': port,
                            'db': db,
                            'password': password,
                        }
                else:
                    # Fallback to individual settings
                    password = redis_password if redis_password else None
                    db = getattr(settings, 'redis_db', 0)
                    host = 'localhost'
                    port = 6379
                    
                    self._connection_params = {
                        'host': host,
                        'port': port,
                        'db': db,
                        'password': password,
                    }
                    logger.debug(f"RedisCache: Using individual settings - host={host}, port={port}, db={db}, password={'***' if password else 'None'}")
            except RecursionError:
                # If we get recursion here, use safe defaults
                logger.error("RedisCache: Recursion error while getting connection params, using defaults")
                self._connection_params = {
                    'host': 'localhost',
                    'port': 6379,
                    'db': 0,
                    'password': None,
                }
        
        return self._connection_params
    
    def _ensure_connected(self):
        """Ensure Redis connection is established (lazy connection)"""
        # Prevent recursive connection attempts
        if self._connecting:
            raise RuntimeError("Redis connection already in progress")
        
        if self._connected and self._client is not None:
            # Quick check if connection is still alive
            try:
                self._client.ping()
                return
            except (RedisError, AttributeError):
                # Connection lost, reconnect
                self._connected = False
                self._client = None
        
        if not self._connected:
            self._connect()
    
    def _connect(self):
        """Connect to Redis server"""
        if self._connected:
            return
        
        # Prevent recursive connection attempts
        if self._connecting:
            logger.warning("RedisCache: Connection already in progress, skipping")
            return
        
        self._connecting = True
        try:
            params = self._get_connection_params()
            redis_url = getattr(settings, 'redis_url', None)
            redis_password = getattr(settings, 'redis_password', None)
            
            # Create Redis client with minimal configuration to avoid recursion
            try:
                if redis_url and 'redis_url' in params:
                    # Use redis.from_url() for proper URL parsing
                    # Override password if settings.redis_password is set (takes precedence)
                    client_kwargs = {
                        'decode_responses': False,
                        'socket_connect_timeout': 2,
                        'socket_timeout': 2,
                        'retry_on_timeout': False,
                        'health_check_interval': 0,
                    }
                    # Override password from settings if provided (takes precedence over URL password)
                    if redis_password:
                        client_kwargs['password'] = redis_password
                    
                    self._client = redis.from_url(redis_url, **client_kwargs)
                else:
                    # Use individual connection parameters
                    self._client = redis.Redis(
                        host=params['host'],
                        port=params['port'],
                        db=params['db'],
                        password=params['password'],
                        decode_responses=False,
                        socket_connect_timeout=2,  # Shorter timeout
                        socket_timeout=2,
                        retry_on_timeout=False,  # Disable retry to avoid recursion
                        health_check_interval=0,  # Disable health check
                    )
            except RecursionError as e:
                logger.error(f"RedisCache: Recursion error while creating Redis client - {e}")
                self._connected = False
                self._client = None
                self._connecting = False
                return  # Don't re-raise to prevent further recursion
            
            # Test connection with timeout protection
            try:
                self._client.ping()
                self._connected = True
                logger.info(f"RedisCache: Connected to Redis at {params['host']}:{params['port']}/{params['db']}")
            except RecursionError as e:
                logger.error(f"RedisCache: Recursion error during ping - {e}")
                self._connected = False
                self._client = None
                # Don't re-raise
            except (RedisError, AttributeError) as e:
                error_msg = str(e)
                # Check if it's an authentication error (may be in different formats)
                if 'authentication' in error_msg.lower() or 'password' in error_msg.lower() or 'auth' in error_msg.lower() or 'requirepass' in error_msg.lower():
                    logger.error(f"RedisCache: Authentication failed - {error_msg}. Ensure REDIS_PASSWORD env var is set correctly or password is included in REDIS_URL.")
                else:
                    logger.warning(f"RedisCache: Connection test failed - {error_msg}")
                self._connected = False
                self._client = None
                # Don't raise - allow graceful degradation
                
        except RecursionError as e:
            logger.error(f"RedisCache: Recursion error during connection setup - {e}. This may indicate a configuration issue.")
            self._connected = False
            self._client = None
            # Don't re-raise RecursionError to prevent further recursion
        except RedisConnectionError as e:
            logger.error(f"RedisCache: Failed to connect to Redis - {e}")
            self._connected = False
            self._client = None
            # Don't raise - allow graceful degradation
        except RedisError as e:
            logger.error(f"RedisCache: Redis error during connection - {e}")
            self._connected = False
            self._client = None
            # Don't raise - allow graceful degradation
        except Exception as e:
            logger.error(f"RedisCache: Unexpected error during connection - {e}")
            self._connected = False
            self._client = None
            # Don't raise - allow graceful degradation
        finally:
            self._connecting = False
    
    def get(self, key: str) -> Optional[Dict]:
        """Get cached value if not expired"""
        try:
            self._ensure_connected()
        except (RedisError, RuntimeError, RecursionError):
            logger.warning(f"RedisCache: Cannot get key {key} - Redis not available")
            return None
        
        # Check if client is available after connection attempt
        if self._client is None:
            logger.warning(f"RedisCache: Cannot get key {key} - Redis client not available")
            return None
        
        try:
            data = self._client.get(key)
            if data is None:
                logger.debug(f"Cache miss: {key}")
                return None
            
            # Deserialize JSON
            try:
                decoded = json.loads(data.decode('utf-8'))
                logger.debug(f"Cache hit: {key}")
                return decoded
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                logger.warning(f"RedisCache: Failed to decode value for key {key}: {e}")
                # Delete corrupted entry
                self._client.delete(key)
                return None
        except RedisError as e:
            logger.error(f"RedisCache: Error getting key {key}: {e}")
            # Reset connection state on error
            self._connected = False
            return None
    
    def get_int(self, key: str) -> Optional[int]:
        """Get cached integer value if not expired (for rate limiting)"""
        try:
            self._ensure_connected()
        except (RedisError, RuntimeError, RecursionError):
            logger.warning(f"RedisCache: Cannot get integer key {key} - Redis not available")
            return None
        
        # Check if client is available after connection attempt
        if self._client is None:
            logger.warning(f"RedisCache: Cannot get integer key {key} - Redis client not available")
            return None
        
        try:
            data = self._client.get(key)
            if data is None:
                return None
            
            # Try to decode as integer directly
            try:
                return int(data.decode('utf-8'))
            except (ValueError, UnicodeDecodeError):
                # If not a simple integer, try JSON decode
                try:
                    decoded = json.loads(data.decode('utf-8'))
                    if isinstance(decoded, int):
                        return decoded
                    if isinstance(decoded, dict) and 'count' in decoded:
                        return decoded['count']
                    return None
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    logger.warning(f"RedisCache: Failed to decode integer for key {key}: {e}")
                    self._client.delete(key)
                    return None
        except RedisError as e:
            logger.error(f"RedisCache: Error getting integer key {key}: {e}")
            # Reset connection state on error
            self._connected = False
            return None
    
    def set(self, key: str, value: Dict | int, ttl_minutes: int):
        """Set cache value with TTL in minutes (supports both dict and int for rate limiting)"""
        try:
            self._ensure_connected()
        except (RedisError, RuntimeError, RecursionError) as e:
            logger.warning(f"RedisCache: Cannot set key {key} - Redis not available: {e}")
            return  # Fail silently if Redis is unavailable
        
        # Check if client is available after connection attempt
        if self._client is None:
            logger.warning(f"RedisCache: Cannot set key {key} - Redis client not available")
            return  # Fail silently if Redis is unavailable
        
        try:
            # Convert TTL from minutes to seconds
            ttl_seconds = ttl_minutes * 60
            
            # Serialize value
            if isinstance(value, int):
                # Store integers as strings for efficiency
                serialized = str(value).encode('utf-8')
            else:
                # Store dicts as JSON
                serialized = json.dumps(value).encode('utf-8')
            
            # Set with TTL
            self._client.setex(key, ttl_seconds, serialized)
            logger.debug(f"Cache set: {key}, TTL: {ttl_minutes} minutes")
        except RedisError as e:
            logger.error(f"RedisCache: Error setting key {key}: {e}")
            # Reset connection state on error
            self._connected = False
    
    def delete(self, key: str):
        """Delete cache entry"""
        try:
            self._ensure_connected()
        except (RedisError, RuntimeError, RecursionError):
            logger.warning(f"RedisCache: Cannot delete key {key} - Redis not available")
            return  # Fail silently if Redis is unavailable
        
        # Check if client is available after connection attempt
        if self._client is None:
            logger.warning(f"RedisCache: Cannot delete key {key} - Redis client not available")
            return  # Fail silently if Redis is unavailable
        
        try:
            self._client.delete(key)
            logger.debug(f"Cache deleted: {key}")
        except RedisError as e:
            logger.error(f"RedisCache: Error deleting key {key}: {e}")
            # Reset connection state on error
            self._connected = False
    
    def clear(self):
        """Clear all cache entries (flush current database)"""
        try:
            self._ensure_connected()
        except (RedisError, RuntimeError, RecursionError):
            logger.warning("RedisCache: Cannot clear cache - Redis not available")
            return  # Fail silently if Redis is unavailable
        
        # Check if client is available after connection attempt
        if self._client is None:
            logger.warning("RedisCache: Cannot clear cache - Redis client not available")
            return  # Fail silently if Redis is unavailable
        
        try:
            self._client.flushdb()
            logger.debug("Cache cleared (flushed database)")
        except RedisError as e:
            logger.error(f"RedisCache: Error clearing cache: {e}")
            # Reset connection state on error
            self._connected = False
    
    def cleanup_expired(self):
        """Remove all expired entries (Redis handles TTL automatically, but we can scan for keys)"""
        # Redis automatically removes expired keys, so this is mostly a no-op
        # But we can log stats if needed
        try:
            self._ensure_connected()
            # Check if client is available after connection attempt
            if self._client is None:
                logger.warning("RedisCache: Cannot cleanup - Redis client not available")
                return
            # Get database info
            info = self._client.info('keyspace')
            logger.debug(f"RedisCache: Database info - {info}")
        except (RedisError, RuntimeError, RecursionError) as e:
            logger.warning(f"RedisCache: Error during cleanup check: {e}")
    
    def ping(self) -> bool:
        """Check if Redis connection is alive"""
        try:
            self._ensure_connected()
            # Check if client is available after connection attempt
            if self._client is None:
                return False
            self._client.ping()
            return True
        except (RedisError, RuntimeError, RecursionError):
            return False
    
    def acquire_lock(self, lock_key: str, timeout_seconds: int = 10, block_seconds: int = 5) -> bool:
        """
        Acquire a distributed lock using Redis.
        
        Args:
            lock_key: Unique key for the lock
            timeout_seconds: How long the lock will be held (auto-release)
            block_seconds: How long to wait trying to acquire the lock
        
        Returns:
            True if lock acquired, False otherwise
        """
        try:
            self._ensure_connected()
            if self._client is None:
                logger.warning(f"RedisCache: Cannot acquire lock {lock_key} - Redis not available")
                return False
            
            # Try to acquire lock with SET NX EX (atomic operation)
            # Returns True if key was set (lock acquired), False if key already exists
            end_time = datetime.utcnow().timestamp() + block_seconds
            lock_value = str(uuid.uuid4())  # Unique value to identify our lock
            
            while datetime.utcnow().timestamp() < end_time:
                # SET key value NX EX timeout - atomic operation
                acquired = self._client.set(
                    lock_key,
                    lock_value,
                    nx=True,  # Only set if key doesn't exist
                    ex=timeout_seconds  # Expire after timeout
                )
                
                if acquired:
                    logger.debug(f"RedisCache: Lock acquired - {lock_key}")
                    return True
                
                # Wait a bit before retrying
                import time
                time.sleep(0.05)  # 50ms
            
            logger.debug(f"RedisCache: Failed to acquire lock - {lock_key}")
            return False
            
        except RedisError as e:
            logger.error(f"RedisCache: Error acquiring lock {lock_key}: {e}")
            self._connected = False
            return False
    
    def release_lock(self, lock_key: str):
        """
        Release a distributed lock.
        
        Args:
            lock_key: The key of the lock to release
        """
        try:
            self._ensure_connected()
            if self._client is None:
                logger.warning(f"RedisCache: Cannot release lock {lock_key} - Redis not available")
                return
            
            self._client.delete(lock_key)
            logger.debug(f"RedisCache: Lock released - {lock_key}")
            
        except RedisError as e:
            logger.error(f"RedisCache: Error releasing lock {lock_key}: {e}")
            self._connected = False
    
    def incr(self, key: str, amount: int = 1) -> Optional[int]:
        """
        Atomically increment a counter in Redis.
        
        Args:
            key: The key to increment
            amount: Amount to increment by (default 1)
        
        Returns:
            The new value after increment, or None if Redis unavailable
        """
        try:
            self._ensure_connected()
            if self._client is None:
                logger.warning(f"RedisCache: Cannot increment key {key} - Redis not available")
                return None
            
            new_value = self._client.incrby(key, amount)
            logger.debug(f"RedisCache: Incremented {key} by {amount} to {new_value}")
            return new_value
            
        except RedisError as e:
            logger.error(f"RedisCache: Error incrementing key {key}: {e}")
            self._connected = False
            return None
    
    def expire(self, key: str, seconds: int):
        """
        Set expiration time on a key.
        
        Args:
            key: The key to set expiration on
            seconds: Number of seconds until expiration
        """
        try:
            self._ensure_connected()
            if self._client is None:
                logger.warning(f"RedisCache: Cannot set expiration on key {key} - Redis not available")
                return
            
            self._client.expire(key, seconds)
            logger.debug(f"RedisCache: Set expiration on {key} to {seconds} seconds")
            
        except RedisError as e:
            logger.error(f"RedisCache: Error setting expiration on key {key}: {e}")
            self._connected = False

