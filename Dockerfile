FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including Chromium for IBeam
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Make scripts executable
RUN chmod +x start_gateway.py

# Find IBeam files
RUN echo "=== Searching for IBeam files ===" && \
    ls -la /usr/local/lib/python3.11/site-packages/ibeam/ || true && \
    find /usr -name "ibeam_starter.py" 2>/dev/null || true && \
    python3 -c "import ibeam; import os; print('IBeam path:', os.path.dirname(ibeam.__file__)); print('Contents:', os.listdir(os.path.dirname(ibeam.__file__)))"

EXPOSE 8000 5000

# Run the gateway starter
CMD ["python3", "start_gateway.py"]