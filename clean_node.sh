#!/bin/bash

# Delete all node_modules folders and package-lock.json files recursively

echo "Searching for node_modules folders and package-lock.json files..."

# Delete node_modules directories
find . -name "node_modules" -type d -prune -print -exec rm -rf {} \;

# Delete package-lock.json files
find . -name "package-lock.json" -type f -print -delete

echo "Done."
