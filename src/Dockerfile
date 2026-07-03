FROM composer:2 AS vendor
WORKDIR /app
COPY composer.json composer.lock ./
RUN composer install --no-dev --no-interaction --no-progress --prefer-dist

FROM php:8.3-apache
RUN apt-get update \
    && apt-get install -y --no-install-recommends libzip-dev unzip curl \
    && rm -rf /var/lib/apt/lists/* \
    && a2enmod headers rewrite

COPY --from=vendor /app/vendor /var/www/html/vendor
COPY public /var/www/html/public
COPY app /var/www/html/app
COPY security-headers.conf /etc/apache2/conf-enabled/security-headers.conf
RUN { echo "expose_php = Off"; echo "display_errors = Off"; } > /usr/local/etc/php/conf.d/security.ini

ENV APACHE_DOCUMENT_ROOT=/var/www/html/public
RUN sed -ri -e 's!/var/www/html!${APACHE_DOCUMENT_ROOT}!g' /etc/apache2/sites-available/*.conf \
    && sed -ri -e 's!/var/www/!${APACHE_DOCUMENT_ROOT}!g' /etc/apache2/apache2.conf /etc/apache2/conf-enabled/*.conf

RUN chown -R www-data:www-data /var/www/html

USER www-data

EXPOSE 80
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s \
    CMD curl -f http://localhost/healthz.php || exit 1
