# syntax=docker/dockerfile:1

FROM alpine:3.22.2 AS build

RUN apk add --no-cache nodejs npm \
    && npm install -g sass@1.96.0 \
    && npm cache clean --force

FROM alpine:3.22.2

RUN apk add --no-cache nodejs \
    && adduser -D -g '' tumblelog \
    && mkdir /data \
    && chown tumblelog:tumblelog /data

COPY --from=build /usr/local /usr/local

USER tumblelog
WORKDIR /data

ENTRYPOINT ["sass"]
