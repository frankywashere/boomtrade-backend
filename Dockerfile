# Use the official IBeam image as base
FROM voyz/ibeam:0.5.0

# Install Python for our FastAPI app
USER root
RUN apt-get update && apt-get install -y python3 python3-pip && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install Python requirements
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy our application
COPY . .

# Script to run both IBeam and our API
RUN echo '#!/bin/bash\n\
# Start IBeam in background\n\
python3 -m ibeam.gateway_starter &\n\
IBEAM_PID=$!\n\
echo "IBeam started with PID $IBEAM_PID"\n\
# Wait a bit for IBeam to initialize\n\
sleep 5\n\
# Start our FastAPI app\n\
python3 main_with_ibeam.py\n\
' > /app/start_both.sh && chmod +x /app/start_both.sh

EXPOSE 8000 5000

CMD ["/app/start_both.sh"]