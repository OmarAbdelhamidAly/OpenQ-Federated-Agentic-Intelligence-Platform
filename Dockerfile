# ── Stage 1: Build stage ──────────────────────────────────────
FROM python:3.11-slim AS builder

# Force HTTPS mirrors to bypass ISP HTTP redirect issues
RUN echo 'Acquire::http::Pipeline-Depth "0";' > /etc/apt/apt.conf.d/99fixbadproxy && \
    echo 'Acquire::Retries "5";' >> /etc/apt/apt.conf.d/99fixbadproxy && \
    sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/*.sources 2>/dev/null || true && \
    sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list 2>/dev/null || true

# System deps for WeasyPrint (PDF export) and PostgreSQL client
RUN apt-get update && apt-get install -y --no-install-recommends --fix-missing \
    build-essential \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    libpq-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: Runtime ──────────────────────────────────────────
FROM python:3.11-slim

# Force HTTPS mirrors to bypass ISP HTTP redirect issues
RUN echo 'Acquire::http::Pipeline-Depth "0";' > /etc/apt/apt.conf.d/99fixbadproxy && \
    echo 'Acquire::Retries "5";' >> /etc/apt/apt.conf.d/99fixbadproxy && \
    sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/*.sources 2>/dev/null || true && \
    sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list 2>/dev/null || true

# Runtime system deps
RUN apt-get update && apt-get install -y --no-install-recommends --fix-missing \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libpq5 \
    shared-mime-info \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app
ENV PYTHONPATH=/app

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

# Copy and set up entrypoint
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Create directories for tenant uploads
RUN mkdir -p /tmp/tenants && chown -R appuser:appuser /tmp/tenants
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--timeout-keep-alive", "300"]
