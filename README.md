# VidNet - HD Video Downloader

A high-performance video downloading service built with FastAPI, supporting multiple platforms including YouTube, TikTok, Instagram, Facebook, and more.

## Quick Start

### Development Setup

1. Clone the repository
2. Copy environment configuration:
   ```bash
   cp .env.example .env
   ```

3. Start with Docker Compose (Development):
   ```bash
   docker-compose -f docker-compose.dev.yml up --build
   ```

4. Access the application:
   - API: http://localhost:8000
   - Health Check: http://localhost:8000/health
   - Static Files: http://localhost/static/

### Production Setup

```bash
docker-compose -f docker-compose.prod.yml up -d --build
```

## Project Structure

```
vidnet-mvp/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── api/                 # API routes
│   ├── core/                # Core utilities
│   ├── models/              # Data models
│   └── services/            # Business logic
├── static/                  # Static files
├── downloads/               # Temporary download storage
├── logs/                    # Application logs
├── tests/                   # Test files
├── docker-compose.yml       # Main compose file
├── docker-compose.dev.yml   # Development configuration
├── docker-compose.prod.yml  # Production configuration
├── Dockerfile               # Multi-stage Docker build
├── nginx.conf               # Nginx configuration
└── requirements.txt         # Python dependencies
```

## Available Commands

### Docker Commands

```bash
# Development
docker-compose -f docker-compose.dev.yml up --build

# Production
docker-compose -f docker-compose.prod.yml up -d --build

# Stop services
docker-compose down

# View logs
docker-compose logs -f app
```

### Local Development (without Docker)

```bash
# Install dependencies
pip install -r requirements.txt

# Start Redis (required)
redis-server

# Run the application
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Environment Variables

See `.env.example` for all available configuration options.

## Health Check

The application includes a health check endpoint at `/health` that returns the service status.

## Next Steps

This is the basic project structure. The next tasks will implement:
- Data models and validation
- Video processing services
- API endpoints
- Frontend interface
- Analytics integration