#!/bin/bash

until pg_isready -h db -p 5432 -U postgres; do
  echo "Waiting for PostgreSQL to be ready..."
  sleep 2
done

python manage.py makemigrations
python manage.py migrate

# collect static files
python manage.py collectstatic --noinput

# start server
python manage.py runserver 0.0.0.0:8000