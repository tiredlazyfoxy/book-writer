#!/bin/bash
# BookWriter — deploy-server update script.
#
# Loads the image staged by build.ps1 into $DOCKER_STORE/bookwriter, refreshes
# the deploy config next to this script, and brings the stack up.
#
# Usage: ./update.sh [--images|--config|--all] [--no-restart]
set -e

MODE="all"
RESTART=1

while [ $# -gt 0 ]; do
    case "$1" in
        --images) MODE="images" ;;
        --config) MODE="config" ;;
        --all) MODE="all" ;;
        --no-restart) RESTART=0 ;;
        *) echo "Usage: $0 [--images|--config|--all] [--no-restart]"; exit 1 ;;
    esac
    shift
done

if [ -z "$DOCKER_STORE" ]; then
    echo "ERROR: DOCKER_STORE environment variable is not set"
    exit 1
fi

STORE_DIR="$DOCKER_STORE/bookwriter"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ ! -d "$STORE_DIR" ]; then
    echo "ERROR: Store directory does not exist: $STORE_DIR"
    exit 1
fi

if [ "$MODE" = "images" ] || [ "$MODE" = "all" ]; then
    ARCHIVE="$STORE_DIR/bookwriter-latest.7z"

    if [ ! -f "$ARCHIVE" ]; then
        echo "ERROR: Image archive not found: $ARCHIVE"
        exit 1
    fi

    echo "Loading iezious/bookwriter..."
    7z x -so "$ARCHIVE" | docker load
fi

if [ "$MODE" = "config" ] || [ "$MODE" = "all" ]; then
    if [ ! -f "$STORE_DIR/docker-compose.yml" ]; then
        echo "ERROR: docker-compose.yml not found in $STORE_DIR"
        exit 1
    fi

    cp "$STORE_DIR/docker-compose.yml" "$SCRIPT_DIR/"
    echo "Copied docker-compose.yml to $SCRIPT_DIR"

    if [ ! -f "$SCRIPT_DIR/.env" ]; then
        if [ ! -f "$STORE_DIR/.env.example" ]; then
            echo "ERROR: .env is missing and .env.example was not found in $STORE_DIR"
            exit 1
        fi

        cp "$STORE_DIR/.env.example" "$SCRIPT_DIR/.env"
        echo ""
        echo "***********************************************************************"
        echo "*  WARNING: no .env was present — created one from .env.example.      *"
        echo "*  It is a TEMPLATE with empty values. Edit $SCRIPT_DIR/.env"
        echo "*  and fill it in, then re-run this script. Until you do, any LLM      *"
        echo "*  provider whose api_key is a \$ENV_VAR reference will not work.       *"
        echo "***********************************************************************"
        echo ""
    fi
fi

# The external database folder: bookwriter.db + vector/ live here.
mkdir -p "$SCRIPT_DIR/data"

cd "$SCRIPT_DIR"

if [ "$RESTART" -eq 1 ]; then
    echo "Starting stack..."
    docker compose up -d
    docker image prune -f
fi

echo ""
docker compose ps
