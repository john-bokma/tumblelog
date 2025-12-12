# syntax=docker/dockerfile:1
FROM alpine:3.22.2 AS base

WORKDIR /app

FROM base AS builder

RUN apk add --no-cache --virtual .build-deps \
        make wget gcc musl-dev perl-dev \
        perl-app-cpanminus \
    && apk add --no-cache perl cmark-dev tzdata \
    && cpanm --no-man-pages --from https://cpan.metacpan.org/ \
             URI JSON::XS YAML::XS Path::Tiny CommonMark Try::Tiny \
    && rm -rf ~/.cpanm \
    && apk del .build-deps


FROM base AS run

LABEL maintainer="John Bokma" \
      version="1.0" \
      description="Tumblelog Application (Perl version)"

RUN adduser -D -g '' tumblelog \
    && mkdir /data \
    && chown tumblelog:tumblelog /data

COPY --from=builder /usr/bin/perl /usr/bin
COPY --from=builder /usr/lib/ /usr/lib/
COPY --from=builder /usr/share /usr/share
COPY --from=builder /usr/local /usr/local

COPY --chown=tumblelog:tumblelog tumblelog.pl .

USER tumblelog
WORKDIR /data
VOLUME ["/data"]

ENTRYPOINT ["perl", "/app/tumblelog.pl"]
