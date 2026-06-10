FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY shared ./shared
COPY services/ai-investigation-service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir --no-deps .

COPY services/ai-investigation-service/app ./app
COPY services/ai-investigation-service/prompts ./prompts
COPY services/ai-investigation-service/workflows ./workflows

CMD ["python", "-c", "print('ai-investigation-service scaffold ready')"]
