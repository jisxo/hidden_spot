FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY apps/worker/requirements.txt /tmp/requirements.txt
RUN apt-get update \
  && apt-get install -y --no-install-recommends curl ca-certificates \
  && rm -rf /var/lib/apt/lists/* \
  && pip install --no-cache-dir -r /tmp/requirements.txt \
  && playwright install chromium

COPY . /app

CMD ["python", "-m", "apps.worker.worker"]
