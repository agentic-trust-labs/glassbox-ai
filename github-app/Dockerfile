FROM python:3.11-slim

# Install git (needed for cloning target repos)
RUN apt-get update && apt-get install -y --no-install-recommends git && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install server dependencies (layer cached separately from agent deps)
COPY github-app/requirements.txt ./server-requirements.txt
RUN pip install --no-cache-dir -r server-requirements.txt

# Install agent dependencies
COPY requirements.txt ./agent-requirements.txt
RUN pip install --no-cache-dir -r agent-requirements.txt

# Copy server package
COPY github-app/app/ ./app/

# Copy agent code (baked in, no clone needed per run)
COPY src/ ./src/

ENV PYTHONPATH=/app:/app/src
ENV PORT=8080

EXPOSE 8080

CMD ["python", "-m", "app.main"]
