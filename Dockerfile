FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends chromium chromium-driver fonts-liberation \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir pipenv

WORKDIR /app
COPY Pipfile Pipfile.lock ./
RUN pipenv install --system --deploy

ENV CHROME_BIN=/usr/bin/chromium PYTHONUNBUFFERED=1 \
    CHROME_PROFILE_DIR=/data/chrome RATE_STATE_FILE=/data/ratelimit.json
COPY . .
CMD ["python", "main.py", "--worker"]
