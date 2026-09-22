FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates procps bubblewrap zstd \
    && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL https://ollama.com/install.sh | sh
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN chmod +x /app/start.sh
ENV PORT=10000 \
    AETHEL_DB_PATH=/data/aethel.db \
    AETHEL_WORKSPACE=/data/projects \
    OLLAMA_MODELS=/data/ollama
EXPOSE 10000
CMD ["/app/start.sh"]
