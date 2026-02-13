FROM python:3.12-slim

# Install minimal build tools
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

# Install dependencies - numpy 1.26.4 udah pre-compiled untuk 3.12!
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app
