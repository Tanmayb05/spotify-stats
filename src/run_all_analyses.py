"""
Master Script - Run All Analyses
Executes all analysis scripts in sequence
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime

def run_script(script_name):
    """Run a Python script and handle output"""
    print("\n" + "="*80)
    print(f"Running {script_name}...")
    print("="*80)

    try:
        result = subprocess.run(
            [sys.executable, script_name],
            capture_output=True,
            text=True,
            check=True
        )
        print(result.stdout)
        if result.stderr:
            print("Warnings/Errors:", result.stderr)
        return True
    except subprocess.CalledProcessError as e:
        print(f"ERROR running {script_name}:")
        print(e.stdout)
        print(e.stderr)
        return False
    except Exception as e:
        print(f"UNEXPECTED ERROR: {e}")
        return False

def main():
    print("="*80)
    print("SPOTIFY STREAMING HISTORY - COMPLETE ANALYSIS SUITE")
    print("="*80)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    scripts = [
        'explore_data.py',
        'listening_patterns.py',
        'artist_discovery.py',
        'detailed_stats.py',
        'advanced_visualizations.py',
        'google_charts_viz.py',
        'google_charts_advanced.py'
    ]

    results = {}
    start_time = datetime.now()

    for script in scripts:
        script_path = Path.cwd().joinpath('src').joinpath(script)
        if script_path.exists():
            success = run_script(script_path)
            results[script] = "✓ SUCCESS" if success else "✗ FAILED"
        else:
            results[script] = "✗ NOT FOUND"
            print(f"WARNING: {script_path} not found, skipping...")

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    # Summary
    print("\n" + "="*80)
    print("ANALYSIS SUITE SUMMARY")
    print("="*80)

    for script, status in results.items():
        print(f"  {script:<30} {status}")

    print(f"\nTotal execution time: {duration:.1f} seconds")
    print(f"Completed at: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Check outputs directory
    output_dir = Path('..').resolve().joinpath('outputs')
    if output_dir.exists():
        files = list(output_dir.glob('*'))
        print(f"\nGenerated {len(files)} files in outputs/ directory:")

        # Count by type
        png_files = list(output_dir.glob('*.png'))
        csv_files = list(output_dir.glob('*.csv'))
        html_files = list(output_dir.glob('*.html'))

        print(f"  - {len(png_files)} visualization images (.png)")
        print(f"  - {len(csv_files)} data files (.csv)")
        print(f"  - {len(html_files)} dashboard visualization html (.html)")

    print("\n" + "="*80)
    print("ALL ANALYSES COMPLETE!")
    print("="*80)

if __name__ == "__main__":
    main()
