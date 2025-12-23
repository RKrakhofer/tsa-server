# Multi-stage build for TSA Server
FROM python:3.12-alpine AS builder

WORKDIR /app

# Install build dependencies
RUN apk add --no-cache gcc musl-dev libffi-dev openssl-dev

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final stage
FROM python:3.12-alpine

WORKDIR /app

# Install runtime dependencies
RUN apk add --no-cache libffi openssl

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local

# Copy application code
COPY tsa/ ./tsa/
COPY client/ ./client/
COPY tools/ ./tools/
COPY pyproject.toml .

# Create directory for certificates
RUN mkdir -p /app/certs

# Make sure scripts are in PATH
ENV PATH=/root/.local/bin:$PATH

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')" || exit 1

# Run the server with Gunicorn (production WSGI server)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "tsa.server:app"]
