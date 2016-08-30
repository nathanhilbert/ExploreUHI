export HIPOSTGRESAPP=postgresql://urbis:urbis@localhost:5432/urbisapp
export HIPOSTGRES=postgresql://urbis:urbis@localhost:5432/urbis
export HIDAYMET=/Volumes/UrbisBackup/rasterstorage/daymet
export HIRASTERBASE=/data/rasterstorage
unset SPATIALINDEX_C_LIBRARY
celery -A dataprocessors worker --loglevel=info