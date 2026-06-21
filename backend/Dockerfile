FROM python:3.10-slim

WORKDIR /app

COPY requirements.docker.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

ENV PYTHONPATH=src

CMD ["uvicorn", "interfaces.api.main:app", "--host", "0.0.0.0", "--port", "8000"]