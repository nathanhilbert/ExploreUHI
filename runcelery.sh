export HIPOSTGRESAPP=postgresql://urbis:urbis@localhost:5434/urbisapp
export HIPOSTGRES=postgresql://urbis:urbis@localhost:5434/urbisdata01
export HIVOLUMESTORAGE=/media/staging/urbis/nlh/ontodar/rasterstorage
export HIRASTERBASE=/media/staging/urbis/nlh/ontodar/rasterstorage
export SPATIALINDEX_C_LIBRARY=/media/staging/urbis/nlh/libspatialindex/lib/libspatialindex_c.so
celery -A dataprocessors worker --loglevel=info
