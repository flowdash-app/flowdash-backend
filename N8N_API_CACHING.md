# n8n API Response Caching Strategy

## Overview

This document outlines the backend caching strategy for n8n API responses to reduce API calls to n8n instances, improve performance, and minimize backend load. The backend caches raw API responses, allowing the mobile app to calculate any statistics it needs from the cached data.

## Purpose

- **Reduce API Calls**: Minimize expensive calls to n8n instances (each instance requires a separate API call)
- **Improve Performance**: Provide faster response times by serving cached data
- **Reduce Backend Load**: Decrease the number of concurrent requests to n8n APIs
- **Better UX**: Show cached data immediately while optionally refreshing in the background
- **Flexibility**: Let the app calculate any metrics it needs from the raw execution data

## What to Cache

### n8n API Responses

Cache the raw responses from n8n API calls, specifically:

**API Endpoint**: `{instance.url}/api/v1/executions`

**Cache Key Structure**: `n8n_executions:{instance_id}:{hash_of_params}`

**Cache Key Components**:
- `instance_id`: The n8n instance ID
- `hash_of_params`: Hash of query parameters (limit, cursor, workflowId, status)

**Example Cache Keys**:
- `n8n_executions:instance_456:a1b2c3d4` (for specific query params)
- `n8n_executions:instance_456:e5f6g7h8` (for different query params)

**Cached Data Structure** (raw n8n API response):
```json
{
  "data": [
    {
      "id": "execution_123",
      "workflowId": "workflow_456",
      "status": "success",
      "startedAt": "2025-01-15T10:30:00Z",
      "stoppedAt": "2025-01-15T10:30:05Z",
      "duration": 5000,
      "error": null
    },
    // ... more executions
  ],
  "nextCursor": "cursor_string_or_null"
}
```

**Why Cache Raw Responses?**
- App can calculate success rate, average duration, or any other metric
- Single cache serves multiple use cases (dashboard, executions list, etc.)
- More flexible than pre-calculated statistics
- Easier to invalidate (just invalidate the API response cache)

## Cache Duration (TTL)

### Execution Data Cache

- **Free Users**: 10 minutes (reduce API load for free tier)
- **Pro Users**: 3 minutes (fresher data for paying customers)
- **Enterprise Users**: **NO CACHING** (always fresh data, real-time updates)

**Rationale**: 
- Execution data changes frequently as new executions complete
- Free users get longer TTL to reduce API load
- Pro users get fresher data with shorter TTL
- Enterprise users pay for real-time data with no caching overhead

### Cache Parameters

Different cache keys for different query parameters:
- Different `limit` values → different cache keys
- Different `workflowId` filters → different cache keys
- Different `status` filters → different cache keys
- Different `cursor` values → different cache keys (pagination)

**Note**: Cursor-based pagination means each page is cached separately, which is correct behavior.

## Cache Invalidation

Cache should be invalidated in the following scenarios:

1. **Time-based**: Automatic expiration based on TTL
2. **Manual**: User explicitly requests refresh (bypass cache with `?refresh=true` query param)
3. **Event-based** (Future): When new execution completes (optional, for real-time updates)

## Implementation Approach

### Cache Backend

**Recommended**: Redis (if available) or in-memory cache (Python `functools.lru_cache` or similar)

**Redis Example**:
```python
import redis
import json
import hashlib
from datetime import timedelta
from typing import Optional, Dict, Any

redis_client = redis.Redis(host='localhost', port=6379, db=0)

def _generate_cache_key(instance_id: str, params: Dict[str, Any]) -> str:
    """Generate cache key from instance_id and query parameters."""
    # Sort params for consistent hashing
    sorted_params = sorted(params.items())
    params_str = json.dumps(sorted_params, sort_keys=True)
    params_hash = hashlib.md5(params_str.encode()).hexdigest()[:8]
    return f"n8n_executions:{instance_id}:{params_hash}"

def get_cached_executions(instance_id: str, params: Dict[str, Any]) -> Optional[Dict]:
    """Get cached n8n executions response."""
    cache_key = _generate_cache_key(instance_id, params)
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)
    return None

def set_cached_executions(
    instance_id: str, 
    params: Dict[str, Any], 
    response: Dict,
    ttl_minutes: int = 5
):
    """Cache n8n executions response."""
    cache_key = _generate_cache_key(instance_id, params)
    redis_client.setex(
        cache_key,
        timedelta(minutes=ttl_minutes),
        json.dumps(response)
    )
```

