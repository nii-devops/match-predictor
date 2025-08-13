# Use a lightweight Python image
FROM python:3.12-slim

# Prevent Python from writing pyc files & enable stdout logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Google Cloud Run sets the PORT env variable automatically
ENV PORT=8080

# Set working directory
WORKDIR /app

# Install system dependencies for pip and gunicorn
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copy the entire project
COPY . .

# Expose the port for Cloud Run
EXPOSE 8080

# Command to run the app with Gunicorn
# Replace "app:create_app()" with your actual Flask app instance if using factory pattern
CMD exec gunicorn --bind :$PORT --workers 2 --threads 4 --timeout 0 run:app
