# Build microwrap
FROM python:3.11-bookworm AS build

# Install dependencies
WORKDIR /microwrap
RUN apt update && apt install -y build-essential libev-dev
COPY . /microwrap
RUN pip install poetry==1.5.1
RUN poetry install --no-root
RUN poetry run task compile

# Create microwrap image
FROM python:3.11-slim-bookworm

COPY --from=build /microwrap/build/microwrap /usr/bin/microwrap

ENTRYPOINT [ "microwrap" ]
