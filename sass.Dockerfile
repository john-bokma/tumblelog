# Syntax=docker/dockerfile:1
FROM alpine:latest

LABEL maintainer="John Bokma" \
      version="1.0" \
      description="A pure JavaScript implementation of Sass"

WORKDIR /app

RUN apk add --no-cache npm \
    && npm install --global sass \
    && adduser -D -g '' tumblelog \
    && mkdir /data \
    && chown tumblelog:tumblelog /data

USER tumblelog
WORKDIR /data
VOLUME ["/data"]

ENTRYPOINT ["npx", "sass"]

