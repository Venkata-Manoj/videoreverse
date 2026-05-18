#!/bin/bash
# VideoReverse Linter for Unix/Mac

echo "================================================"
echo "  VideoReverse - Linter"
echo "================================================"
echo ""

# Run linter
node scripts/lint.js

if [ $? -ne 0 ]; then
    echo ""
    echo "Lint issues found!"
    exit 1
fi

echo ""
echo "No lint issues found!"
exit 0