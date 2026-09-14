FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app/web:/app/1C_Support_Agent
WORKDIR /app
COPY 1C_Support_Agent/requirements.txt ./1C_Support_Agent/requirements.txt
COPY web/server/requirements.txt ./web/server/requirements.txt
COPY web/server/requirements.lock ./web/server/requirements.lock
RUN pip install --no-cache-dir -r web/server/requirements.lock
COPY 1C_Support_Agent/app ./1C_Support_Agent/app
COPY 1C_Support_Agent/support_agent_db ./1C_Support_Agent/support_agent_db
COPY 1C_Support_Agent/scripts ./1C_Support_Agent/scripts
COPY 1C_Support_Agent/data/knowledge ./1C_Support_Agent/data/knowledge
COPY web/server ./web/server
RUN useradd --uid 10001 --create-home support && mkdir -p /state && ln -s /state/support_agent.db /app/1C_Support_Agent/support_agent.db && chown -R support:support /state /app
USER support
WORKDIR /app/1C_Support_Agent
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
