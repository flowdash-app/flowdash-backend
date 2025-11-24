import json
import hashlib
import logging
from typing import Optional, Dict, Any
from app.core.redis_cache import RedisCache

logger = logging.getLogger(__name__)


# Global cache instance
_cache_instance: Optional[RedisCache] = None


def get_cache() -> RedisCache:
    """Get global Redis cache instance"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = RedisCache()
    return _cache_instance


def _generate_cache_key(instance_id: str, params: Dict[str, Any]) -> str:
    """Generate cache key from instance_id and query parameters."""
    # Sort params for consistent hashing
    sorted_params = sorted(params.items())
    params_str = json.dumps(sorted_params, sort_keys=True)
    params_hash = hashlib.md5(params_str.encode()).hexdigest()[:8]
    return f"n8n_executions:{instance_id}:{params_hash}"


def get_cached_executions(instance_id: str, params: Dict[str, Any]) -> Optional[Dict]:
    """Get cached n8n executions response."""
    cache = get_cache()
    cache_key = _generate_cache_key(instance_id, params)
    return cache.get(cache_key)


def set_cached_executions(
    instance_id: str,
    params: Dict[str, Any],
    response: Dict,
    ttl_minutes: int = 5
):
    """Cache n8n executions response."""
    cache = get_cache()
    cache_key = _generate_cache_key(instance_id, params)
    cache.set(cache_key, response, ttl_minutes)


def delete_cached_executions(instance_id: str, params: Dict[str, Any]):
    """Delete cached n8n executions response."""
    cache = get_cache()
    cache_key = _generate_cache_key(instance_id, params)
    cache.delete(cache_key)

