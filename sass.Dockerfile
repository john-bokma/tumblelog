# syntax=docker/dockerfile:1

FROM alpine:3.22.2 AS build

RUN apk add --no-cache curl tar

WORKDIR /tmp

RUN curl -fsSL \
	https://github.com/sass/dart-sass/releases/download/1.96.0/dart-sass-1.96.0-linux-x64.tar.gz \
    | tar -xz

FROM gcr.io/distroless/cc-debian13:nonroot

WORKDIR /data

COPY --from=build /tmp/dart-sass /usr/local/dart-sass

ENV PATH="/usr/local/dart-sass:${PATH}"

ENTRYPOINT [ "/usr/local/dart-sass/src/dart", "/usr/local/dart-sass/src/sass.snapshot" ]
