#!/bin/sh

[ -n "$1" ] && exec "$@"

#######################
# wait for postgresql #
#######################
check_pgsql() {
    python3 manage.py shell -c "import sys
from django.db import connections
try:
  connections['default'].cursor()
except Exception:
  sys.exit(1)
sys.exit(0)"
}

wait_postgresql() {
    until check_pgsql
    do
        printf "."
        sleep 1
    done
}


###########################
# wait for the migrations #
###########################
check_initial_migrations() {
    python3 manage.py shell -c "import sys
import django
from django.db import connections
try:
    connections['default'].cursor().execute('SELECT * from django_migrations')
except django.db.utils.Error:
    sys.exit(1)
sys.exit(0)"
}

check_migrations() {
    migrations=$(python3 manage.py showmigrations --plan)
    if [ "$?" != "0" ]
    then
        return 1
    fi
    return $(echo "$migrations" | grep -c "\\[ \\]")
}

wait_migration() {
    # Check that the django_migrations table exist before calling 'showmigrations'.
    # In fact, 'showmigrations' will create the table if it's missing. But if
    # two processes try to create the table at the same time, the last to
    # commit will crash.
    until check_initial_migrations
    do
        echo "."
        sleep 1
    done
    # The table exist, calling 'showmigrations' is now idempotent.
    until check_migrations
    do
        echo "."
        sleep 1
    done
}


echo "Waiting for postgresql"
wait_postgresql
echo "done"
echo ""

if [ "$SERVICE" = "celery" ]
then
  echo "Waiting for migrations"
  wait_migration
  echo "done"
  echo ""

  exec python3 -m celery -A website worker --loglevel=info
elif [ "$SERVICE" = "gunicorn" ]
then
  echo "Applying migrations"
  python3 manage.py migrate --noinput
  echo "done"
  echo ""

  exec gunicorn3 --log-level debug --bind 0.0.0.0:80 --threads 10 --workers 4 --worker-tmp-dir /dev/shm website.wsgi
fi
