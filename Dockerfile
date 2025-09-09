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

# Verify IBeam installation
RUN python3 -c "import ibeam; print('IBeam installed at:', ibeam.__file__)"

# Copy application code
COPY . .

# Make test script executable
RUN chmod +x test_ibeam.py

# Test IBeam on build
RUN python3 test_ibeam.py || true

EXPOSE 8000

# For now, run the test to see what's happening
CMD ["python3", "test_ibeam.py"]