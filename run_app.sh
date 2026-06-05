#!/bin/bash
echo "Starting Application Components..."

VENV_PATH="backend/venv_win"
if [ ! -d "$VENV_PATH" ]; then
    echo "Creating Windows virtual environment..."
    python -m venv "$VENV_PATH"
    echo "Installing backend requirements..."
    source "$VENV_PATH/Scripts/activate"
    pip install -r backend/requirements.txt
fi

echo "Starting Next.js Frontend..."
npm run dev &

echo "Starting FastAPI Backend..."
(cd backend && source venv_win/Scripts/activate && uvicorn main:app --reload) &

echo "Starting Celery Worker..."
(cd backend && source venv_win/Scripts/activate && celery -A tasks worker --loglevel=info --pool=solo) &

echo "All components are running in the integrated terminal. Press Ctrl+C to stop them."
wait
