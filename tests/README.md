# VidNet Comprehensive Test Suite

This directory contains the comprehensive test suite for VidNet, implementing task 18 from the implementation plan. The test suite provides thorough validation of all system components and performance characteristics.

## Test Categories

### 1. Integration Tests (`test_complete_download_workflows.py`)
- **Purpose**: End-to-end workflow validation
- **Coverage**: Complete download workflows from API request to file serving
- **Key Tests**:
  - Video download workflow
  - Audio extraction workflow  
  - Download cancellation
  - Error handling
  - Concurrent downloads
  - File security

### 2. Performance Tests (`test_load_performance.py`)
- **Purpose**: Concurrent user scenario validation
- **Coverage**: System performance under various load conditions
- **Key Tests**:
  - 100+ concurrent user handling
  - Rate limiting effectiveness
  - Graceful degradation
  - Performance monitoring accuracy

### 3. Platform Compatibility Tests (`test_platform_compatibility_integration.py`)
- **Purpose**: Real URL validation across all supported platforms
- **Coverage**: Platform detection, URL validation, and metadata extraction
- **Supported Platforms**:
  - YouTube (youtube.com, youtu.be)
  - TikTok (tiktok.com, vm.tiktok.com)
  - Instagram (instagram.com)
  - Facebook (facebook.com, fb.watch)
  - Twitter/X (twitter.com, x.com)
  - Reddit (reddit.com, v.redd.it)
  - Vimeo (vimeo.com)
  - Direct video links (.mp4, .avi, .mov, etc.)

### 4. Load Testing (`test_scalability_load_testing.py`)
- **Purpose**: Scalability validation under various load patterns
- **Coverage**: System behavior under different load scenarios
- **Test Scenarios**:
  - Baseline performance (1 user)
  - Moderate load (25 users)
  - High concurrent load (100+ users)
  - Sustained load (long duration)
  - Spike load (sudden increases)
  - Resource usage monitoring

### 5. Uptime Monitoring (`test_uptime_monitoring.py`)
- **Purpose**: Service availability and response time validation
- **Coverage**: System uptime and performance monitoring
- **Key Metrics**:
  - Uptime percentage (target: 99%+)
  - Response time requirements (target: <3s)
  - Service degradation detection
  - Recovery monitoring

## Test Infrastructure

### Configuration (`conftest.py`)
- Shared fixtures and test utilities
- Mock services for isolated testing
- Test data providers
- Performance assertion helpers

### Comprehensive Runner (`test_comprehensive_suite_runner.py`)
- Unified test execution framework
- Configurable test selection
- Detailed reporting and analysis
- Performance metrics collection

### CLI Runner (`../run_comprehensive_tests.py`)
- Command-line interface for test execution
- Flexible test configuration
- HTML and JSON report generation

## Usage

### Running All Tests
```bash
# Run complete comprehensive test suite
python run_comprehensive_tests.py --all

# Run with custom configuration
python run_comprehensive_tests.py --all --users 75 --duration 120
```

### Running Specific Test Categories
```bash
# Integration tests only
python run_comprehensive_tests.py --integration

# Performance and load tests
python run_comprehensive_tests.py --performance --load

# Platform compatibility tests
python run_comprehensive_tests.py --platform

# Uptime monitoring tests
python run_comprehensive_tests.py --uptime --uptime-duration 10
```

### Using Pytest Directly
```bash
# Run all tests with pytest
pytest tests/ -v

# Run specific test categories
pytest tests/ -m integration
pytest tests/ -m performance
pytest tests/ -m platform

# Run specific test files
pytest tests/test_platform_compatibility_integration.py -v
pytest tests/test_scalability_load_testing.py::ScalabilityTestSuite::test_high_concurrent_load
```

### Quick Testing Mode
```bash
# Run abbreviated tests for faster feedback
python run_comprehensive_tests.py --all --quick
```

## Test Requirements Validation

The comprehensive test suite validates the following requirements from the VidNet specification:

### Requirement 4.2 - Performance Under Load
- ✅ 100+ concurrent user handling
- ✅ Response time monitoring (<3s target)
- ✅ Rate limiting effectiveness
- ✅ Graceful degradation

