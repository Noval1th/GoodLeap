# Multi-stage build for optimal image size and security
FROM python:3.11-slim AS builder

# Set working directory
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set working directory
WORKDIR /app

# Copy Python packages from builder stage
COPY --from=builder /root/.local /home/appuser/.local

# Copy application code and test files
COPY github_monitor.py test_github_monitor.py run_tests.sh requirements.txt ./

# Set ownership and permissions
RUN chown -R appuser:appuser /app
USER appuser

# Update PATH to include user's local bin
ENV PATH=/home/appuser/.local/bin:$PATH

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('https://api.github.com', timeout=5)" || exit 1

# Default command with help
CMD ["python", "github_monitor.py", "--help"]

# Labels for metadata
LABEL maintainer="SRE Team" \
      description="GitHub Repository Health Monitor" \
      version="1.0" \
      org.opencontainers.image.source="https://github.com/your-org/sre-tools"