FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --no-cache-dir --upgrade -r requirements.txt

COPY . .

CMD ["python", "main.py"]