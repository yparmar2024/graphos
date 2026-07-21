FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y nmap

COPY . /app/tools/
RUN pip install -r tools/requirements.txt

ENV PYTHONPATH=/app

CMD ["python", "tools/main.py"]
