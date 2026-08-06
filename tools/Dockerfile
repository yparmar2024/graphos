FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y nmap curl ffuf wget build-essential

RUN mkdir -p /app/tools/wordlists && \
    wget -q https://raw.githubusercontent.com/danielmiessler/SecLists/master/Discovery/Web-Content/common.txt -O /app/tools/wordlists/common.txt

COPY . /app/tools/
RUN pip install -r tools/requirements.txt

ENV PYTHONPATH=/app

CMD ["python", "tools/main.py"]
