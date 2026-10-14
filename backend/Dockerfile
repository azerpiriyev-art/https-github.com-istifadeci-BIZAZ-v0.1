FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --system bizaz && useradd --system --gid bizaz --home-dir /app bizaz

COPY backend/requirements-prod.txt /app/requirements-prod.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install -r /app/requirements-prod.txt

COPY --chown=bizaz:bizaz backend/app /app/app
COPY --chown=bizaz:bizaz backend/scripts/purge_expired_notifications.py /app/scripts/purge_expired_notifications.py

USER bizaz
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read()"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