### Cache Flow in `get_executions` Method

1. **Check Cache**: Look for cached response based on instance_id and query params
2. **Cache Hit**: Return cached data immediately (no n8n API call)
3. **Cache Miss**: 
   - Make API call to n8n instance
   - Store response in cache with TTL
   - Return data to client
4. **Error Handling**: If n8n API fails, return cached data if available (stale data is better than no data)

### Updated `get_executions` Implementation

```python
async def get_executions(
    self,
    db: Session,
    instance_id: str,
    user_id: str,
    workflow_id: str | None = None,
    limit: int = 20,
    cursor: str | None = None,
    status: str | None = None,
    refresh: bool = False  # New parameter to bypass cache
) -> dict:
    # Get user plan to determine caching strategy
    user_plan = self._get_user_plan(user_id)  # 'free', 'pro', or 'enterprise'
    
    # Enterprise users: always bypass cache (real-time data)
    should_use_cache = user_plan != 'enterprise' and not refresh
    
    # Build params dict for cache key
    params = {
        "limit": limit,
        "workflowId": workflow_id,
        "cursor": cursor,
        "status": status
    }
    # Remove None values
    params = {k: v for k, v in params.items() if v is not None}
    
    # Check cache (unless enterprise plan or refresh requested)
    if should_use_cache:
        cached = get_cached_executions(instance_id, params)
        if cached:
            self.logger.info(f"get_executions: Cache hit - instance: {instance_id}, plan: {user_plan}")
            return cached
    
    # Cache miss, enterprise plan, or refresh requested - fetch from n8n
    # ... existing n8n API call code ...
    
    result = {
        "data": executions_data,
        "nextCursor": next_cursor
    }
    
    # Cache the response (skip for enterprise users)
    if user_plan != 'enterprise':
        ttl = self._get_cache_ttl(user_plan)  # Based on user plan
        set_cached_executions(instance_id, params, result, ttl)
        self.logger.info(f"get_executions: Cached response - instance: {instance_id}, plan: {user_plan}, ttl: {ttl}min")
    else:
        self.logger.info(f"get_executions: Skipped cache (enterprise plan) - instance: {instance_id}")
    
    return result

def _get_cache_ttl(self, user_plan: str) -> int:
    """Get cache TTL in minutes based on user plan."""
    ttl_map = {
        'free': 10,
        'pro': 3,
        'enterprise': 0  # No caching, but return 0 for clarity
    }
    return ttl_map.get(user_plan, 10)  # Default to free tier
```

## Cache Key Strategy

### Hash-Based Cache Keys

Use MD5 hash of sorted parameters to create consistent cache keys:

**Example**:
```python
params = {
    "limit": 20,
    "workflowId": "workflow_123",
    "status": "success"
}
# Hash: a1b2c3d4
# Cache key: n8n_executions:instance_456:a1b2c3d4
```

**Benefits**:
- Consistent keys for same parameters
- Short cache keys (better for Redis)
- Handles parameter order differences

### Cache Key Components

Always include in cache key:
- `instance_id`: Different instances have different data
- `limit`: Different limits return different data
- `workflowId`: Filtering by workflow changes results
- `status`: Filtering by status changes results
- `cursor`: Pagination requires different cache entries

**Do NOT include in cache key**:
- `user_id`: Already scoped by instance ownership
- Timestamps: Use TTL for expiration instead

## Cache Warming Strategies

### 1. On User Login

Pre-warm cache when user logs in for common queries.

