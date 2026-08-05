FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir -r requirements.txt -e .

ENV DAGSTER_HOME=/opt/dagster
COPY deploy/dagster.yaml /opt/dagster/dagster.yaml
