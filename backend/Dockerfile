FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --system bizaz \
    && useradd --system --gid bizaz --home-dir /app \
       --shell /usr/sbin/nologin bizaz

COPY requirements-prod.txt ./requirements-prod.txt
RUN python -m pip install --no-cache-dir -r requirements-prod.txt

COPY --chown=bizaz:bizaz app/ ./app/
COPY --chown=bizaz:bizaz scripts/ ./scripts/

USER bizaz

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=3)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
