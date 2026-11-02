#!/usr/bin/env bash
# Usage: ./run-radient.sh [port]   (falls back to $PORT, then prompts)
port="${1:-$PORT}"
if [ -z "$port" ]; then read -r -p "Enter the port where to run the server: " port; fi
exec python run.py "$port"
