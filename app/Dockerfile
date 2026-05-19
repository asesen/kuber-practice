FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir prometheus_client

COPY main.py /app/main.py

ENV APP_PORT=8080

EXPOSE 8080

CMD ["python", "/app/main.py"]
