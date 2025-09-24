# Multi-stage Dockerfile optimized for Apple Silicon (ARM64) and Intel (AMD64)
FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd --create-home --shell /bin/bash trader
USER trader
WORKDIR /home/trader

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/home/trader/.local/bin:$PATH"

# Copy dependency files
COPY --chown=trader:trader pyproject.toml poetry.lock* requirements.txt ./

# Install dependencies
RUN pip install --user -r requirements.txt

# Production stage
FROM base as production

# Copy application code
COPY --chown=trader:trader . .

# Create necessary directories
RUN mkdir -p logs reports data/sample notebooks

# Set Python path
ENV PYTHONPATH=/home/trader:$PYTHONPATH

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD python -c "from src.config import config; print('Health check passed')"

# Default command
CMD ["python", "-m", "src.cli", "--help"]

# Development stage
FROM production as development

# Install development dependencies
RUN pip install --user pytest pytest-cov black isort flake8 mypy pre-commit

# Install Jupyter for development
RUN pip install --user jupyter notebook ipykernel

# Expose Jupyter port
EXPOSE 8888

# Development command
CMD ["jupyter", "notebook", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--allow-root"]