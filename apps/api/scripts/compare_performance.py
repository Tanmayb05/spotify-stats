#!/usr/bin/env python3
"""
Performance Comparison: JSON vs Supabase PostgreSQL

This script measures the execution time for various analytics operations
using both the JSON file-based loader and the Supabase PostgreSQL loader.

Metrics measured:
- Initial data loading time
- Query execution time for common operations
- Memory usage
- Total time for full analysis workflow
"""

import time
import sys
import psutil
import os
from pathlib import Path
from typing import Dict, Any, Callable
from tabulate import tabulate

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

try:
    from app.services.data_loader import SpotifyDataLoader
    from app.services.supabase_data_loader import SupabaseDataLoader
except ImportError as e:
    print(f"Error importing loaders: {e}")
    print("Make sure both data_loader.py and supabase_data_loader.py exist")
    sys.exit(1)


class PerformanceComparator:
    """Compare performance between JSON and Supabase loaders"""

    def __init__(self):
        self.json_loader = None
        self.supabase_loader = None
        self.results = []
        self.process = psutil.Process(os.getpid())

    def get_memory_mb(self) -> float:
        """Get current memory usage in MB"""
        return self.process.memory_info().rss / 1024 / 1024

    def measure_time(self, func: Callable, name: str) -> tuple[Any, float]:
        """Measure execution time of a function"""
        start_time = time.time()
        result = func()
        end_time = time.time()
        elapsed = end_time - start_time
        return result, elapsed

    def test_json_loader(self):
        """Test JSON-based loader"""
        print("\n" + "="*70)
        print("🗂️  Testing JSON File-Based Loader")
        print("="*70)

        results_json = {}

        # Measure initial load
        print("\n1. Initial Data Load...")
        mem_before = self.get_memory_mb()
        self.json_loader = SpotifyDataLoader()

        _, load_time = self.measure_time(
            lambda: self.json_loader.load_data(),
            "Initial Load"
        )
        mem_after = self.get_memory_mb()
        mem_delta = mem_after - mem_before

        print(f"   ✓ Load time: {load_time:.2f}s")
        print(f"   ✓ Memory used: {mem_delta:.2f} MB")

        results_json['initial_load'] = {
            'time': load_time,
            'memory_mb': mem_delta
        }

        # Test common queries
        queries = [
            ('Overview Stats', lambda: self.json_loader.get_overview_stats()),
            ('Top 10 Artists', lambda: self.json_loader.get_top_artists(10)),
            ('Top 10 Tracks', lambda: self.json_loader.get_top_tracks(10)),
            ('Monthly Data', lambda: self.json_loader.get_monthly_data()),
            ('Platform Stats', lambda: self.json_loader.get_platform_stats()),
            ('Hourly Distribution', lambda: self.json_loader.get_hourly_distribution()),
            ('Daily Distribution', lambda: self.json_loader.get_daily_distribution()),
            ('Skip Behavior', lambda: self.json_loader.get_skip_behavior(20)),
            ('Yearly Comparison', lambda: self.json_loader.get_yearly_comparison()),
            ('Listening Streaks', lambda: self.json_loader.get_listening_streaks(10)),
        ]

        print("\n2. Query Performance...")
        total_query_time = 0

        for query_name, query_func in queries:
            _, query_time = self.measure_time(query_func, query_name)
            total_query_time += query_time
            results_json[query_name] = query_time
            print(f"   {query_name:.<40} {query_time:.3f}s")

        print(f"\n   Total query time: {total_query_time:.2f}s")
        print(f"   Average query time: {total_query_time/len(queries):.3f}s")

        results_json['total_query_time'] = total_query_time
        results_json['total_time'] = load_time + total_query_time

        return results_json

    def test_supabase_loader(self):
        """Test Supabase-based loader"""
        print("\n" + "="*70)
        print("🗄️  Testing Supabase PostgreSQL Loader")
        print("="*70)

        results_supabase = {}

        # Measure connection
        print("\n1. Database Connection...")
        mem_before = self.get_memory_mb()

        _, connect_time = self.measure_time(
            lambda: SupabaseDataLoader(),
            "Connect"
        )
        self.supabase_loader = SupabaseDataLoader()
        mem_after = self.get_memory_mb()
        mem_delta = mem_after - mem_before

        print(f"   ✓ Connection time: {connect_time:.3f}s")
        print(f"   ✓ Memory used: {mem_delta:.2f} MB")

        results_supabase['initial_load'] = {
            'time': connect_time,
            'memory_mb': mem_delta
        }

        # Test common queries
        queries = [
            ('Overview Stats', lambda: self.supabase_loader.get_overview_stats()),
            ('Top 10 Artists', lambda: self.supabase_loader.get_top_artists(10)),
            ('Top 10 Tracks', lambda: self.supabase_loader.get_top_tracks(10)),
            ('Monthly Data', lambda: self.supabase_loader.get_monthly_data()),
            ('Platform Stats', lambda: self.supabase_loader.get_platform_stats()),
            ('Hourly Distribution', lambda: self.supabase_loader.get_hourly_distribution()),
            ('Daily Distribution', lambda: self.supabase_loader.get_daily_distribution()),
            ('Skip Behavior', lambda: self.supabase_loader.get_skip_behavior(20)),
            ('Yearly Comparison', lambda: self.supabase_loader.get_yearly_comparison()),
            ('Listening Streaks', lambda: self.supabase_loader.get_listening_streaks(10)),
        ]

        print("\n2. Query Performance...")
        total_query_time = 0

        for query_name, query_func in queries:
            _, query_time = self.measure_time(query_func, query_name)
            total_query_time += query_time
            results_supabase[query_name] = query_time
            print(f"   {query_name:.<40} {query_time:.3f}s")

        print(f"\n   Total query time: {total_query_time:.2f}s")
        print(f"   Average query time: {total_query_time/len(queries):.3f}s")

        results_supabase['total_query_time'] = total_query_time
        results_supabase['total_time'] = connect_time + total_query_time

        return results_supabase

    def print_comparison(self, json_results: Dict, supabase_results: Dict):
        """Print detailed comparison"""
        print("\n" + "="*70)
        print("📊 PERFORMANCE COMPARISON")
        print("="*70)

        # Initial load comparison
        print("\n1. Initial Setup")
        print("-" * 70)
        table_data = [
            [
                "JSON Files",
                f"{json_results['initial_load']['time']:.2f}s",
                f"{json_results['initial_load']['memory_mb']:.2f} MB"
            ],
            [
                "Supabase",
                f"{supabase_results['initial_load']['time']:.3f}s",
                f"{supabase_results['initial_load']['memory_mb']:.2f} MB"
            ],
            [
                "Speedup",
                f"{json_results['initial_load']['time'] / supabase_results['initial_load']['time']:.1f}x",
                f"{json_results['initial_load']['memory_mb'] / max(supabase_results['initial_load']['memory_mb'], 0.01):.1f}x less"
            ]
        ]
        print(tabulate(table_data, headers=["Method", "Time", "Memory"], tablefmt="grid"))

        # Query comparison
        print("\n2. Query Performance")
        print("-" * 70)

        queries = [
            'Overview Stats',
            'Top 10 Artists',
            'Top 10 Tracks',
            'Monthly Data',
            'Platform Stats',
            'Hourly Distribution',
            'Daily Distribution',
            'Skip Behavior',
            'Yearly Comparison',
            'Listening Streaks'
        ]

        table_data = []
        for query in queries:
            json_time = json_results.get(query, 0)
            supabase_time = supabase_results.get(query, 0)
            speedup = json_time / supabase_time if supabase_time > 0 else 0

            table_data.append([
                query,
                f"{json_time:.3f}s",
                f"{supabase_time:.3f}s",
                f"{speedup:.1f}x" if speedup > 1 else f"{1/speedup:.1f}x slower"
            ])

        print(tabulate(
            table_data,
            headers=["Query", "JSON Time", "Supabase Time", "Speedup"],
            tablefmt="grid"
        ))

        # Overall summary
        print("\n3. Overall Summary")
        print("-" * 70)

        json_total = json_results['total_time']
        supabase_total = supabase_results['total_time']
        overall_speedup = json_total / supabase_total

        summary_data = [
            ["Total Execution Time", f"{json_total:.2f}s", f"{supabase_total:.2f}s"],
            ["Query Time Only", f"{json_results['total_query_time']:.2f}s", f"{supabase_results['total_query_time']:.2f}s"],
            ["Overall Speedup", "", f"{overall_speedup:.1f}x faster" if overall_speedup > 1 else f"{1/overall_speedup:.1f}x slower"],
        ]
        print(tabulate(summary_data, headers=["Metric", "JSON", "Supabase"], tablefmt="grid"))

        # Key insights
        print("\n4. Key Insights")
        print("-" * 70)
        print(f"✓ Initial setup is {json_results['initial_load']['time'] / supabase_results['initial_load']['time']:.1f}x faster with Supabase")
        print(f"✓ Memory usage is {json_results['initial_load']['memory_mb'] / max(supabase_results['initial_load']['memory_mb'], 0.01):.1f}x lower with Supabase")
        print(f"✓ Overall workflow is {overall_speedup:.1f}x faster with Supabase")

        if overall_speedup > 1:
            print(f"\n🎉 Supabase is {overall_speedup:.1f}x faster overall!")
            time_saved = json_total - supabase_total
            print(f"   Time saved: {time_saved:.2f}s ({time_saved/json_total*100:.1f}% reduction)")
        else:
            print(f"\n⚠️  JSON is {1/overall_speedup:.1f}x faster for this dataset")

        # Additional benefits
        print("\n5. Additional Supabase Benefits (Not Measured)")
        print("-" * 70)
        print("✓ Concurrent queries (multiple users)")
        print("✓ No file I/O bottlenecks")
        print("✓ Materialized views for instant aggregations")
        print("✓ Horizontal scalability")
        print("✓ Real-time data updates")
        print("✓ Advanced SQL capabilities (window functions, CTEs, etc.)")
        print("✓ Data integrity and ACID compliance")

    def run_comparison(self):
        """Run full comparison"""
        print("="*70)
        print("⚡ Spotify Stats Performance Comparison")
        print("   JSON Files vs Supabase PostgreSQL")
        print("="*70)

        try:
            # Test JSON loader
            json_results = self.test_json_loader()

            # Test Supabase loader
            try:
                supabase_results = self.test_supabase_loader()
            except Exception as e:
                print(f"\n❌ Supabase test failed: {e}")
                print("\nMake sure:")
                print("1. You've run the migration scripts")
                print("2. You've loaded data using load_json_to_supabase.py")
                print("3. Your .env has correct SUPABASE_URL and SUPABASE_SERVICE_KEY")
                return

            # Print comparison
            self.print_comparison(json_results, supabase_results)

        except KeyboardInterrupt:
            print("\n\n⚠️  Comparison interrupted by user")
            sys.exit(1)
        except Exception as e:
            print(f"\n❌ Error during comparison: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


def main():
    """Main execution"""
    # Check if required packages are installed
    try:
        import tabulate
    except ImportError:
        print("ERROR: tabulate package not installed.")
        print("Please run: pip install tabulate psutil")
        sys.exit(1)

    comparator = PerformanceComparator()
    comparator.run_comparison()


if __name__ == '__main__':
    main()
