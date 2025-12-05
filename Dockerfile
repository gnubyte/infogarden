FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0 \
    libffi-dev \
    shared-mime-info \
    zbar-tools \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p app/static/uploads app/backups

EXPOSE 5000

# Environment variables can be set at runtime:
# - DATABASE_URL: Full database connection string (optional)
# - DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME: Individual DB components
# - SECRET_KEY: Flask secret key (required)
# - ENCRYPTION_KEY: Encryption key for password storage (required)
# - FLASK_ENV: Flask environment (development/production)
# - FLASK_PORT: Port for the web service (default: 5000)
# - GUNICORN_WORKERS: Number of worker processes (default: CPU count * 2 + 1)
# - LOG_LEVEL: Logging level (default: info)
# - BACKUP_*: Backup configuration variables

# Use gunicorn for production WSGI server
# Create a WSGI entry point
CMD ["gunicorn", "--config", "gunicorn_config.py", "wsgi:app"]

