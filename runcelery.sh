export SPATIALINDEX_C_LIBRARY=/media/staging/urbis/nlh/libspatialindex/lib/libspatialindex_c.so
celery -A dataprocessors worker --loglevel=info
