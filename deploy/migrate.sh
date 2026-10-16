#!/bin/sh
set -eu

: "${PGHOST:?PGHOST is required}"
: "${PGDATABASE:?PGDATABASE is required}"
: "${PGUSER:?PGUSER is required}"
: "${PGPASSWORD:?PGPASSWORD is required}"

psql -X -v ON_ERROR_STOP=1 <<'SQL'
CREATE TABLE IF NOT EXISTS public.schema_migrations (
    filename text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
);
REVOKE ALL PRIVILEGES ON TABLE public.schema_migrations FROM PUBLIC, bizaz_app;
SQL

found=0

for migration in /migrations/*.sql; do
    [ -f "$migration" ] || continue
    found=1
    filename=${migration##*/}

    applied="$(psql -X -v ON_ERROR_STOP=1 \
        -v migration_name="$filename" -Atq <<'SQL'
SELECT 1
FROM public.schema_migrations
WHERE filename = :'migration_name';
SQL
)"

    if [ "$applied" = "1" ]; then
        echo "SKIP  $filename"
        continue
    fi

    echo "APPLY $filename"

    {
        printf 'BEGIN;\n'
        awk 'NR == 1 { sub(/^\357\273\277/, "") } toupper($0) !~ /^[[:space:]]*(BEGIN|COMMIT);[[:space:]]*$/ { print }' "$migration"
        printf "INSERT INTO public.schema_migrations (filename) VALUES ('%s');\n" "$filename"
        printf 'COMMIT;\n'
    } | psql -X -v ON_ERROR_STOP=1
done

if [ "$found" -ne 1 ]; then
    echo "ERROR: No SQL migrations found in /migrations." >&2
    exit 1
fi

echo "Migration run completed."
