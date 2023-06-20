# Build microwrap
FROM alpine:3.18 as build

# Install dependencies
RUN apk add --no-cache poetry
RUN poetry install
RUN poetry run task compile

# Create microwrap image
FROM alpine:3.18

COPY --from=build /microwrap /usr/bin/microwrap
COPY --from=build /usr/local/lib/libmicrohttpd.so.12 /usr/local/lib

ENTRYPOINT [ "microwrap" ]
