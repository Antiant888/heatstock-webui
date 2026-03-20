# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY database.py .
COPY app.py .
COPY templates/ templates/
COPY static/ static/

# Expose port (Railway will set PORT environment variable)
EXPOSE ${PORT:-8000}

# Run the application
CMD uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}
