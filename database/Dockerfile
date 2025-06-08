FROM python:3.12-slim

WORKDIR /app

# Создаем директорию для данных
RUN mkdir -p /app/data

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --no-cache-dir --upgrade -r requirements.txt

COPY . .

# Устанавливаем PYTHONPATH
ENV PYTHONPATH="/app"

# Открываем порт
EXPOSE 8001

# Команда запуска
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]