#!/bin/bash

# VidNet Deployment Script
# Usage: ./deploy.sh [environment] [platform]
# Example: ./deploy.sh production render

set -e  # Exit on any error

# Configuration
ENVIRONMENT=${1:-production}
PLATFORM=${2:-render}
PROJECT_NAME="vidnet"
DOCKER_IMAGE="vidnet-api"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    # Check if git is installed
    if ! command -v git &> /dev/null; then
        log_error "Git is not installed. Please install Git first."
        exit 1
    fi
    
    # Check if we're in a git repository
    if ! git rev-parse --git-dir > /dev/null 2>&1; then
        log_error "Not in a git repository. Please run from project root."
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Validate environment
validate_environment() {
    log_info "Validating environment configuration..."
    
    if [ "$ENVIRONMENT" = "production" ]; then
        if [ ! -f ".env.production" ]; then
            log_warning ".env.production not found. Using default configuration."
        fi
        
        # Check for required environment variables
        required_vars=("REDIS_URL")
        for var in "${required_vars[@]}"; do
            if [ -z "${!var}" ] && ! grep -q "^$var=" .env.production 2>/dev/null; then
                log_warning "Required environment variable $var not set"
            fi
        done
    fi
    
    log_success "Environment validation completed"
}

# Run tests
run_tests() {
    log_info "Running tests..."
    
    # Build test image
    docker build -t ${DOCKER_IMAGE}-test --target builder .
    
    # Run tests in container
    docker run --rm \
        -v $(pwd):/app \
        -w /app \
        ${DOCKER_IMAGE}-test \
        python -m pytest tests/ -v --tb=short
    
    if [ $? -eq 0 ]; then
        log_success "All tests passed"
    else
        log_error "Tests failed. Deployment aborted."
        exit 1
    fi
}

# Build Docker image
build_image() {
    log_info "Building Docker image for $ENVIRONMENT..."
    
    # Build production image
    docker build \
        --target production \
        --build-arg ENVIRONMENT=$ENVIRONMENT \
        -t $DOCKER_IMAGE:latest \
        -t $DOCKER_IMAGE:$(git rev-parse --short HEAD) \
        .
    
    if [ $? -eq 0 ]; then
        log_success "Docker image built successfully"
    else
        log_error "Docker build failed"
        exit 1
    fi
}

# Test Docker image
test_image() {
    log_info "Testing Docker image..."
    
    # Start container for testing
    CONTAINER_ID=$(docker run -d \
        -p 8001:8000 \
        -e ENVIRONMENT=test \
        -e REDIS_URL=redis://localhost:6379 \
        $DOCKER_IMAGE:latest)
    
    # Wait for container to start
    sleep 10
    
    # Test health endpoint
    if curl -f http://localhost:8001/health > /dev/null 2>&1; then
        log_success "Health check passed"
    else
        log_error "Health check failed"
        docker logs $CONTAINER_ID
        docker stop $CONTAINER_ID
        exit 1
    fi
    
    # Cleanup
    docker stop $CONTAINER_ID
    docker rm $CONTAINER_ID
}

# Deploy to platform
deploy_to_platform() {
    log_info "Deploying to $PLATFORM..."
    
    case $PLATFORM in
        "render")
            deploy_to_render
            ;;
        "railway")
            deploy_to_railway
            ;;
        "docker")
            deploy_with_docker_compose
            ;;
        *)
            log_error "Unsupported platform: $PLATFORM"
            log_info "Supported platforms: render, railway, docker"
            exit 1
            ;;
    esac
}

# Deploy to Render
deploy_to_render() {
    log_info "Deploying to Render..."
    
    # Check if render.yaml exists
    if [ ! -f "render.yaml" ]; then
        log_error "render.yaml not found. Please create render.yaml first."
        exit 1
    fi
    
    # Push to git (Render deploys from git)
    git add .
    git commit -m "Deploy to production - $(date)" || true
    git push origin main
    
    log_success "Code pushed to repository. Render will automatically deploy."
    log_info "Monitor deployment at: https://dashboard.render.com/"
}

# Deploy to Railway
deploy_to_railway() {
    log_info "Deploying to Railway..."
    
    # Check if Railway CLI is installed
    if ! command -v railway &> /dev/null; then
        log_error "Railway CLI not installed. Install from: https://railway.app/cli"
        exit 1
    fi
    
    # Deploy using Railway CLI
    railway login
    railway up
    
    log_success "Deployed to Railway successfully"
}

# Deploy with Docker Compose
deploy_with_docker_compose() {
    log_info "Deploying with Docker Compose..."
    
    # Use production compose file
    docker-compose -f docker-compose.prod.yml down
    docker-compose -f docker-compose.prod.yml up -d --build
    
    # Wait for services to start
    sleep 30
    
    # Test deployment
    if curl -f http://localhost/health > /dev/null 2>&1; then
        log_success "Docker Compose deployment successful"
    else
        log_error "Docker Compose deployment failed"
        docker-compose -f docker-compose.prod.yml logs
        exit 1
    fi
}

# Post-deployment verification
verify_deployment() {
    log_info "Verifying deployment..."
    
    # Wait for deployment to be ready
    sleep 60
    
    case $PLATFORM in
        "render")
            # Render provides the URL in dashboard
            log_info "Check deployment status at Render dashboard"
            ;;
        "railway")
            # Get Railway URL
            RAILWAY_URL=$(railway status --json | jq -r '.deployments[0].url' 2>/dev/null || echo "")
            if [ -n "$RAILWAY_URL" ]; then
                test_deployment_url "$RAILWAY_URL"
            fi
            ;;
        "docker")
            test_deployment_url "http://localhost"
            ;;
    esac
}

# Test deployment URL
test_deployment_url() {
    local url=$1
    log_info "Testing deployment at: $url"
    
    # Test health endpoint
    if curl -f "$url/health" > /dev/null 2>&1; then
        log_success "Health check passed at $url"
    else
        log_error "Health check failed at $url"
        return 1
    fi
    
    # Test API endpoint
    if curl -f "$url/api/v1/monitoring/status" > /dev/null 2>&1; then
        log_success "API endpoints accessible"
    else
        log_warning "API endpoints may not be ready yet"
    fi
}

# Cleanup function
cleanup() {
    log_info "Cleaning up temporary resources..."
    
    # Remove test containers
    docker ps -a --filter "name=vidnet-test" --format "{{.ID}}" | xargs -r docker rm -f
    
    # Remove dangling images
    docker image prune -f
    
    log_success "Cleanup completed"
}

# Main deployment flow
main() {
    log_info "Starting VidNet deployment to $PLATFORM ($ENVIRONMENT)"
    
    # Set trap for cleanup on exit
    trap cleanup EXIT
    
    check_prerequisites
    validate_environment
    
    if [ "$ENVIRONMENT" = "production" ]; then
        run_tests
    fi
    
    build_image
    test_image
    deploy_to_platform
    verify_deployment
    
    log_success "Deployment completed successfully!"
    log_info "Platform: $PLATFORM"
    log_info "Environment: $ENVIRONMENT"
    log_info "Image: $DOCKER_IMAGE:$(git rev-parse --short HEAD)"
}

# Show usage if no arguments
if [ $# -eq 0 ]; then
    echo "Usage: $0 [environment] [platform]"
    echo ""
    echo "Environments: development, staging, production"
    echo "Platforms: render, railway, docker"
    echo ""
    echo "Examples:"
    echo "  $0 production render"
    echo "  $0 staging railway"
    echo "  $0 development docker"
    exit 1
fi

# Run main function
main "$@"