# VidNet Deployment Guide

This directory contains all the necessary configuration files and scripts for deploying VidNet to production environments.

## Quick Start

### 1. Platform Deployment (Recommended)

#### Render Deployment
```bash
# 1. Push code to GitHub
git add .
git commit -m "Deploy to production"
git push origin main

# 2. Connect repository to Render
# - Go to https://dashboard.render.com/
# - Create new Web Service
# - Connect your GitHub repository
# - Render will automatically use render.yaml configuration

# 3. Set up Redis
# - Create Redis service in Render dashboard
# - Copy connection URL to environment variables
```

#### Railway Deployment
```bash
# 1. Install Railway CLI
npm install -g @railway/cli

# 2. Login and deploy
railway login
railway up

# 3. Set environment variables in Railway dashboard
```

### 2. Docker Deployment

#### Local Development
```bash
# Start development environment
docker-compose -f docker-compose.dev.yml up -d

# View logs
docker-compose -f docker-compose.dev.yml logs -f
```

#### Production with Docker Compose
```bash
# Deploy production stack
./deployment/deploy.sh production docker

# Or manually:
docker-compose -f docker-compose.prod.yml up -d
```

### 3. Kubernetes Deployment

```bash
# Apply all Kubernetes manifests
kubectl apply -f deployment/k8s/

# Check deployment status
kubectl get pods -n vidnet
kubectl get services -n vidnet
kubectl get ingress -n vidnet
```

## Configuration Files

### Platform Configurations
- `render.yaml` - Render platform configuration
- `railway.json` - Railway platform configuration
- `.env.production` - Production environment variables template

### Docker Configurations
- `Dockerfile` - Multi-stage Docker build
- `docker-compose.yml` - Development environment
- `docker-compose.prod.yml` - Production environment
- `docker-healthcheck.sh` - Container health check script

### Kubernetes Configurations
- `k8s/namespace.yaml` - Kubernetes namespace
- `k8s/configmap.yaml` - Configuration management
- `k8s/secret.yaml` - Secrets management
- `k8s/deployment.yaml` - Application deployment
- `k8s/service.yaml` - Service definitions
- `k8s/redis.yaml` - Redis deployment
- `k8s/ingress.yaml` - Ingress configuration
- `k8s/hpa.yaml` - Horizontal Pod Autoscaler

### CI/CD Configurations
- `.github/workflows/deploy.yml` - Deployment pipeline
- `.github/workflows/test.yml` - Test pipeline
- `deploy.sh` - Deployment script

### Monitoring and Health Checks
- `monitoring.py` - Production monitoring utilities
- `docker-healthcheck.sh` - Docker health check script

## Environment Setup

### Required Environment Variables

#### Core Application
```bash
ENVIRONMENT=production
DEBUG=false
REDIS_URL=redis://your-redis-url:6379
```

#### Performance Configuration
```bash
RATE_LIMIT_REQUESTS_PER_MINUTE=100
RATE_LIMIT_REQUESTS_PER_HOUR=2000
PERFORMANCE_MONITORING_ENABLED=true
METADATA_CACHE_TTL=3600
DOWNLOAD_CACHE_TTL=1800
```

#### Optional Analytics
```bash
GOOGLE_ANALYTICS_ID=GA_MEASUREMENT_ID
FACEBOOK_PIXEL_ID=PIXEL_ID
```

### Setting Up External Services

#### 1. Upstash Redis (Recommended)
1. Create account at https://upstash.com/
2. Create Redis database
3. Copy connection URL
4. Set as `REDIS_URL` environment variable

See `upstash-setup.md` for detailed instructions.

#### 2. Cloudflare CDN (Optional)
1. Add domain to Cloudflare
2. Configure caching rules
3. Set up SSL/TLS

See `cloudflare-setup.md` for detailed instructions.

## Deployment Strategies

### 1. Blue-Green Deployment

```bash
# Deploy to staging environment first
./deployment/deploy.sh staging render

# Test staging environment
curl https://staging.yourdomain.com/health

# Deploy to production
./deployment/deploy.sh production render
```

### 2. Rolling Deployment (Kubernetes)

```bash
# Update image in deployment
kubectl set image deployment/vidnet-api vidnet-api=ghcr.io/your-repo/vidnet:new-tag -n vidnet

# Monitor rollout
kubectl rollout status deployment/vidnet-api -n vidnet

# Rollback if needed
kubectl rollout undo deployment/vidnet-api -n vidnet
```

