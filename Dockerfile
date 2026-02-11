FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV REPO_ROOT=/app

WORKDIR /app

COPY requirements.txt requirements-memory.txt requirements-service.txt /app/
RUN pip install --no-cache-dir -r requirements-service.txt

COPY . /app

EXPOSE 8000

CMD ["uvicorn", "team.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
