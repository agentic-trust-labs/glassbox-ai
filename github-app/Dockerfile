FROM python:3.11-slim

# Install gh CLI and git
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl && \
    curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null && \
    apt-get update && apt-get install -y gh && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install server dependencies
COPY github-app/requirements.txt ./server-requirements.txt
RUN pip install --no-cache-dir -r server-requirements.txt

# Install agent dependencies
COPY requirements.txt ./agent-requirements.txt
RUN pip install --no-cache-dir -r agent-requirements.txt

# Copy server code
COPY github-app/server.py github-app/auth.py ./

# Copy agent code (so we don't need to clone it each time)
COPY src/ ./src/

ENV PYTHONPATH=/app/src
ENV PORT=8080

EXPOSE 8080

CMD ["python", "server.py"]