**Implementation**:
- Trigger background job to fetch and cache executions for all user instances
- **Skip Enterprise users** (they don't use cache)
- Cache with common parameters (limit=20, no filters)
- Use lower priority/async task to avoid blocking login

### 2. Background Job

Periodic background job to refresh cache before expiration.

**Implementation**:
- Run every 3-5 minutes
- Refresh cache for active users (users who logged in within last 24 hours)
- **Skip Enterprise users** (they don't use cache)
- Focus on most common queries (limit=20, no filters)
- Use queue system (Celery, RQ, etc.) to avoid blocking main application

### 3. Proactive Refresh

Refresh cache when user navigates to dashboard (if cache is close to expiration).

**Implementation**:
- Check cache age
- **Skip Enterprise users** (they don't use cache)
- If cache is >80% of TTL, refresh in background
- Return current cached data immediately

## Cache Metrics and Monitoring

### Metrics to Track

1. **Cache Hit Rate**: Percentage of requests served from cache
2. **Cache Miss Rate**: Percentage of requests requiring n8n API calls
3. **Average Response Time**: Compare cached vs non-cached responses
4. **Cache Size**: Monitor memory/Redis usage
5. **n8n API Call Reduction**: Track reduction in actual API calls

### Monitoring

- Log cache hits/misses with instance_id and params
- Alert on low cache hit rate (<50%)
- Monitor cache size growth
- Track n8n API call reduction percentage
- Monitor cache TTL effectiveness

## Benefits of Caching Raw API Responses

### 1. Flexibility

- App can calculate any metric from cached data
- Success rate, average duration, execution counts, etc.
- No need to pre-calculate statistics

### 2. Single Cache, Multiple Uses

- Same cache serves dashboard statistics
- Same cache serves executions list view
- Same cache serves workflow detail views
- Reduces redundant API calls

### 3. Simpler Invalidation

- Invalidate cache when new execution completes
- No need to recalculate multiple statistics
- App recalculates from fresh data

### 4. Better Performance

- Faster response times (no n8n API wait)
- Reduced n8n instance load
- Better user experience

## Future Enhancements

### 1. Smart Cache Invalidation

Invalidate cache based on execution events:
- When workflow execution completes (invalidate relevant cache entries)
- When workflow is toggled (optional invalidation)
- When instance is updated (invalidate all instance caches)

### 2. Tiered Caching

Different cache strategies based on user plan:
- **Free**: Longer TTL (10 min), less frequent refresh
- **Pro**: Shorter TTL (3 min), more frequent refresh
- **Enterprise**: **NO CACHING** (always fresh data, real-time updates)

### 3. Cache Prefetching

Predict user behavior and prefetch likely-needed data:
- Prefetch on app open (common queries)
- Prefetch based on user patterns
- Prefetch for frequently accessed instances/workflows

### 4. Distributed Caching

For multi-server deployments:
- Use Redis cluster
- Implement cache replication
- Handle cache synchronization

## Implementation Checklist

- [ ] Choose cache backend (Redis recommended)
- [ ] Implement cache key generation (hash-based)
- [ ] Implement cache get/set functions
- [ ] Add caching to `get_executions` method in `WorkflowService`
- [ ] Add `refresh` parameter to bypass cache
- [ ] Add TTL based on user plan (skip caching for enterprise users)
- [ ] Implement user plan check to bypass cache for enterprise tier
- [ ] Implement cache invalidation
- [ ] Add fallback to direct API calls on cache miss
- [ ] Implement cache warming on login
- [ ] Add background job for cache refresh
- [ ] Add cache metrics and monitoring
- [ ] Test cache performance
- [ ] Document cache configuration

## Configuration

### Environment Variables

```bash
# Redis configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Cache TTL (in minutes)
# Note: Enterprise plan (3rd plan and above) bypasses cache entirely
CACHE_TTL_FREE=10
CACHE_TTL_PRO=3
# CACHE_TTL_ENTERPRISE is not used (enterprise users get no caching)

# Cache warming
ENABLE_CACHE_WARMING=true
CACHE_WARMING_INTERVAL=5  # minutes

# Cache bypass
ENABLE_CACHE_BYPASS=true  # Allow ?refresh=true parameter
```

## Plan-Based Caching Strategy

### Free Plan
- **Caching**: Enabled
- **TTL**: 10 minutes
- **Rationale**: Reduce API load for free tier users

### Pro Plan
- **Caching**: Enabled
- **TTL**: 3 minutes
- **Rationale**: Fresher data for paying customers while still reducing API load

### Enterprise Plan (3rd Plan and Above)
- **Caching**: **DISABLED**
- **TTL**: N/A (no caching)
- **Rationale**: Enterprise users pay for real-time, always-fresh data with no caching overhead

**Implementation Note**: Always check user plan before using cache. Enterprise users should bypass cache entirely, ensuring they always get the latest data directly from n8n instances.

## Notes

- **Start Simple**: Begin with in-memory cache for MVP, upgrade to Redis when scaling
- **Monitor Performance**: Track cache hit rates and adjust TTLs as needed
- **User Feedback**: Consider user feedback on data freshness
- **Balance**: Balance between freshness and API load (except enterprise - always fresh)
- **App Responsibility**: Mobile app calculates statistics from cached execution data
- **Cache Key Design**: Use hash-based keys for consistency and efficiency
- **Enterprise Priority**: Enterprise users get premium experience with real-time data
