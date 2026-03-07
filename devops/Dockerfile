FROM python:3.10-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
        libpoppler-cpp-dev libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    python -m nltk.downloader punkt punkt_tab stopwords -d /usr/local/share/nltk_data

COPY backend/ .
RUN mkdir -p data

ENV DB_PATH=/app/data/warehouse.db
ENV PYTHONUNBUFFERED=1

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/')" || exit 1

CMD ["python", "app.py"]
