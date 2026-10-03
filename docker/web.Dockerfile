FROM debian:bookworm-slim

ENV TZ=Asia/Tokyo

RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx php8.2-fpm php8.2-curl supervisor tzdata \
    && rm -rf /var/lib/apt/lists/* \
    # Pass container env (STOCKTOOL_API_BASE) through to PHP getenv()
    && sed -i 's|^;\?clear_env = .*|clear_env = no|' /etc/php/8.2/fpm/pool.d/www.conf \
    && sed -i 's|^listen = .*|listen = 127.0.0.1:9000|' /etc/php/8.2/fpm/pool.d/www.conf \
    && rm -f /etc/nginx/sites-enabled/default /var/www/html/index.nginx-debian.html \
    && mkdir -p /run/php

COPY docker/nginx.conf /etc/nginx/conf.d/stocktool.conf
COPY docker/supervisord.conf /etc/supervisor/conf.d/stocktool.conf
COPY frontend/*.php /var/www/html/
COPY frontend/css/ /var/www/html/css/

EXPOSE 80
CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/supervisord.conf"]
