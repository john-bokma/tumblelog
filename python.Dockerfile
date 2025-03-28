# syntax=docker/dockerfile:1
FROM python:3-alpine

LABEL maintainer="John Bokma" \
      version="1.0" \
      description="Tumblelog Application (Python version)"

WORKDIR /app

COPY requirements.txt .
RUN apk add --no-cache --virtual .build-deps gcc musl-dev \
    && apk add --no-cache tzdata \
    && pip install --no-cache-dir --requirement requirements.txt \
    && rm requirements.txt \
    && apk del .build-deps \
    && adduser -D -g '' tumblelog \
    && mkdir /data \
    && chown tumblelog:tumblelog /data

COPY --chown=tumblelog:tumblelog tumblelog.py .

USER tumblelog
WORKDIR /data
VOLUME ["/data"]

ENTRYPOINT ["python", "/app/tumblelog.py"]
