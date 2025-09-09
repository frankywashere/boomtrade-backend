# Use official IBeam image directly
FROM voyz/ibeam:latest

# Install Python and our app dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Environment variables for IBeam
ENV IBEAM_GATEWAY_DIR=/srv/clientportal.gw
ENV IBEAM_LOG_LEVEL=INFO
ENV IBEAM_MAINTENANCE_INTERVAL=86400
ENV IBEAM_SPAWN_NEW_PROCESSES=false

# Expose ports
EXPOSE 8000 5000

# Start both IBeam and our FastAPI
CMD python3 main.py