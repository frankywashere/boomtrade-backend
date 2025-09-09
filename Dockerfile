FROM voyz/ibeam:latest AS ibeam

FROM python:3.11-slim

# Copy IBeam from the official image
COPY --from=ibeam /srv/ibeam /srv/ibeam

# Install dependencies
RUN apt-get update && apt-get install -y \
    openjdk-21-jre-headless \
    chromium \
    chromium-driver \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install ibeam

# Copy application code
COPY . .

# Create directories for IBeam
RUN mkdir -p /tmp/clientportal /root/ibeam

# Expose ports
EXPOSE 8000 5000

# Start script
RUN chmod +x start.sh

CMD ["./start.sh"]