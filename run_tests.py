#!/usr/bin/env python3
"""
Test runner script for the Zendesk Voice Server.

This script sets up the environment and runs all tests with proper coverage reporting.
"""

import os
import sys
import subprocess
import unittest
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def run_tests():
    """Run all tests and generate coverage report."""
    print("🧪 Running Zendesk Voice Server Tests")
    print("=" * 50)
    
    # Check if coverage is installed
    try:
        import coverage
        use_coverage = True
        print("✅ Coverage module found - will generate coverage report")
    except ImportError:
        use_coverage = False
        print("⚠️  Coverage module not found - install with: pip install coverage")
    
    # Set up coverage if available
    if use_coverage:
        cov = coverage.Coverage(
            source=['src'],
            omit=[
                '*/tests/*',
                '*/venv/*',
                '*/__pycache__/*'
            ]
        )
        cov.start()
    
    # Discover and run tests
    loader = unittest.TestLoader()
    start_dir = os.path.join(os.path.dirname(__file__), 'tests')
    suite = loader.discover(start_dir, pattern='test_*.py')
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Generate coverage report if available
    if use_coverage:
        cov.stop()
        cov.save()
        
        print("\n📊 Coverage Report")
        print("=" * 30)
        cov.report()
        
        # Generate HTML coverage report
        cov.html_report(directory='htmlcov')
        print(f"\n📁 HTML coverage report generated in: htmlcov/index.html")
    
    # Return exit code
    return 0 if result.wasSuccessful() else 1

def run_specific_test(test_file):
    """Run a specific test file."""
    print(f"🧪 Running specific test: {test_file}")
    print("=" * 50)
    
    test_path = os.path.join(os.path.dirname(__file__), 'tests', test_file)
    if not os.path.exists(test_path):
        print(f"❌ Test file not found: {test_path}")
        return 1
    
    # Run the specific test
    result = subprocess.run([
        sys.executable, '-m', 'unittest', test_path
    ], cwd=os.path.dirname(__file__))
    
    return result.returncode

def main():
    """Main function to handle command line arguments."""
    if len(sys.argv) > 1:
        # Run specific test file
        test_file = sys.argv[1]
        if not test_file.endswith('.py'):
            test_file += '.py'
        exit_code = run_specific_test(test_file)
    else:
        # Run all tests
        exit_code = run_tests()
    
    print(f"\n{'✅ Tests passed' if exit_code == 0 else '❌ Tests failed'}")
    sys.exit(exit_code)

if __name__ == '__main__':
    main() 