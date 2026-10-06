#!/usr/bin/env bash
# Additive toolbox deployment. Keep old grades, model files, secrets and rollback image.
set -euo pipefail
cd /home/ubuntu/gradeflow
compose=(docker compose --env-file .env.vps -f docker-compose.vps.yml)
backup=scratch/toolbox_before_2112
mkdir -p "$backup"
chmod 700 "$backup"
test -z "$(git status --porcelain --untracked-files=no)"
if [ ! -s "$backup/database.sql" ]; then
  git rev-parse HEAD > "$backup/commit.txt"
  docker tag gradeflow-vps-web gradeflow-vps-web:before-toolbox-2112
  "${compose[@]}" exec -T db sh -c 'exec pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > "$backup/database.sql"
  chmod 600 "$backup/database.sql"
  test -s "$backup/database.sql"
fi
git pull --ff-only
"${compose[@]}" build web
# Test the production image against an isolated temporary SQLite database.
# Production PostgreSQL and user data are never used by TestCase fixtures.
"${compose[@]}" run --rm --no-deps -e DJANGO_DEBUG=True -e DATABASE_URL=sqlite:////tmp/toolbox-test.sqlite3 web \
  python manage.py test toolbox --noinput --verbosity 1
"${compose[@]}" up -d --no-deps --wait --wait-timeout 240 web
"${compose[@]}" up -d --no-deps notifications
"${compose[@]}" exec -T proxy nginx -s reload
"${compose[@]}" exec -T web python manage.py check
"${compose[@]}" exec -T web python manage.py showmigrations toolbox
"${compose[@]}" ps
curl --silent --show-error --output /dev/null --write-out 'Toolbox protected endpoint HTTP %{http_code}\n' \
  --header 'Host: gradeflow.io.vn' --header 'X-Forwarded-Proto: https' http://127.0.0.1:8000/api/v1/classrooms/
git rev-parse --short HEAD
