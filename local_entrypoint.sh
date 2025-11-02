#!/bin/bash

until pg_isready -h db -p 5432 -U postgres; do
  echo "Waiting for PostgreSQL to be ready..."
  sleep 2
done

python manage.py makemigrations
python manage.py migrate

# collect static files
python manage.py collectstatic --noinput

# start ASGI server for WebSocket support
daphne -b 0.0.0.0 -p 8000 config.asgi:application