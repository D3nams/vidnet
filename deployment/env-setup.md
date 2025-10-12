# Environment Variables Setup Guide

## Required Environment Variables for Production

### Platform Deployment (Render/Railway)

Set these environment variables in your deployment platform:

#### Core Application Settings
```
ENVIRONMENT=production
DEBUG=false
PORT=8000
```

#### Redis Configuration
```
REDIS_URL=<provided-by-platform-redis-service>
METADATA_CACHE_TTL=3600
DOWNLOAD_CACHE_TTL=1800
```

#### Rate Limiting
```
RATE_LIMIT_REQUESTS_PER_MINUTE=100
RATE_LIMIT_REQUESTS_PER_HOUR=2000
RATE_LIMIT_BURST_LIMIT=20
RATE_LIMIT_QUEUE_SIZE=200
RATE_LIMIT_QUEUE_TIMEOUT=30
RATE_LIMIT_ENABLE_GRACEFUL_DEGRADATION=true
```

#### Performance Monitoring
```
PERFORMANCE_MONITORING_ENABLED=true
PERFORMANCE_RESPONSE_TIME_WARNING=2.0
PERFORMANCE_RESPONSE_TIME_CRITICAL=5.0
PERFORMANCE_CPU_WARNING=70.0
PERFORMANCE_CPU_CRITICAL=90.0
PERFORMANCE_MEMORY_WARNING=75.0
PERFORMANCE_MEMORY_CRITICAL=90.0
```

#### Optional Analytics (set if using)
```
GOOGLE_ANALYTICS_ID=GA_MEASUREMENT_ID
FACEBOOK_PIXEL_ID=PIXEL_ID
```

### Upstash Redis Setup

1. Create account at https://upstash.com/
2. Create Redis database
3. Copy connection URL
4. Set as REDIS_URL environment variable

### Secrets Management

#### For Render:
1. Go to your service dashboard
2. Navigate to Environment tab
3. Add environment variables
4. Mark sensitive values as "Secret"

#### For Railway:
1. Go to your project dashboard
2. Navigate to Variables tab
3. Add environment variables
4. Sensitive values are automatically encrypted

#### For Docker Compose:
1. Create `.env.production` file (not committed to git)
2. Use `docker-compose --env-file .env.production up`

### Security Best Practices

1. Never commit `.env.production` to version control
2. Use platform-provided secret management
3. Rotate secrets regularly
4. Use least-privilege access for service accounts
5. Enable audit logging for secret access

### Environment Validation

The application validates required environment variables on startup:
- REDIS_URL must be accessible
- Performance thresholds must be valid numbers
- Rate limiting values must be positive integers

### Monitoring Environment Health

Health check endpoint: `/health`
Metrics endpoint: `/api/v1/monitoring/metrics`
Status endpoint: `/api/v1/monitoring/status`