### Requirement 5.1 & 5.2 - Scalability
- ✅ Asynchronous request processing
- ✅ Resource management under load
- ✅ Auto-cleanup functionality
- ✅ Queue management

### Requirement 5.3 - Caching Performance
- ✅ Redis cache effectiveness
- ✅ Metadata serving optimization
- ✅ Cache hit rate monitoring

### Requirements 6.1-6.6 - Platform Support
- ✅ YouTube URL processing
- ✅ TikTok URL processing  
- ✅ Instagram URL processing
- ✅ Facebook URL processing
- ✅ Twitter/X URL processing
- ✅ Reddit URL processing
- ✅ Vimeo URL processing
- ✅ Direct video link processing
- ✅ Error handling for unsupported platforms

## Performance Benchmarks

### Target Performance Metrics
- **Uptime**: 99%+ availability
- **Response Time**: <3s for download preparation
- **Metadata Fetch**: <200ms with cache
- **Concurrent Users**: 100+ without degradation
- **Success Rate**: 90%+ under normal load
- **Cache Hit Rate**: 80%+ for repeated requests

### Load Test Scenarios
1. **Baseline**: 1 user, 30s duration
2. **Moderate**: 25 users, 60s duration  
3. **High Load**: 100 users, 120s duration
4. **Sustained**: 50 users, 300s duration
5. **Spike**: 150 users, rapid ramp-up

## Output and Reporting

### Test Results Directory Structure
```
test_results/
├── comprehensive_test_report_[timestamp].json    # Detailed JSON results
├── test_report_[timestamp].html                  # HTML dashboard
├── load_test_results.json                        # Load test metrics
├── uptime_report.json                           # Uptime monitoring data
└── test_runner.log                              # Execution logs
```

### HTML Report Features
- Executive summary with pass/fail rates
- Performance metrics visualization
- Test execution timeline
- Error analysis and recommendations
- Platform compatibility matrix

### JSON Report Contents
- Detailed test results with timing
- Performance metrics and benchmarks
- Error categorization and analysis
- System resource usage data
- Recommendations for improvements

## Continuous Integration

### GitHub Actions Integration
```yaml
# Example CI configuration
- name: Run Comprehensive Tests
  run: |
    python run_comprehensive_tests.py --all --quick
    
- name: Upload Test Results
  uses: actions/upload-artifact@v3
  with:
    name: test-results
    path: test_results/
```

### Performance Regression Detection
- Automated performance baseline comparison
- Alert on response time degradation
- Success rate monitoring
- Resource usage trend analysis

## Troubleshooting

### Common Issues

1. **Import Errors**
   - Ensure you're running from project root
   - Check Python path configuration
   - Verify all dependencies are installed

2. **Network Timeouts**
   - Tests use mocked external services
   - Check firewall/proxy settings if needed
   - Increase timeout values for slow systems

3. **Resource Constraints**
   - Reduce concurrent user counts for limited systems
   - Use `--quick` mode for faster execution
   - Monitor system resources during tests

4. **Test Failures**
   - Check detailed logs in test_results/
   - Review HTML report for specific failures
   - Verify system dependencies (Redis, FFmpeg)

### Performance Tuning
- Adjust concurrent user limits based on system capacity
- Modify test durations for thorough vs. quick testing
- Configure timeout values for network conditions
- Customize performance thresholds for environment

## Contributing

When adding new tests to the comprehensive suite:

1. Follow existing test patterns and naming conventions
2. Add appropriate markers (@pytest.mark.integration, etc.)
3. Include performance assertions where relevant
4. Update this README with new test descriptions
5. Ensure tests work with mocked dependencies
6. Add configuration options to the test runner

## Dependencies

### Required Packages
- pytest (test framework)
- pytest-asyncio (async test support)
- httpx (HTTP client for load testing)
- psutil (system resource monitoring)

### Optional Packages
- pytest-html (HTML report generation)
- pytest-cov (coverage reporting)
- pytest-xdist (parallel test execution)

### System Requirements
- Python 3.8+
- Sufficient memory for concurrent testing
- Network access for integration tests (mocked)
- Disk space for test result storage