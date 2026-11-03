FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends nmap curl ffuf ca-certificates && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /app/tools/requirements.txt
RUN pip install --no-cache-dir -r /app/tools/requirements.txt
ARG SECLISTS_REVISION=68bcd12457978649d41ae4f56e3b5d2db2b72560
RUN mkdir -p /app/tools/wordlists && \
    curl --fail --location --retry 3 "https://raw.githubusercontent.com/danielmiessler/SecLists/${SECLISTS_REVISION}/Discovery/Web-Content/common.txt" -o /app/tools/wordlists/common.txt && \
    curl --fail --location --retry 3 "https://raw.githubusercontent.com/danielmiessler/SecLists/${SECLISTS_REVISION}/Discovery/Web-Content/quickhits.txt" -o /app/tools/wordlists/quick.txt && \
    curl --fail --location --retry 3 "https://raw.githubusercontent.com/danielmiessler/SecLists/${SECLISTS_REVISION}/Discovery/Web-Content/api/api-endpoints.txt" -o /app/tools/wordlists/api.txt
COPY . /app/tools/
ENV PYTHONPATH=/app PYTHONUNBUFFERED=1
USER 1000:1000
CMD ["python", "-m", "tools.main"]
