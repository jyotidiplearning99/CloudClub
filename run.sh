#!/bin/bash

# Simple run script for Cloud Club Resume Parser POC

case "$1" in
  setup)
    echo " Setting up environment..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    echo " Setup complete!"
    echo " Copy .env.example to .env and add  OPENAI_API_KEY"
    ;;
  
  run)
    echo "Starting server..."
    source .venv/bin/activate
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
    ;;
  
  test)
    echo " Running tests..."
    source .venv/bin/activate
    pytest tests/ -v
    ;;
  
  *)
    echo "Usage: ./run.sh {setup|run|test}"
    echo ""
    echo "Commands:"
    echo "  setup  - Create virtual environment and install dependencies"
    echo "  run    - Start the API server"
    echo "  test   - Run tests"
    exit 1
    ;;
esac
