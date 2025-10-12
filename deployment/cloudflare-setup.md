# Cloudflare CDN Setup for VidNet

## Overview

Cloudflare CDN will accelerate static asset delivery (CSS, JS, images) and provide additional security and performance benefits.

## Setup Steps

### 1. Domain and DNS Setup

#### Option A: Use Cloudflare as DNS Provider
1. Add your domain to Cloudflare
2. Update nameservers at your registrar
3. Enable "Proxied" (orange cloud) for your domain

#### Option B: CNAME Setup (if using platform subdomain)
1. Create CNAME record pointing to your app
2. Enable Cloudflare proxy

### 2. SSL/TLS Configuration
```
SSL/TLS Mode: Full (Strict)
Always Use HTTPS: On
Minimum TLS Version: 1.2
```

### 3. Caching Rules

#### Static Assets Caching
```
Rule: Cache everything for static files
Match: *.css, *.js, *.png, *.jpg, *.svg, *.ico, *.woff2
Cache Level: Cache Everything
Edge Cache TTL: 1 month
Browser Cache TTL: 1 day
```

#### API Endpoints
```
Rule: Bypass cache for API
Match: /api/*
Cache Level: Bypass
```

#### HTML Files
```
Rule: Cache HTML with short TTL
Match: *.html
Cache Level: Cache Everything
Edge Cache TTL: 1 hour
Browser Cache TTL: 5 minutes
```

### 4. Page Rules Configuration

Create these page rules in order:

#### 1. API Bypass (Priority: 1)
```
URL Pattern: yourdomain.com/api/*
Settings:
  - Cache Level: Bypass
  - Disable Apps
  - Disable Performance
```

#### 2. Static Assets (Priority: 2)
```
URL Pattern: yourdomain.com/static/*
Settings:
  - Cache Level: Cache Everything
  - Edge Cache TTL: 1 month
  - Browser Cache TTL: 1 day
```

#### 3. Root Domain (Priority: 3)
```
URL Pattern: yourdomain.com/*
Settings:
  - Cache Level: Standard
  - Browser Cache TTL: 4 hours
```

### 5. Performance Optimization

#### Speed Settings
```
Auto Minify:
  - JavaScript: On
  - CSS: On
  - HTML: On

Brotli Compression: On
Early Hints: On (if available)
```

#### Image Optimization
```
Polish: Lossless
WebP Conversion: On
Mirage: On (mobile optimization)
```

### 6. Security Configuration

#### Security Settings
```
Security Level: Medium
Challenge Passage: 30 minutes
Browser Integrity Check: On
```

#### Firewall Rules
```
# Block common attack patterns
(http.request.uri.path contains "/admin" and ip.geoip.country ne "US")
Action: Block

# Rate limiting for API
(http.request.uri.path matches "^/api/.*" and rate(1m) > 100)
Action: Challenge
```

### 7. Workers for Advanced Caching

Create a Cloudflare Worker for intelligent caching:

```javascript
// cloudflare-worker.js
addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
})

async function handleRequest(request) {
  const url = new URL(request.url)
  
  // Cache static assets aggressively
  if (url.pathname.startsWith('/static/')) {
    const cache = caches.default
    const cacheKey = new Request(url.toString(), request)
    
    let response = await cache.match(cacheKey)
    
    if (!response) {
      response = await fetch(request)
      
      if (response.status === 200) {
        const headers = new Headers(response.headers)
        headers.set('Cache-Control', 'public, max-age=31536000, immutable')
        headers.set('Vary', 'Accept-Encoding')
        
        response = new Response(response.body, {
          status: response.status,
          statusText: response.statusText,
          headers: headers
        })
        
        event.waitUntil(cache.put(cacheKey, response.clone()))
      }
    }
    
    return response
  }
  
  // Pass through API requests without caching
  if (url.pathname.startsWith('/api/')) {
    return fetch(request)
  }
  
  // Cache HTML with short TTL
  const response = await fetch(request)
  
  if (response.headers.get('content-type')?.includes('text/html')) {
    const headers = new Headers(response.headers)
    headers.set('Cache-Control', 'public, max-age=3600')
    
    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: headers
    })
  }
  
  return response
}
```

### 8. Analytics and Monitoring

#### Enable Cloudflare Analytics
```
Web Analytics: On
Core Web Vitals: On
```

#### Custom Analytics Events
```javascript
// Track performance metrics
analytics.track('page_load_time', {
  value: performance.now(),
  url: window.location.href
})
```

### 9. Configuration Files

#### Nginx Configuration (if using)
```nginx
# nginx.conf additions for Cloudflare
location /static/ {
    expires 1y;
    add_header Cache-Control "public, immutable";
    add_header Vary "Accept-Encoding";
}

# Trust Cloudflare IPs
set_real_ip_from 173.245.48.0/20;
set_real_ip_from 103.21.244.0/22;
set_real_ip_from 103.22.200.0/22;
real_ip_header CF-Connecting-IP;
```

#### Application Headers
```python
# In FastAPI app
from fastapi.responses import FileResponse

@app.get("/static/{file_path:path}")
async def serve_static(file_path: str):
    response = FileResponse(f"static/{file_path}")
    response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    response.headers["Vary"] = "Accept-Encoding"
    return response
```

### 10. Performance Testing

#### Test CDN Performance
```bash
# Test cache headers
curl -I https://yourdomain.com/static/style.css

# Test compression
curl -H "Accept-Encoding: gzip" -I https://yourdomain.com/

# Test from different locations
curl -I https://yourdomain.com/ --resolve yourdomain.com:443:CLOUDFLARE_IP
```

#### Monitor Metrics
- Cache hit ratio (target: >95% for static assets)
- Time to First Byte (TTFB)
- Core Web Vitals scores
- Bandwidth savings

### 11. Cost Optimization

#### Free Plan Features:
- Unlimited bandwidth
- Basic DDoS protection
- SSL certificates
- Basic analytics

#### Pro Plan Benefits ($20/month):
- Advanced analytics
- Image optimization
- Mobile optimization
- Priority support

### 12. Troubleshooting

#### Common Issues:
1. **Mixed Content**: Ensure all assets use HTTPS
2. **Cache Purging**: Use Cloudflare API or dashboard
3. **Origin Errors**: Check backend health
4. **SSL Issues**: Verify certificate chain

#### Debug Commands:
```bash
# Check DNS resolution
dig yourdomain.com

# Test SSL
openssl s_client -connect yourdomain.com:443

# Check headers
curl -I https://yourdomain.com/
```