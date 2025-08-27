FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    docker.io \
    curl \
    wget \
    libcurl4-gnutls-dev \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /workflow

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy orchestrator code
COPY . .

# Create necessary directories
RUN mkdir -p /workflow/data /workflow/workflows /workflow/logs

# Make orchestrator executable
RUN chmod +x /workflow/orchestrator.py

# Expose port
EXPOSE 8001

# Default command - run as service
CMD ["python", "orchestrator.py", "--data-dir", "/data", "--init-docker"]
