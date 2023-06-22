# Build microwrap
FROM python:3.11-buster as build

# Install dependencies
WORKDIR /microwrap
RUN apt update && apt install -y build-essential libev-dev
COPY . /microwrap
RUN pip install poetry
RUN poetry install
RUN poetry run task compile

# Create microwrap image
FROM python:3.11-slim-buster

COPY --from=build /microwrap/build/microwrap /usr/bin/microwrap

ENTRYPOINT [ "microwrap" ]
