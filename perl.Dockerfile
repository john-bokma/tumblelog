# syntax=docker/dockerfile:1
FROM alpine:latest AS base

WORKDIR /app

FROM base AS builder

RUN apk add --no-cache --virtual .build-deps \
        gcc musl-dev make wget perl-dev \
        perl-app-cpanminus \
    && apk add cmark-dev perl \
    && cpanm URI JSON::XS YAML::XS Path::Tiny CommonMark Try::Tiny \
    && apk del .build-deps

FROM base AS run
COPY --from=builder /usr/local /usr/local
COPY --from=builder /usr/lib /usr/lib
COPY --from=builder /usr/share /usr/share
COPY --from=builder /usr/bin/perl /usr/bin

COPY tumblelog.pl .
WORKDIR /data
ENTRYPOINT ["perl", "/app/tumblelog.pl"]
