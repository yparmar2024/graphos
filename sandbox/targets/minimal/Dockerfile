FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends iputils-ping && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir Flask==3.1.2
COPY app.py .
EXPOSE 80
HEALTHCHECK --interval=3s --timeout=5s --start-period=5s --retries=20 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:80/', timeout=3)"
CMD ["python", "app.py"]
