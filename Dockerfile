FROM python:3.11-slim

# Set environment variables for security and performance
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

# Set work directory
WORKDIR /app

# Install system dependencies, create user, and install Python dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        g++ \
        gcc \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean \
    && addgroup --system --gid 1001 appgroup \
    && adduser --system --uid 1001 --gid 1001 --no-create-home --disabled-password appuser

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip check

# Copy project files
COPY . .

# Set proper permissions
RUN chown -R appuser:appgroup /app \
    && chmod -R 755 /app \
    && chmod 644 /app/requirements.txt

# Switch to non-root user
USER appuser

# Expose port (Cloud Run will override with its own PORT env var)
EXPOSE 8080

# Health check with proper error handling (using default port for build time)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run the application with production settings
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT} --workers 2 --threads 4 --timeout 300 --keep-alive 5 --max-requests 1000 --max-requests-jitter 100 --preload --log-level info --access-logfile - --error-logfile - app:app"]
