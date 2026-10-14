#!/bin/sh
set -eu

: "${BIZAZ_APP_USER:?BIZAZ_APP_USER must be set}"
: "${BIZAZ_APP_PASSWORD:?BIZAZ_APP_PASSWORD must be set}"

psql \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  --set=ON_ERROR_STOP=1 \
  --set=app_user="$BIZAZ_APP_USER" \
  --set=app_password="$BIZAZ_APP_PASSWORD" \
  --set=db_name="$POSTGRES_DB" <<'SQL'
CREATE ROLE :"app_user" LOGIN PASSWORD :'app_password';
GRANT CONNECT ON DATABASE :"db_name" TO :"app_user";
SQL
