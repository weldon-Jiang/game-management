#!/bin/bash
# Bend Agent Startup Script

cd "$(dirname "$0")/src"

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    exit 1
fi

# Check if dependencies are installed
if ! python3 -c "import aiohttp" 2>/dev/null; then
    echo "Installing dependencies..."
    pip install -r ../requirements.txt
fi

# Run the agent
python3 main.py "$@"
