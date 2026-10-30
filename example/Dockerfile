ARG MICROWRAP_IMAGE=michionlion/microwrap:latest

# Build the service executable in a "development" container
FROM eclipse-temurin:11-jdk-jammy AS build
# Copy source code to container
COPY Version.java /Version.java
# Compile source code
RUN javac Version.java

# Create an image using microwrap as the base to serve as our runtime image
FROM ${MICROWRAP_IMAGE}
COPY --from=build /opt/java/openjdk /opt/java/openjdk
ENV PATH="/opt/java/openjdk/bin:${PATH}"
# Configure microwrap
COPY microwrap.json /microwrap.json
# Copy executable (a script to run Version.class)
COPY version.sh /version.sh
# Copy compiled code from the build image
COPY --from=build /Version.class /Version.class

EXPOSE 80
