FROM python:3.13-slim

USER 0
WORKDIR /workspace

ARG SERVICE_PATH

COPY pyproject.toml README.md ./
COPY shared ./shared
COPY ${SERVICE_PATH}/requirements.txt ./service/requirements.txt
COPY ${SERVICE_PATH}/app ./service/app
COPY ${SERVICE_PATH}/tests ./service/tests

RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir -r service/requirements.txt \
    && python -m pip install --no-cache-dir -e ".[dev]"
