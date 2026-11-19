FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Non-root user
RUN addgroup --system app && adduser --system --ingroup app app

# System dependencies: espeak-ng (TTS fallback) + ffmpeg (WAV→MP3)
RUN apt-get update && apt-get install -y --no-install-recommends \
        espeak-ng \
        ffmpeg \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first for better layer caching
COPY requirements.txt .
RUN pip install -r requirements.txt

# Download default Piper voice model into /app/voices
# -f makes curl fail (non-zero exit) on HTTP errors so the build breaks visibly.
RUN mkdir -p /app/voices && \
    curl -fsSL -o /app/voices/en_US-lessac-medium.onnx \
        "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx" && \
    curl -fsSL -o /app/voices/en_US-lessac-medium.onnx.json \
        "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"

# Application code
COPY . .

# Writable dirs owned by the app user (tts_cache is NOT under storage)
RUN mkdir -p /app/storage /app/tts_cache && chown -R app:app /app

USER app

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)" || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--no-server-header"]
