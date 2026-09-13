#!/bin/sh
set -e
# Standby PostgreSQL node replication bootstrap
until pg_isready -h postgres -p 5432 -U replicator; do
  echo "Waiting for primary PostgreSQL to accept replication connections..."
  sleep 2
done

if [ ! -s "$PGDATA/PG_VERSION" ]; then
  echo "Initializing standby replica from primary..."
  PGPASSWORD=replicator_password pg_basebackup -h postgres -p 5432 -U replicator -D "$PGDATA" -Fp -Xs -P -R
  chmod 0700 "$PGDATA"
fi

exec docker-entrypoint.sh postgres
