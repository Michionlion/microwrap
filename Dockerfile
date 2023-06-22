# Build microwrap
FROM alpine:latest as build

# Install dependencies
WORKDIR /microwrap
RUN apk add --no-cache build-base libev poetry
COPY . /microwrap
RUN poetry install
RUN poetry run task compile

# Create microwrap image
FROM alpine:latest

COPY --from=build /microwrap/build/microwrap /usr/bin/microwrap

ENTRYPOINT [ "microwrap" ]
