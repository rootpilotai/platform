FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY prompts ./prompts
COPY workflows ./workflows

CMD ["python", "-c", "print('ai-investigation-service scaffold ready')"]
