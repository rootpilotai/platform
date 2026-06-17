FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY shared ./shared
COPY infrastructure ./infrastructure
COPY services/otel-adapter-service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir --no-deps .

COPY services/otel-adapter-service/app ./app

EXPOSE 8004

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8004"]
