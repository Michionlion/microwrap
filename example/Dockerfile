# Build the service executable in a "development" container
FROM alpine:3.18 as build

RUN apk add --no-cache openjdk11
COPY Version.java /Version.java
RUN javac Version.java

# Create a new image with microwrap as the base to serve as our runtime image
FROM michionlion/microwrap:0.1
# Install runtime dependency
RUN apk add --no-cache openjre11
# Configure microwrap
COPY microwrap.json /microwrap.json
# Copy the executable from the build image
COPY --from=build /Version.class /Version.class
