#!/usr/bin/env python3
"""
Test runner script for the Zendesk Voice Server.

This script sets up the environment and runs all tests with proper coverage reporting.
"""

import os
import sys
import subprocess
import re
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
        print("\n📁 HTML coverage report generated in: htmlcov/index.html")
    
    # Return exit code
    return 0 if result.wasSuccessful() else 1

def run_specific_test(test_file):
    """Run a specific test file with strict security validation."""
    # Comprehensive input validation and sanitization to prevent path traversal
    if not test_file or not isinstance(test_file, str):
        print("❌ Invalid test file input")
        return 1
    
    # Remove any path components to prevent directory traversal
    test_file = os.path.basename(test_file)
    
    # Strict whitelist validation - only allow alphanumeric, underscore, dot
    if not re.match(r'^[a-zA-Z0-9_\.]+$', test_file):
        print(f"❌ Invalid test file name format: {test_file}")
        return 1
    
    # Must follow test file naming convention
    if not test_file.startswith('test_') or not test_file.endswith('.py'):
        print(f"❌ Test file must start with 'test_' and end with '.py': {test_file}")
        return 1
    
    print(f"🧪 Running specific test: {test_file}")
    print("=" * 50)
    
    # Construct and validate the full path
    tests_dir = os.path.join(os.path.dirname(__file__), 'tests')
    tests_dir = os.path.abspath(tests_dir)  # Get absolute path
    test_path = os.path.join(tests_dir, test_file)
    test_path = os.path.abspath(test_path)  # Get absolute path
    
    # Ensure the test file is within the tests directory (prevent path traversal)
    if not test_path.startswith(tests_dir + os.sep):
        print(f"❌ Test file must be in tests directory: {test_file}")
        return 1
    
    # Verify file exists
    if not os.path.exists(test_path):
        print(f"❌ Test file not found: {test_path}")
        return 1
    
    # Run the specific test with safe arguments - no shell injection possible
    try:
        result = subprocess.run([
            sys.executable, '-m', 'unittest', f'tests.{test_file[:-3]}'  # Use module path instead of file path
        ], cwd=os.path.dirname(__file__), timeout=300, shell=False, capture_output=False)  # Explicitly disable shell
        
        return result.returncode
    except subprocess.TimeoutExpired:
        print("❌ Test execution timed out")
        return 1
    except Exception as e:
        print(f"❌ Error running test: {e}")
        return 1

def main():
    """Main function to handle command line arguments."""
    if len(sys.argv) > 1:
        # Run specific test file - sanitize input
        test_file = sys.argv[1].strip()
        
        # Basic validation - only allow safe characters
        if not test_file or '..' in test_file or '/' in test_file or '\\' in test_file:
            print("❌ Invalid test file name")
            sys.exit(1)
            
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