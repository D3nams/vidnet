#!/usr/bin/env python3
"""
VidNet Comprehensive Test Runner

This script runs the comprehensive test suite for VidNet, including:
- Integration tests for end-to-end workflows
- Performance tests for concurrent user scenarios  
- Platform compatibility tests with real URLs
- Load testing scripts for scalability validation
- Monitoring tests for uptime and response time requirements

Usage:
    python run_comprehensive_tests.py --all
    python run_comprehensive_tests.py --integration --performance
    python run_comprehensive_tests.py --load --users 100 --duration 120
"""

import asyncio
import sys
import argparse
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from tests.test_comprehensive_suite_runner import ComprehensiveTestRunner, TestSuiteConfig
except ImportError as e:
    print(f"Error importing test modules: {e}")
    print("Make sure you're running from the project root directory")
    sys.exit(1)


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="VidNet Comprehensive Test Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --all                    # Run all tests
  %(prog)s --integration            # Run only integration tests
  %(prog)s --performance --load     # Run performance and load tests
  %(prog)s --load --users 50        # Run load tests with 50 concurrent users
  %(prog)s --uptime --uptime-duration 10  # Run 10-minute uptime test
        """
    )
    
    # Test selection
    test_group = parser.add_argument_group('Test Selection')
    test_group.add_argument("--all", action="store_true", 
                           help="Run all comprehensive tests")
    test_group.add_argument("--integration", action="store_true",
                           help="Run integration tests for end-to-end workflows")
    test_group.add_argument("--performance", action="store_true",
                           help="Run performance tests for concurrent scenarios")
    test_group.add_argument("--platform", action="store_true",
                           help="Run platform compatibility tests")
    test_group.add_argument("--load", action="store_true",
                           help="Run load testing for scalability validation")
    test_group.add_argument("--uptime", action="store_true",
                           help="Run uptime and response time monitoring tests")
    
    # Test configuration
    config_group = parser.add_argument_group('Test Configuration')
    config_group.add_argument("--users", type=int, default=50,
                             help="Number of concurrent users for load tests (default: 50)")
    config_group.add_argument("--duration", type=int, default=60,
                             help="Duration for load tests in seconds (default: 60)")
    config_group.add_argument("--uptime-duration", type=int, default=5,
                             help="Duration for uptime tests in minutes (default: 5)")
    
    # Output configuration
    output_group = parser.add_argument_group('Output Configuration')
    output_group.add_argument("--output", default="test_results",
                             help="Output directory for test results (default: test_results)")
    output_group.add_argument("--no-report", action="store_true",
                             help="Skip generating HTML report")
    output_group.add_argument("--no-save", action="store_true",
                             help="Don't save detailed results to files")
    
    # Execution options
    exec_group = parser.add_argument_group('Execution Options')
    exec_group.add_argument("--verbose", "-v", action="store_true",
                           help="Enable verbose output")
    exec_group.add_argument("--quick", action="store_true",
                           help="Run quick tests with reduced duration")
    
    return parser.parse_args()


def configure_test_suite(args):
    """Configure test suite based on arguments."""
    # Apply quick mode adjustments
    if args.quick:
        args.duration = min(args.duration, 30)
        args.uptime_duration = min(args.uptime_duration, 2)
        args.users = min(args.users, 25)
    
    # Determine which tests to run
    run_integration = args.integration or args.all
    run_performance = args.performance or args.all
    run_platform = args.platform or args.all
    run_load = args.load or args.all
    run_uptime = args.uptime or args.all
    
    # If no specific tests selected, run all
    if not any([args.integration, args.performance, args.platform, args.load, args.uptime]):
        run_integration = run_performance = run_platform = run_load = run_uptime = True
    
    config = TestSuiteConfig(
        run_integration_tests=run_integration,
        run_performance_tests=run_performance,
        run_platform_tests=run_platform,
        run_load_tests=run_load,
        run_uptime_tests=run_uptime,
        load_test_users=args.users,
        load_test_duration=args.duration,
        uptime_test_duration=args.uptime_duration,
        generate_report=not args.no_report,
        save_results=not args.no_save,
        output_directory=args.output
    )
    
    return config


def print_test_plan(config):
    """Print the test execution plan."""
    print("=" * 80)
    print("VIDNET COMPREHENSIVE TEST SUITE")
    print("=" * 80)
    print("Test Execution Plan:")
    
    if config.run_integration_tests:
        print("  ✓ Integration Tests - End-to-end workflow validation")
    
    if config.run_performance_tests:
        print("  ✓ Performance Tests - Concurrent user scenarios")
    
    if config.run_platform_tests:
        print("  ✓ Platform Compatibility Tests - Real URL validation")
    
    if config.run_load_tests:
        print(f"  ✓ Load Tests - Scalability with {config.load_test_users} users for {config.load_test_duration}s")
    
    if config.run_uptime_tests:
        print(f"  ✓ Uptime Monitoring Tests - {config.uptime_test_duration} minute monitoring")
    
    print(f"\nOutput Directory: {config.output_directory}")
    print(f"Generate Report: {'Yes' if config.generate_report else 'No'}")
    print(f"Save Results: {'Yes' if config.save_results else 'No'}")
    print("=" * 80)


async def main():
    """Main entry point."""
    args = parse_arguments()
    config = configure_test_suite(args)
    
    # Print test plan
    print_test_plan(config)
    
    # Create and run test suite
    try:
        runner = ComprehensiveTestRunner(config)
        report = await runner.run_comprehensive_tests()
        
        # Print final results
        print("\n" + "=" * 80)
        print("TEST EXECUTION COMPLETED")
        print("=" * 80)
        print(f"Total Tests: {report.total_tests}")
        print(f"Passed: {report.passed_tests}")
        print(f"Failed: {report.failed_tests}")
        print(f"Success Rate: {report.success_rate:.1f}%")
        print(f"Duration: {report.duration:.1f} seconds")
        
        if report.success_rate >= 90:
            print("\n🎉 All tests passed successfully!")
            exit_code = 0
        else:
            print(f"\n⚠️  Some tests failed. Success rate: {report.success_rate:.1f}%")
            exit_code = 1
        
        # Show output files
        if config.save_results or config.generate_report:
            print(f"\nResults saved to: {config.output_directory}/")
        
        print("=" * 80)
        return exit_code
        
    except KeyboardInterrupt:
        print("\n\nTest execution interrupted by user")
        return 130
    except Exception as e:
        print(f"\n\nError during test execution: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nInterrupted")
        sys.exit(130)