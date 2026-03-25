FROM apache/superset:latest
USER root

# The apache/superset image runs python from /app/.venv which lacks pip.
# We use the system pip but install the package into the virtualenv's site-packages.
RUN pip install psycopg2-binary --target /app/.venv/lib/python3.10/site-packages

USER superset
