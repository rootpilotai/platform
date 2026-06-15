FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY shared ./shared
COPY infrastructure ./infrastructure
COPY services/ai-investigation-service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir --no-deps .

COPY services/ai-investigation-service/app ./app
COPY services/ai-investigation-service/workflows ./workflows
COPY services/ai-investigation-service/run.py ./run.py

EXPOSE 8002

CMD ["uvicorn", "run:app", "--host", "0.0.0.0", "--port", "8002"]
