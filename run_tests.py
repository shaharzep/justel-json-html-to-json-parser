#!/usr/bin/env python3
"""Test runner script for Juportal Decisions Parser"""

import sys
import subprocess
import argparse
from pathlib import Path


def run_command(cmd):
    """Run a shell command and return the result"""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description="Run tests for Juportal Decisions Parser")
    parser.add_argument(
        "--type",
        choices=["all", "unit", "integration", "field", "text", "notices", "coverage"],
        default="all",
        help="Type of tests to run"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--failfast", "-x",
        action="store_true",
        help="Stop on first failure"
    )
    
    args = parser.parse_args()
    
    # Base pytest command
    cmd = ["python", "-m", "pytest"]
    
    if args.verbose:
        cmd.append("-v")
    
    if args.failfast:
        cmd.append("-x")
    
    # Determine which tests to run
    if args.type == "all":
        cmd.append("tests/")
    elif args.type == "unit":
        cmd.extend(["tests/unit/", "-m", "unit"])
    elif args.type == "integration":
        cmd.extend(["tests/integration/", "-m", "integration"])
    elif args.type == "field":
        cmd.append("tests/unit/test_field_extraction.py")
    elif args.type == "text":
        cmd.append("tests/unit/test_text_processing.py")
    elif args.type == "notices":
        cmd.append("tests/unit/test_notices.py")
    elif args.type == "coverage":
        cmd.extend([
            "--cov=juportal_utils",
            "--cov=src",
            "--cov-report=term-missing",
            "--cov-report=html",
            "tests/"
        ])
    
    # Run the tests
    return_code = run_command(cmd)
    
    if args.type == "coverage" and return_code == 0:
        print("\nCoverage report generated in htmlcov/index.html")
    
    return return_code


if __name__ == "__main__":
    sys.exit(main())