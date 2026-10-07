FROM python:3.12-slim

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY static ./static

ENV DATA_DIR=/srv/data \
    ENABLE_SCHEDULER=1 \
    RUN_ON_START=0 \
    COLLECT_INTERVAL_MIN=60

EXPOSE 8000
CMD ["uvicorn", "app.web:app", "--host", "0.0.0.0", "--port", "8000"]
