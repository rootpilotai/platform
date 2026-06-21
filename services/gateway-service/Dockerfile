FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY shared ./shared
COPY infrastructure ./infrastructure
COPY services/gateway-service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir --no-deps .

COPY services/gateway-service/app ./app
COPY services/gateway-service/run.py ./run.py

EXPOSE 8005

CMD ["uvicorn", "run:app", "--host", "0.0.0.0", "--port", "8005"]
