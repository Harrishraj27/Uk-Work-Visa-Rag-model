FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY core ./core
COPY app ./app
COPY data/chunks.jsonl ./data/chunks.jsonl
COPY data/manifest.json ./data/manifest.json
COPY data/fixtures ./data/fixtures
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
# No .env is copied. Pass settings at run time:  docker run --env-file .env -p 8000:8000 uk-work-visa-rag
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
