FROM python:3.9-slim

# Install nginx, PHP-FPM, MySQL client, supervisor, and dependencies for Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
        nginx \
        php-fpm \
        php-curl \
        default-mysql-client \
        supervisor \
        curl \
        libnss3 \
        libnspr4 \
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libcups2 \
        libdbus-1-3 \
        libdrm2 \
        libexpat1 \
        libgbm1 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

# Configure PHP-FPM: TCP port + allow_url_fopen (needed for file_get_contents HTTP)
RUN PHP_VER=$(php --version | grep -oP '^\S+\s+\K\d+\.\d+') \
    && sed -i "s|listen = /run/php/php${PHP_VER}-fpm.sock|listen = 127.0.0.1:9000|" \
        /etc/php/${PHP_VER}/fpm/pool.d/www.conf \
    && echo "allow_url_fopen = On" >> /etc/php/${PHP_VER}/fpm/php.ini \
    && ln -sf /usr/sbin/php-fpm${PHP_VER} /usr/local/bin/php-fpm-run

# Python dependencies (+ gunicorn for production)
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt gunicorn

# Install Playwright browsers (Chromium for headless scraping)
RUN playwright install chromium

# Application files
COPY backend/  /app/backend/
COPY frontend/ /var/www/html/
COPY init.sql  /init.sql

# Config
COPY nginx.conf        /etc/nginx/sites-available/default
COPY supervisord.conf  /etc/supervisor/conf.d/stocktool.conf
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Remove default nginx site if it conflicts
RUN rm -f /etc/nginx/sites-enabled/default \
    && ln -sf /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default

RUN mkdir -p /var/log/supervisor /run/php

WORKDIR /app/backend
EXPOSE 80

ENTRYPOINT ["/docker-entrypoint.sh"]
