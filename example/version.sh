#!/bin/sh

VERSION="1.0.0"

if [ "$1" == "--include-build" ]; then
    VERSION="$VERSION-b4"
fi

echo "$VERSION"
