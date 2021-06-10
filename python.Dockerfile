# syntax=docker/dockerfile:1
FROM python:3-alpine

WORKDIR /app
COPY requirements.txt .
RUN apk add --no-cache --virtual .build-deps gcc musl-dev \
    && pip install --no-cache-dir -r requirements.txt \
    && apk del .build-deps

COPY tumblelog.py .
WORKDIR /data
ENTRYPOINT ["python", "/app/tumblelog.py"] 
