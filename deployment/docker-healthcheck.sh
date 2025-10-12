#!/bin/bash

# Docker health check script for VidNet
# This script is used by Docker's HEALTHCHECK instruction

set -e

# Configuration
HEALTH_URL="http://localhost:8000/health"
API_URL="http://localhost:8000/api/v1/monitoring/status"
TIMEOUT=10
MAX_RETRIES=3

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${1}[$(date +'%Y-%m-%d %H:%M:%S')] $2${NC}" >&2
}

# Check if curl is available
if ! command -v curl &> /dev/null; then
    log "$RED" "ERROR: curl is not available"
    exit 1
fi

# Function to check HTTP endpoint
check_endpoint() {
    local url=$1
    local name=$2
    local retry_count=0
    
    while [ $retry_count -lt $MAX_RETRIES ]; do
        if curl -f -s --max-time $TIMEOUT "$url" > /dev/null 2>&1; then
            log "$GREEN" "✅ $name check passed"
            return 0
        else
            retry_count=$((retry_count + 1))
            if [ $retry_count -lt $MAX_RETRIES ]; then
                log "$YELLOW" "⚠️ $name check failed, retrying ($retry_count/$MAX_RETRIES)..."
                sleep 2
            fi
        fi
    done
    
    log "$RED" "❌ $name check failed after $MAX_RETRIES attempts"
    return 1
}

# Function to check Redis connectivity (through app)
check_redis() {
    local response
    response=$(curl -f -s --max-time $TIMEOUT "$API_URL" 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        # Check if response contains Redis status
        if echo "$response" | grep -q '"redis"'; then
            log "$GREEN" "✅ Redis connectivity check passed"
            return 0
        fi
    fi
    
    log "$RED" "❌ Redis connectivity check failed"
    return 1
}

# Function to check system resources
check_resources() {
    # Check available memory (at least 100MB)
    local available_memory
    available_memory=$(free -m | awk 'NR==2{printf "%.0f", $7}')
    
    if [ "$available_memory" -gt 100 ]; then
        log "$GREEN" "✅ Memory check passed (${available_memory}MB available)"
    else
        log "$YELLOW" "⚠️ Low memory warning (${available_memory}MB available)"
    fi
    
    # Check disk space (at least 1GB)
    local available_disk
    available_disk=$(df / | awk 'NR==2{print $4}')
    available_disk_gb=$((available_disk / 1024 / 1024))
    
    if [ "$available_disk_gb" -gt 1 ]; then
        log "$GREEN" "✅ Disk space check passed (${available_disk_gb}GB available)"
    else
        log "$YELLOW" "⚠️ Low disk space warning (${available_disk_gb}GB available)"
    fi
    
    return 0
}

# Main health check function
main() {
    log "$GREEN" "Starting VidNet health check..."
    
    local exit_code=0
    
    # Check main health endpoint
    if ! check_endpoint "$HEALTH_URL" "Health endpoint"; then
        exit_code=1
    fi
    
    # Check API status endpoint
    if ! check_endpoint "$API_URL" "API status endpoint"; then
        exit_code=1
    fi
    
    # Check Redis connectivity
    if ! check_redis; then
        exit_code=1
    fi
    
    # Check system resources (warnings only)
    check_resources
    
    if [ $exit_code -eq 0 ]; then
        log "$GREEN" "🎉 All health checks passed"
    else
        log "$RED" "💥 Health check failed"
    fi
    
    exit $exit_code
}

# Handle script arguments
case "${1:-}" in
    --help|-h)
        echo "Usage: $0 [--help|--verbose]"
        echo "Docker health check script for VidNet"
        echo ""
        echo "Options:"
        echo "  --help, -h     Show this help message"
        echo "  --verbose, -v  Enable verbose output"
        exit 0
        ;;
    --verbose|-v)
        set -x
        ;;
esac

# Run main function
main