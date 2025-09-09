FROM python:3.11-slim

# Install Java for IBeam
RUN apt-get update && apt-get install -y \
    openjdk-21-jre-headless \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download and setup IBeam
RUN pip install ibeam

# Copy application code
COPY . .

# Expose ports
EXPOSE 8000 5000

# Start both IBeam and FastAPI
CMD ["python", "main.py"]