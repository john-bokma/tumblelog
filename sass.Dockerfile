# Syntax=docker/dockerfile:1
FROM alpine:latest

WORKDIR /app

RUN apk add --no-cache npm \
    && npm install --global sass

WORKDIR /data

ENTRYPOINT ["npx", "sass"]

