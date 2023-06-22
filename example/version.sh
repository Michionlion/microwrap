#!/bin/sh

USE_JAVA=true

if [ "$USE_JAVA" = "true" ] && [ -f Version.class ]; then
    java -classpath . Version "$@"
else
    VERSION="2.0.0"
    if [ "$1" = "--include-build" ]; then
        VERSION="$VERSION-b4"
    fi
    echo "$VERSION"
fi
