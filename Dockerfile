FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt requirements-dbt.txt pyproject.toml ./
COPY src/ ./src/
COPY dbt/ ./dbt/
RUN pip install --no-cache-dir -r requirements.txt -r requirements-dbt.txt -e .

# dbt looks in ~/.dbt by default, which does not exist here
ENV DBT_PROFILES_DIR=/app/dbt

# the manifest has to exist before Dagster can turn the models into assets. Parsing
# opens no connection but still resolves a profile, hence the placeholder credentials:
# the prod target reads PG* variables that only exist once the container is running
RUN cd /app/dbt && \
    DBT_TARGET=dev POSTGRES_PASSWORD=unused dbt deps && \
    DBT_TARGET=dev POSTGRES_PASSWORD=unused dbt parse

ENV DBT_TARGET=prod

ENV DAGSTER_HOME=/opt/dagster
COPY deploy/dagster.yaml /opt/dagster/dagster.yaml
