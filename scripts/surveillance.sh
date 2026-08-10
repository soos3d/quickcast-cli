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
    CLI=(python3 -m spectrax.cli)
fi

# Parse command line arguments
case "$1" in
    quick)
        echo "🚀 Quick start mode (deprecated alias → serve)"
        cd "$PROJECT_ROOT"
        "${CLI[@]}" quick
        ;;
    config|serve)
        echo "📋 Starting SpectraX (serve)..."
        cd "$PROJECT_ROOT"
        shift || true
        "${CLI[@]}" serve --config "$PROJECT_ROOT/config/spectrax.yml" "$@"
        ;;
    doctor)
        cd "$PROJECT_ROOT"
        "${CLI[@]}" doctor
        ;;
    custom)
        echo "⚙️  Custom serve options:"
        shift
        cd "$PROJECT_ROOT"
        "${CLI[@]}" serve "$@"
        ;;
    dashboard)
        echo "🌐 Opening surveillance dashboard..."
        open "$PROJECT_ROOT/dashboard/dashboard.html"
        ;;
    *)
        echo "Usage: ./scripts/surveillance.sh [serve|config|quick|doctor|custom|dashboard]"
        echo ""
        echo "  serve     - Start SpectraX from config/spectrax.yml (preferred)"
        echo "  config    - Alias for serve"
        echo "  quick     - Deprecated quick start"
        echo "  doctor    - Environment checks"
        echo "  custom    - serve with extra flags"
        echo "  dashboard - Standalone HTML (orphaned until Phase 4)"
        echo ""
        echo "Default: serve"
        cd "$PROJECT_ROOT"
        "${CLI[@]}" serve --config "$PROJECT_ROOT/config/spectrax.yml"
        ;;
esac
