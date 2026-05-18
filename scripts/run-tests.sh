#!/bin/bash
# VideoReverse Test Runner for Unix/Mac

echo "================================================"
echo "  VideoReverse - Test Suite (Unix/Mac)"
echo "================================================"
echo ""

# Run tests
echo "Running tests..."
node src/run_tests.js -- tests/

if [ $? -ne 0 ]; then
    echo ""
    echo "Tests failed!"
    exit 1
fi

echo ""
echo "All tests passed!"
exit 0