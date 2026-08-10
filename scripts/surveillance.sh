#!/bin/bash

# SpectraX Surveillance System Launcher
# Simple script to start your surveillance system

echo "🎥 SpectraX Surveillance System"
echo "==============================="
echo ""

# Set the project root directory (parent of scripts/)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Check if MediaMTX is installed
if ! command -v mediamtx &> /dev/null; then
    echo "❌ MediaMTX is not installed!"
    echo "Please install it first: brew install mediamtx"
    exit 1
fi

# Activate virtual environment if it exists
if [ -d "$PROJECT_ROOT/venv" ]; then
    echo "Activating virtual environment..."
    source "$PROJECT_ROOT/venv/bin/activate"
elif [ -d "$PROJECT_ROOT/.venv" ]; then
    echo "Activating virtual environment..."
    source "$PROJECT_ROOT/.venv/bin/activate"
fi

# Prefer the installed console script; fall back to python -m
if command -v spectrax &> /dev/null; then
    CLI=(spectrax)
elif command -v surveillance &> /dev/null; then
    CLI=(surveillance)
else
    CLI=(python3 -m spectrax.surveillance)
fi

# Parse command line arguments
case "$1" in
    quick)
        echo "🚀 Quick start mode (1 camera, with detection)"
        cd "$PROJECT_ROOT"
        "${CLI[@]}" quick
        ;;
    config)
        echo "📋 Starting with configuration file..."
        cd "$PROJECT_ROOT"
        "${CLI[@]}" config
        ;;
    custom)
        echo "⚙️  Custom mode - specify your options:"
        shift
        cd "$PROJECT_ROOT"
        "${CLI[@]}" start "$@"
        ;;
    dashboard)
        echo "🌐 Opening surveillance dashboard..."
        open "$PROJECT_ROOT/dashboard/dashboard.html"
        ;;
    *)
        echo "Usage: ./scripts/surveillance.sh [quick|config|custom|dashboard]"
        echo ""
        echo "  quick     - Quick start with 1 camera and object detection"
        echo "  config    - Start using config/spectrax.yml"
        echo "  custom    - Start with custom command line options"
        echo "  dashboard - Open the standalone web dashboard (orphaned until Phase 4)"
        echo ""
        echo "Default: Starting with configuration file..."
        cd "$PROJECT_ROOT"
        "${CLI[@]}" config
        ;;
esac
