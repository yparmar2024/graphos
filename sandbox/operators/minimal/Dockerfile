FROM python:3.11-slim
WORKDIR /app

RUN pip install openai httpx mcp

RUN useradd -m agentuser
USER agentuser

CMD ["python", "agent.py"]