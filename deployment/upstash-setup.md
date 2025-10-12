# Upstash Redis Setup for Production

## Overview

Upstash provides serverless Redis with automatic scaling and pay-per-request pricing, perfect for VidNet's caching needs.

## Setup Steps

### 1. Create Upstash Account
1. Visit https://upstash.com/
2. Sign up with GitHub/Google or email
3. Verify your account

### 2. Create Redis Database
1. Click "Create Database" in dashboard
2. Configure database:
   - **Name**: `vidnet-cache`
   - **Region**: Choose closest to your app deployment (e.g., `us-east-1` for Render Oregon)
   - **Type**: Regional (for better performance)
   - **Eviction**: `allkeys-lru` (recommended for caching)

### 3. Configure Database Settings
```
Max Memory: 256MB (starter) / 1GB+ (production)
Max Connections: 1000
Max Request Size: 1MB
Max Daily Requests: 10,000 (free tier) / Unlimited (paid)
```

### 4. Get Connection Details
After creation, copy:
- **UPSTASH_REDIS_REST_URL**: For REST API access
- **UPSTASH_REDIS_REST_TOKEN**: Authentication token
- **Redis URL**: Standard Redis connection string

### 5. Environment Configuration

#### For Render:
```bash
# In Render dashboard environment variables
REDIS_URL=rediss://default:YOUR_PASSWORD@YOUR_ENDPOINT:6380
```

#### For Railway:
```bash
# In Railway project variables
REDIS_URL=rediss://default:YOUR_PASSWORD@YOUR_ENDPOINT:6380
```

#### For Docker Compose:
```yaml
# In docker-compose.prod.yml
environment:
  - REDIS_URL=rediss://default:YOUR_PASSWORD@YOUR_ENDPOINT:6380
```

### 6. Connection Validation

Test connection with Python:
```python
import redis
import os

# Test connection
r = redis.from_url(os.getenv('REDIS_URL'))
r.ping()  # Should return True
```

### 7. Performance Optimization

#### Cache Configuration
```python
# Recommended settings for VidNet
METADATA_CACHE_TTL=3600      # 1 hour for video metadata
DOWNLOAD_CACHE_TTL=1800      # 30 minutes for download links
```

#### Memory Management
```python
# Upstash Redis configuration
maxmemory-policy: allkeys-lru
maxmemory: 256mb  # Adjust based on plan
```

### 8. Monitoring and Alerts

#### Upstash Dashboard Metrics:
- Memory usage
- Request count
- Connection count
- Hit/miss ratio

#### Application Metrics:
- Cache hit rate (target: >80%)
- Response time improvement
- Memory usage patterns

### 9. Scaling Considerations

#### Free Tier Limits:
- 10,000 requests/day
- 256MB storage
- 1000 connections

#### Paid Tier Benefits:
- Unlimited requests
- Up to 50GB storage
- Higher connection limits
- Advanced monitoring

### 10. Backup and Recovery

Upstash provides:
- Automatic daily backups
- Point-in-time recovery
- Cross-region replication (paid plans)

### 11. Security Features

- TLS encryption in transit
- Authentication via password/token
- IP allowlisting (paid plans)
- VPC peering (enterprise)

## Integration with VidNet

### Cache Strategy
```python
# Video metadata caching
cache_key = f"metadata:{url_hash}"
ttl = 3600  # 1 hour

# Download link caching  
cache_key = f"download:{task_id}"
ttl = 1800  # 30 minutes

# Rate limiting data
cache_key = f"rate_limit:{client_id}"
ttl = 3600  # 1 hour window
```

### Error Handling
```python
# Graceful degradation when Redis is unavailable
try:
    cached_data = redis_client.get(cache_key)
except redis.ConnectionError:
    # Fall back to direct processing
    cached_data = None
```

## Cost Estimation

### Free Tier (Development):
- $0/month
- 10K requests/day
- 256MB storage

### Pro Tier (Production):
- ~$20-50/month
- Unlimited requests
- 1GB+ storage
- Better performance

### Monitoring Costs:
- Track daily request count
- Monitor memory usage
- Set up billing alerts