# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Non-root user (uid 1000 to match the run script)
RUN useradd -m -u 1000 appuser

WORKDIR /home/appuser/app

# (Optional) tini for proper signal handling
RUN apt-get update && apt-get install -y --no-install-recommends tini \
  && rm -rf /var/lib/apt/lists/*

# Runtime deps
RUN pip install --no-cache-dir fastapi==0.115.* uvicorn[standard]==0.30.* redis==5.0.*

# Copy your app
COPY --chown=appuser:appuser app.py .
COPY --chown=appuser:appuser favicon.ico .

USER appuser
EXPOSE 8000

ENTRYPOINT ["/usr/bin/tini","--"]
CMD ["uvicorn","app:app","--host","0.0.0.0","--port","8000"]

