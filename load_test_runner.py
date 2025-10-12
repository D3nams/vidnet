#!/usr/bin/env python3
"""
Standalone load test runner for VidNet API.

This script runs comprehensive load tests to verify rate limiting and performance
optimization features work correctly under high concurrent load.
"""

import asyncio
import time
import logging
import json
import argparse
from pathlib import Path
import httpx
from typing import Dict, Any, List


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class LoadTestRunner:
    """Comprehensive load test runner for VidNet API."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results = {
            'test_config': {},
            'test_results': [],
            'summary': {}
        }
    
    async def run_concurrent_load_test(self, concurrent_users: int = 100, 
                                     duration: int = 60) -> Dict[str, Any]:
        """
        Run concurrent load test with specified parameters.
        
        Args:
            concurrent_users: Number of concurrent users to simulate
            duration: Test duration in seconds
            
        Returns:
            Dict with test results
        """
        logger.info(f"Starting concurrent load test: {concurrent_users} users, {duration}s duration")
        
        # Test configuration
        test_config = {
            'concurrent_users': concurrent_users,
            'duration': duration,
            'start_time': time.time()
        }
        
        # Create semaphore to limit concurrent connections
        semaphore = asyncio.Semaphore(concurrent_users)
        
        # Results collection
        results = []
        
        async def simulate_user(user_id: int):
            """Simulate a single user's behavior."""
            async with semaphore:
                async with httpx.AsyncClient(base_url=self.base_url, timeout=30.0) as client:
                    end_time = time.time() + duration
                    user_results = []
                    
                    while time.time() < end_time:
                        try:
                            # Test different endpoints
                            test_scenarios = [
                                ('metadata', self._test_metadata),
                                ('download', self._test_download),
                                ('health', self._test_health),
                                ('monitoring', self._test_monitoring)
                            ]
                            
                            for scenario_name, test_func in test_scenarios:
                                start_time = time.time()
                                status_code, response_data = await test_func(client)
                                response_time = time.time() - start_time
                                
                                user_results.append({
                                    'user_id': user_id,
                                    'scenario': scenario_name,
                                    'status_code': status_code,
                                    'response_time': response_time,
                                    'success': status_code < 500,
                                    'timestamp': start_time
                                })
                                
                                # Small delay between requests
                                await asyncio.sleep(0.1)
                            
                            # Delay between test cycles
                            await asyncio.sleep(1.0)
                            
                        except Exception as e:
                            logger.error(f"User {user_id} error: {e}")
                            user_results.append({
                                'user_id': user_id,
                                'scenario': 'error',
                                'status_code': 500,
                                'response_time': 0,
                                'success': False,
                                'error': str(e),
                                'timestamp': time.time()
                            })
                            await asyncio.sleep(1.0)
                    
                    return user_results
        
        # Run all users concurrently
        tasks = [simulate_user(i) for i in range(concurrent_users)]
        user_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Flatten results
        for user_result in user_results:
            if isinstance(user_result, list):
                results.extend(user_result)
            else:
                logger.error(f"User task failed: {user_result}")
        
        # Calculate summary statistics
        summary = self._calculate_summary(results, test_config)
        
        return {
            'test_config': test_config,
            'results': results,
            'summary': summary
        }
    
    async def _test_metadata(self, client: httpx.AsyncClient) -> tuple[int, Dict[str, Any]]:
        """Test metadata endpoint."""
        try:
            response = await client.post(
                "/api/v1/metadata",
                json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}
            )
            return response.status_code, response.json() if response.content else {}
        except Exception as e:
            return 500, {"error": str(e)}
    
    async def _test_download(self, client: httpx.AsyncClient) -> tuple[int, Dict[str, Any]]:
        """Test download endpoint."""
        try:
            response = await client.post(
                "/api/v1/download",
                json={
                    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                    "quality": "720p",
                    "format": "video"
                }
            )
            return response.status_code, response.json() if response.content else {}
        except Exception as e:
            return 500, {"error": str(e)}
    
    async def _test_health(self, client: httpx.AsyncClient) -> tuple[int, Dict[str, Any]]:
        """Test health endpoint."""
        try:
            response = await client.get("/api/v1/monitoring/health")
            return response.status_code, response.json() if response.content else {}
        except Exception as e:
            return 500, {"error": str(e)}
    
    async def _test_monitoring(self, client: httpx.AsyncClient) -> tuple[int, Dict[str, Any]]:
        """Test monitoring endpoints."""
        try:
            response = await client.get("/api/v1/monitoring/metrics")
            return response.status_code, response.json() if response.content else {}
        except Exception as e:
            return 500, {"error": str(e)}
    
    def _calculate_summary(self, results: List[Dict[str, Any]], 
                          test_config: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate test summary statistics."""
        if not results:
            return {"error": "No results to analyze"}
        
        # Basic statistics
        total_requests = len(results)
        successful_requests = sum(1 for r in results if r['success'])
        failed_requests = total_requests - successful_requests
        
        # Response time statistics
        response_times = [r['response_time'] for r in results if r['response_time'] > 0]
        response_times.sort()
        
        # Status code distribution
        status_codes = {}
        for result in results:
            code = result['status_code']
            status_codes[code] = status_codes.get(code, 0) + 1
        
        # Scenario performance
        scenarios = {}
        for result in results:
            scenario = result['scenario']
            if scenario not in scenarios:
                scenarios[scenario] = {
                    'total_requests': 0,
                    'successful_requests': 0,
                    'response_times': []
                }
            
            scenarios[scenario]['total_requests'] += 1
            if result['success']:
                scenarios[scenario]['successful_requests'] += 1
            if result['response_time'] > 0:
                scenarios[scenario]['response_times'].append(result['response_time'])
        
        # Calculate scenario statistics
        for scenario_name, scenario_data in scenarios.items():
            times = scenario_data['response_times']
            if times:
                times.sort()
                scenario_data['avg_response_time'] = sum(times) / len(times)
                scenario_data['min_response_time'] = min(times)
                scenario_data['max_response_time'] = max(times)
                scenario_data['p95_response_time'] = times[int(len(times) * 0.95)] if times else 0
            else:
                scenario_data['avg_response_time'] = 0
                scenario_data['min_response_time'] = 0
                scenario_data['max_response_time'] = 0
                scenario_data['p95_response_time'] = 0
            
            scenario_data['success_rate'] = (scenario_data['successful_requests'] / scenario_data['total_requests']) * 100
        
        # Overall summary
        test_duration = time.time() - test_config['start_time']
        
        summary = {
            'test_duration': test_duration,
            'total_requests': total_requests,
            'successful_requests': successful_requests,
            'failed_requests': failed_requests,
            'success_rate': (successful_requests / total_requests) * 100,
            'requests_per_second': total_requests / test_duration if test_duration > 0 else 0,
            'status_codes': status_codes,
            'scenarios': scenarios
        }
        
        if response_times:
            summary.update({
                'avg_response_time': sum(response_times) / len(response_times),
                'min_response_time': min(response_times),
                'max_response_time': max(response_times),
                'p50_response_time': response_times[int(len(response_times) * 0.5)],
                'p95_response_time': response_times[int(len(response_times) * 0.95)],
                'p99_response_time': response_times[int(len(response_times) * 0.99)]
            })
        
        return summary
    
    async def run_rate_limit_test(self) -> Dict[str, Any]:
        """Test rate limiting functionality."""
        logger.info("Running rate limit test")
        
        async with httpx.AsyncClient(base_url=self.base_url, timeout=30.0) as client:
            results = []
            
            # Make rapid requests to trigger rate limiting
            for i in range(80):  # Exceed rate limit
                start_time = time.time()
                try:
                    response = await client.post(
                        "/api/v1/metadata",
                        json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}
                    )
                    response_time = time.time() - start_time
                    
                    results.append({
                        'request_number': i + 1,
                        'status_code': response.status_code,
                        'response_time': response_time,
                        'rate_limited': response.status_code == 429,
                        'headers': dict(response.headers)
                    })
                    
                except Exception as e:
                    results.append({
                        'request_number': i + 1,
                        'status_code': 500,
                        'response_time': time.time() - start_time,
                        'rate_limited': False,
                        'error': str(e)
                    })
                
                # Small delay to avoid overwhelming
                await asyncio.sleep(0.05)
        
        # Analyze rate limiting
        rate_limited_count = sum(1 for r in results if r.get('rate_limited', False))
        successful_count = sum(1 for r in results if r['status_code'] == 200)
        
        return {
            'total_requests': len(results),
            'rate_limited_requests': rate_limited_count,
            'successful_requests': successful_count,
            'rate_limit_effectiveness': (rate_limited_count / len(results)) * 100,
            'results': results
        }
    
    def save_results(self, results: Dict[str, Any], filename: str = None):
        """Save test results to JSON file."""
        if filename is None:
            timestamp = int(time.time())
            filename = f"load_test_results_{timestamp}.json"
        
        filepath = Path("logs") / filename
        filepath.parent.mkdir(exist_ok=True)
        
        with open(filepath, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        logger.info(f"Results saved to {filepath}")
    
    def print_summary(self, results: Dict[str, Any]):
        """Print test results summary."""
        summary = results.get('summary', {})
        
        print("\n" + "="*60)
        print("LOAD TEST RESULTS SUMMARY")
        print("="*60)
        
        if 'error' in summary:
            print(f"❌ Test failed: {summary['error']}")
            return
        
        # Overall statistics
        print(f"Test Duration: {summary.get('test_duration', 0):.2f} seconds")
        print(f"Total Requests: {summary.get('total_requests', 0)}")
        print(f"Successful Requests: {summary.get('successful_requests', 0)}")
        print(f"Failed Requests: {summary.get('failed_requests', 0)}")
        print(f"Success Rate: {summary.get('success_rate', 0):.2f}%")
        print(f"Requests/Second: {summary.get('requests_per_second', 0):.2f}")
        
        # Response time statistics
        if 'avg_response_time' in summary:
            print(f"\nResponse Time Statistics:")
            print(f"  Average: {summary['avg_response_time']:.3f}s")
            print(f"  Minimum: {summary['min_response_time']:.3f}s")
            print(f"  Maximum: {summary['max_response_time']:.3f}s")
            print(f"  P95: {summary['p95_response_time']:.3f}s")
            print(f"  P99: {summary['p99_response_time']:.3f}s")
        
        # Status code distribution
        status_codes = summary.get('status_codes', {})
        if status_codes:
            print(f"\nStatus Code Distribution:")
            for code, count in sorted(status_codes.items()):
                print(f"  {code}: {count} requests")
        
        # Scenario performance
        scenarios = summary.get('scenarios', {})
        if scenarios:
            print(f"\nScenario Performance:")
            for scenario_name, scenario_data in scenarios.items():
                print(f"  {scenario_name}:")
                print(f"    Requests: {scenario_data['total_requests']}")
                print(f"    Success Rate: {scenario_data['success_rate']:.2f}%")
                print(f"    Avg Response Time: {scenario_data['avg_response_time']:.3f}s")
        
        # Performance assessment
        print(f"\nPerformance Assessment:")
        success_rate = summary.get('success_rate', 0)
        avg_response_time = summary.get('avg_response_time', 0)
        p95_response_time = summary.get('p95_response_time', 0)
        
        if success_rate >= 90:
            print("✅ Success Rate: EXCELLENT (≥90%)")
        elif success_rate >= 80:
            print("⚠️  Success Rate: GOOD (≥80%)")
        else:
            print("❌ Success Rate: POOR (<80%)")
        
        if avg_response_time <= 3.0:
            print("✅ Average Response Time: EXCELLENT (≤3s)")
        elif avg_response_time <= 5.0:
            print("⚠️  Average Response Time: ACCEPTABLE (≤5s)")
        else:
            print("❌ Average Response Time: POOR (>5s)")
        
        if p95_response_time <= 10.0:
            print("✅ P95 Response Time: ACCEPTABLE (≤10s)")
        else:
            print("❌ P95 Response Time: POOR (>10s)")
        
        # Rate limiting check
        if 429 in status_codes:
            print("✅ Rate Limiting: WORKING (429 responses detected)")
        else:
            print("⚠️  Rate Limiting: NOT DETECTED (no 429 responses)")


async def main():
    """Main function to run load tests."""
    parser = argparse.ArgumentParser(description="VidNet API Load Test Runner")
    parser.add_argument("--url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--users", type=int, default=100, help="Number of concurrent users")
    parser.add_argument("--duration", type=int, default=60, help="Test duration in seconds")
    parser.add_argument("--rate-limit-test", action="store_true", help="Run rate limit test")
    parser.add_argument("--save-results", action="store_true", help="Save results to file")
    
    args = parser.parse_args()
    
    runner = LoadTestRunner(args.url)
    
    try:
        if args.rate_limit_test:
            # Run rate limit test
            logger.info("Running rate limit test...")
            rate_limit_results = await runner.run_rate_limit_test()
            
            print("\n" + "="*60)
            print("RATE LIMIT TEST RESULTS")
            print("="*60)
            print(f"Total Requests: {rate_limit_results['total_requests']}")
            print(f"Rate Limited: {rate_limit_results['rate_limited_requests']}")
            print(f"Successful: {rate_limit_results['successful_requests']}")
            print(f"Rate Limit Effectiveness: {rate_limit_results['rate_limit_effectiveness']:.2f}%")
            
            if args.save_results:
                runner.save_results(rate_limit_results, "rate_limit_test_results.json")
        
        else:
            # Run concurrent load test
            logger.info(f"Running concurrent load test with {args.users} users for {args.duration} seconds...")
            results = await runner.run_concurrent_load_test(args.users, args.duration)
            
            # Print summary
            runner.print_summary(results)
            
            # Save results if requested
            if args.save_results:
                runner.save_results(results)
    
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())