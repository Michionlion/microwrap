#!/bin/sh

USE_JAVA=true

if [ "$USE_JAVA" == "true" && -f Version.class ]; then
    java Version.class
else
    VERSION="1.0.0"

    if [ "$1" == "--include-build" ]; then
        VERSION="$VERSION-b4"
    fi

    echo "$VERSION"
fi
