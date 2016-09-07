export HIPOSTGRESAPP=postgresql://urbis:urbis@localhost:5432/urbisapp
export HIPOSTGRES=postgresql://urbis:urbis@localhost:5432/urbis
export HIVOLUMESTORAGE=/Volumes/UrbisBackup/rasterstorage
export HIRASTERBASE=/data/rasterstorage
unset SPATIALINDEX_C_LIBRARY
python webserver.py