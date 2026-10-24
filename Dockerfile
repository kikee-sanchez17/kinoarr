FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# ffmpeg ships ffprobe, needed to detect embedded subtitles
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# alass re-times downloaded subtitles to the movie's audio; the checksum makes the build fail if the file changes
ARG ALASS_URL=https://github.com/kaegi/alass/releases/download/v2.0.0/alass-linux64
ARG ALASS_SHA256=7bd0b9ae7e035d3ba940eacffb21243614df36231d47f21f0b4ce42001ab7fcd
ADD ${ALASS_URL} /usr/local/bin/alass
# Checked in a RUN step: the legacy builder ignores ADD --checksum
RUN echo "${ALASS_SHA256}  /usr/local/bin/alass" | sha256sum --check --quiet - \
    && chmod 0755 /usr/local/bin/alass

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')" || exit 1

# A single worker to save RAM
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
