# Build the service executable in a "development" container
FROM debian:buster as build
# Add Java 11 JDK
RUN apt update && apt install -y openjdk-11-jdk
# Copy source code to container
COPY Version.java /Version.java
# Compile source code
RUN javac Version.java

# Create an image using microwrap as the base to serve as our runtime image
FROM michionlion/microwrap:latest
# Install Java 11 JRE
RUN apt update && apt install -y openjdk-11-jre && apt clean && rm -rf /var/lib/apt/lists/*
# Configure microwrap
COPY microwrap.json /microwrap.json
# Copy executable (a script to run Version.class)
COPY version.sh /version.sh
# Copy compiled code from the build image
COPY --from=build /Version.class /Version.class

EXPOSE 80
