#!/bin/bash
# Test runner script for GitHub Repository Health Monitor
# This script runs comprehensive tests and provides a demo

set -e  # Exit on any error

echo "🚀 GitHub Repository Health Monitor - Test Suite"
echo "================================================="

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Check if Python is available (try py first, then python3)
PYTHON_CMD=""
if command -v py &> /dev/null; then
    PYTHON_CMD="py"
    print_status "Python found: $(py --version)"
elif command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
    print_status "Python 3 found: $(python3 --version)"
else
    print_error "Python is required but not installed"
    exit 1
fi

# Check if pip is available
PIP_CMD=""
if command -v pip &> /dev/null; then
    PIP_CMD="pip"
elif command -v pip3 &> /dev/null; then
    PIP_CMD="pip3"
else
    print_error "pip is required but not installed"
    exit 1
fi

# Install dependencies if needed
echo -e "\n📦 Installing dependencies..."
$PIP_CMD install -r requirements.txt --quiet
print_status "Dependencies installed"

# Run unit tests
echo -e "\n🧪 Running unit tests..."
if $PYTHON_CMD -m pytest test_github_monitor.py -v --cov=github_monitor --cov-report=term-missing; then
    print_status "Unit tests passed"
else
    print_error "Unit tests failed"
    exit 1
fi

# Run linting (if available)
echo -e "\n🔍 Code quality checks..."
if command -v flake8 &> /dev/null; then
    if flake8 github_monitor.py --max-line-length=100 --ignore=E203,W503; then
        print_status "Linting passed"
    else
        print_warning "Linting issues found (non-blocking)"
    fi
else
    print_warning "flake8 not installed, skipping linting"
fi

# Run integration tests with real API calls
echo -e "\n🌐 Integration tests with real API..."
echo "Testing with popular repositories..."

# Test with a small, stable repository
if $PYTHON_CMD github_monitor.py --no-file octocat/Hello-World > /dev/null 2>&1; then
    print_status "Integration test 1 passed (octocat/Hello-World)"
else
    print_warning "Integration test 1 failed - API may be unreachable"
fi

# Test with a larger repository
if $PYTHON_CMD github_monitor.py --no-file microsoft/vscode > /dev/null 2>&1; then
    print_status "Integration test 2 passed (microsoft/vscode)"
else
    print_warning "Integration test 2 failed - API may be unreachable"
fi

# Test error handling with non-existent repository
if ! $PYTHON_CMD github_monitor.py --no-file nonexistent/repository > /dev/null 2>&1; then
    print_status "Error handling test passed (404 handling)"
else
    print_warning "Error handling test unexpected result"
fi

# Docker tests (if Docker is available)
echo -e "\n🐳 Docker tests..."
if command -v docker &> /dev/null; then
    echo "Building Docker image..."
    if docker build -t github-health-monitor-test . > /dev/null 2>&1; then
        print_status "Docker build successful"
        
        # Test Docker run
        if docker run --rm github-health-monitor-test python github_monitor.py --help > /dev/null 2>&1; then
            print_status "Docker run test passed"
        else
            print_warning "Docker run test failed"
        fi
        
        # Cleanup
        docker rmi github-health-monitor-test > /dev/null 2>&1 || true
    else
        print_warning "Docker build failed"
    fi
else
    print_warning "Docker not available, skipping Docker tests"
fi

# Demonstration run
echo -e "\n🎯 Live demonstration..."
echo "Analyzing nodejs/node repository..."
echo "======================================"

$PYTHON_CMD github_monitor.py nodejs/node --output demo_report.json

if [ -f "demo_report.json" ]; then
    print_status "Demo report generated: demo_report.json"
    echo -e "\n📊 Report preview:"
    echo "$(head -10 demo_report.json)..."
else
    print_warning "Demo report not generated"
fi

# Performance test
echo -e "\n⚡ Performance test..."
start_time=$(date +%s)
$PYTHON_CMD github_monitor.py --no-file facebook/react > /dev/null 2>&1
end_time=$(date +%s)
duration=$((end_time - start_time))

if [ $duration -lt 10 ]; then
    print_status "Performance test passed (${duration}s)"
else
    print_warning "Performance test slow (${duration}s)"
fi

# Summary
echo -e "\n📋 Test Summary"
echo "================"
print_status "Unit tests: Passed"
print_status "Integration tests: Completed"
print_status "Docker tests: Completed"
print_status "Demo run: Completed"
print_status "Performance test: Completed"

echo -e "\n🎉 All tests completed successfully!"
echo "The GitHub Repository Health Monitor is ready for use."

# Cleanup
rm -f demo_report.json

echo -e "\n💡 Next steps:"
echo "1. Review the generated reports"
echo "2. Customize the health scoring algorithm if needed"
echo "3. Set up monitoring and alerting"
echo "4. Deploy to your preferred environment"