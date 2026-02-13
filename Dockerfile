FROM python:3.12-slim

# Install system dependencies needed for numpy and other packages
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# First copy only requirements to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Then copy the rest of the application
COPY . .

# Make sure the app is accessible
RUN ls -la && \
    echo "Checking if app.py exists:" && \
    ls -la app.py || echo "app.py not found!"

# Use the PORT environment variable that Koyeb provides
EXPOSE 8000

# Run with proper logging
CMD gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 --log-level debug app:app
