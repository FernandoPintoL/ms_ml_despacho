# Multi-stage Dockerfile for HADS ML Service
# Stage 1: Builder
FROM python:3.11-slim as builder

LABEL maintainer="HADS Team"
LABEL description="HADS ML Microservice - Hospital Ambulance Dispatch System"

# Set working directory
WORKDIR /app

# Install system dependencies for building
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies in a virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

LABEL stage=production

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    FLASK_ENV=production

# Install runtime dependencies (incluye soporte para SQL Server)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    gnupg2 \
    ca-certificates \
    apt-transport-https \
    && rm -rf /var/lib/apt/lists/*

# Instalar Microsoft ODBC Driver for SQL Server (para conexión a SQL Server)
# Usando el método moderno sin apt-key (compatible con Debian 12+)
RUN apt-get update && \
    curl https://packages.microsoft.com/keys/microsoft.asc -o /tmp/microsoft.asc && \
    gpg --dearmor -o /usr/share/keyrings/microsoft-archive-keyring.gpg /tmp/microsoft.asc && \
    echo "deb [signed-by=/usr/share/keyrings/microsoft-archive-keyring.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" > /etc/apt/sources.list.d/mssql-release.list && \
    apt-get update && \
    ACCEPT_EULA=Y apt-get install -y --no-install-recommends \
    msodbcsql17 \
    && rm -rf /var/lib/apt/lists/* /tmp/microsoft.asc

# Create non-root user
RUN useradd -m -u 1000 appuser

# Set working directory
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY --chown=appuser:appuser . .

# Create logs directory
RUN mkdir -p /app/src/logs && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Expose port
EXPOSE 5000

# Run application with Gunicorn
CMD ["gunicorn", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "4", \
     "--worker-class", "sync", \
     "--timeout", "60", \
     "--max-requests", "1000", \
     "--max-requests-jitter", "50", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--log-level", "info", \
     "src.main:create_app()"]
