FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    chromium \
    chromium-driver \
    git \
    openjdk-17-jre-headless \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
RUN pip install --no-cache-dir \
    ibeam==0.5.1 \
    fastapi \
    uvicorn \
    httpx \
    pydantic

# Copy application code
COPY . .

# Make scripts executable
RUN chmod +x run_ibeam.py

# Create supervisor config
RUN echo '[supervisord]\n\
nodaemon=true\n\
logfile=/tmp/supervisord.log\n\
\n\
[program:ibeam]\n\
command=python3 /app/run_ibeam.py\n\
autostart=true\n\
autorestart=true\n\
stderr_logfile=/tmp/ibeam.err.log\n\
stdout_logfile=/tmp/ibeam.out.log\n\
environment=IBEAM_ACCOUNT="%(ENV_IBEAM_ACCOUNT)s",IBEAM_PASSWORD="%(ENV_IBEAM_PASSWORD)s"\n\
\n\
[program:fastapi]\n\
command=python3 /app/main.py\n\
autostart=true\n\
autorestart=true\n\
stderr_logfile=/tmp/fastapi.err.log\n\
stdout_logfile=/tmp/fastapi.out.log\n\
startsecs=10' > /etc/supervisor/conf.d/supervisord.conf

EXPOSE 8000 5000

# Use supervisor to run both processes
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]