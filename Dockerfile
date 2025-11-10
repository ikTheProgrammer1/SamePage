# Cloud Run container for SamePage
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates git && \
    rm -rf /var/lib/apt/lists/*

# Copy minimal files first for better layer caching
COPY pyproject.toml /app/

# Install deps directly (hackathon-friendly). For reproducibility, pin later.
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
      fastapi==0.115.0 \
      uvicorn==0.30.6 \
      jinja2==3.1.4 \
      google-cloud-firestore==2.16.0 \
      google-cloud-aiplatform==1.66.0 \
      python-multipart==0.0.9

# Prevent legacy 'google' stub package from blocking namespace imports and
# ensure ADK is importable at build time (fail-fast if not).
RUN pip uninstall -y google || true
RUN pip install --no-cache-dir git+https://github.com/google/adk-python.git@main
RUN python -c "import google, google.adk; import sys; print('ADK import OK; google locations:', getattr(__import__('google').__spec__, 'submodule_search_locations', []))"

# Copy app
COPY . /app

# Non-root user (optional)
RUN useradd -m appuser && chown -R appuser /app
USER appuser

ENV PORT=8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
