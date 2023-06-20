# Build the service executable in a "development" container
FROM alpine:latest as build
# Add Java 11 JDK
RUN apk add --no-cache openjdk11
# Copy source code to container
COPY Version.java /Version.java
# Compile source code
RUN javac Version.java

# Create an image using microwrap as the base to serve as our runtime image
FROM michionlion/microwrap:latest
# Install Java 11 JRE
RUN apk add --no-cache openjre11
# Configure microwrap
COPY microwrap.json /microwrap.json
# Copy executable (a script to run Version.class)
COPY version.sh /version.sh
# Copy compiled code from the build image
COPY --from=build /Version.class /Version.class
