#!/usr/bin/env bash
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate --no-input

if [ "${SEED_DEMO_DATA:-False}" = "True" ]; then
  python manage.py seed_demo_data
fi
