FROM python:3.11-slim

# Force HTTPS mirrors to bypass ISP HTTP redirect issues
RUN echo 'Acquire::http::Pipeline-Depth "0";' > /etc/apt/apt.conf.d/99fixbadproxy && \
    echo 'Acquire::Retries "5";' >> /etc/apt/apt.conf.d/99fixbadproxy && \
    sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/*.sources 2>/dev/null || true && \
    sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list 2>/dev/null || true

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --default-timeout=1000 --retries 10 -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8009

# Entrypoint
RUN chmod +x docker-entrypoint.sh
ENTRYPOINT ["/bin/bash", "docker-entrypoint.sh"]