### 3. Canary Deployment

```bash
# Deploy canary version (10% traffic)
kubectl apply -f deployment/k8s/canary/

# Monitor metrics and gradually increase traffic
# If successful, promote to full deployment
```

## Monitoring and Observability

### Health Checks

#### Application Health
```bash
curl https://yourdomain.com/health
```

#### Detailed Status
```bash
curl https://yourdomain.com/api/v1/monitoring/status
```

#### Metrics
```bash
curl https://yourdomain.com/api/v1/monitoring/metrics
```

### Log Aggregation

#### Docker Logs
```bash
docker-compose logs -f app
```

#### Kubernetes Logs
```bash
kubectl logs -f deployment/vidnet-api -n vidnet
```

### Performance Monitoring

The application includes built-in performance monitoring:
- Response time tracking
- Resource usage monitoring
- Cache hit rate monitoring
- Error rate tracking

Access monitoring dashboard at: `/api/v1/monitoring/dashboard`

## Security Considerations

### 1. Environment Variables
- Never commit `.env.production` to version control
- Use platform-provided secret management
- Rotate secrets regularly

### 2. Container Security
- Run containers as non-root user
- Use minimal base images
- Regularly update dependencies
- Scan images for vulnerabilities

### 3. Network Security
- Use HTTPS/TLS for all communications
- Implement proper CORS policies
- Use rate limiting and DDoS protection
- Restrict network access between services

### 4. Data Security
- Encrypt data in transit and at rest
- Implement proper access controls
- Regular security audits
- Backup and recovery procedures

## Troubleshooting

### Common Issues

#### 1. Container Won't Start
```bash
# Check logs
docker logs container-name

# Check health status
docker exec container-name /usr/local/bin/healthcheck.sh
```

#### 2. Redis Connection Issues
```bash
# Test Redis connectivity
redis-cli -u $REDIS_URL ping

# Check Redis logs
docker logs redis-container
```

#### 3. High Memory Usage
```bash
# Check container stats
docker stats

# Monitor application metrics
curl https://yourdomain.com/api/v1/monitoring/metrics
```

#### 4. Slow Response Times
```bash
# Check performance metrics
curl https://yourdomain.com/api/v1/monitoring/status

# Monitor cache hit rates
# Check Redis memory usage
# Review application logs
```

### Debug Commands

#### Docker
```bash
# Enter container shell
docker exec -it container-name /bin/bash

# Check container resources
docker stats container-name

# Inspect container configuration
docker inspect container-name
```

#### Kubernetes
```bash
# Get pod details
kubectl describe pod pod-name -n vidnet

# Check events
kubectl get events -n vidnet --sort-by='.lastTimestamp'

# Port forward for debugging
kubectl port-forward pod/pod-name 8000:8000 -n vidnet
```

## Performance Optimization

### 1. Caching Strategy
- Redis for metadata caching (1 hour TTL)
- CDN for static assets (1 month TTL)
- Application-level caching for frequent operations

### 2. Resource Optimization
- Use multi-stage Docker builds
- Optimize container resource limits
- Implement horizontal pod autoscaling
- Use connection pooling for Redis

### 3. Monitoring and Alerting
- Set up performance alerts
- Monitor key metrics (response time, error rate, throughput)
- Implement log aggregation and analysis
- Regular performance testing

## Scaling Considerations

### Horizontal Scaling
- Use load balancers for traffic distribution
- Implement stateless application design
- Use external Redis for session storage
- Configure auto-scaling based on metrics

### Vertical Scaling
- Monitor resource usage patterns
- Adjust container resource limits
- Optimize application performance
- Use appropriate instance sizes

### Database Scaling
- Use Redis clustering for high availability
- Implement read replicas if needed
- Monitor cache hit rates and memory usage
- Consider Redis persistence options

## Backup and Recovery

### Application Data
- Regular database backups (if applicable)
- Configuration backup procedures
- Disaster recovery planning
- Testing recovery procedures

### Redis Data
- Configure Redis persistence (AOF/RDB)
- Regular backup of Redis data
- Cross-region replication for critical data
- Monitoring backup integrity

## Cost Optimization

### Platform Costs
- Monitor resource usage and optimize
- Use appropriate service tiers
- Implement auto-scaling to reduce costs
- Regular cost analysis and optimization

### External Services
- Monitor Upstash Redis usage and costs
- Optimize Cloudflare caching rules
- Review analytics service costs
- Implement cost alerts and budgets