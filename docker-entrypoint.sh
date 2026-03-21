#!/bin/bash
set -e

MYSQL_HOST="${MYSQL_HOST:-localhost}"
MYSQL_PORT="${MYSQL_PORT:-3306}"
MYSQL_USER="${MYSQL_USER:-root}"
MYSQL_PASSWORD="${MYSQL_PASSWORD:-}"

# Wait for MySQL if using a remote host
if [ "${MYSQL_HOST}" != "localhost" ] && [ "${MYSQL_HOST}" != "127.0.0.1" ]; then
    echo "Waiting for MySQL at ${MYSQL_HOST}:${MYSQL_PORT}..."
    until mysqladmin ping \
        -h"${MYSQL_HOST}" \
        -P"${MYSQL_PORT}" \
        -u"${MYSQL_USER}" \
        -p"${MYSQL_PASSWORD}" \
        --skip-ssl \
        --silent 2>/dev/null; do
        echo "  MySQL not ready, retrying in 3s..."
        sleep 3
    done
    echo "MySQL is ready."
fi

# Initialize schema (idempotent — uses IF NOT EXISTS)
echo "Initializing database schema..."
mysql \
    -h"${MYSQL_HOST}" \
    -P"${MYSQL_PORT}" \
    -u"${MYSQL_USER}" \
    -p"${MYSQL_PASSWORD}" \
    --skip-ssl \
    < /init.sql && echo "Schema ready." || echo "Schema init skipped (may already exist)."

exec /usr/bin/supervisord -n -c /etc/supervisor/supervisord.conf
