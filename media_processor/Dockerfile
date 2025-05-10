# Этап 1: Базовый образ Python (Debian 12 Bookworm)
FROM python:3.12.3-slim

# Установка переменных окружения
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive 
# Предотвращает интерактивные запросы apt

# Этап 2: Установка системных зависимостей (FFmpeg из Debian Testing)

# Определяем кодовое имя базового дистрибутива (для python:3.12.3-slim это bookworm)
ARG BASE_CODENAME=bookworm
# Определяем кодовое имя Testing (на момент написания это trixie)
ARG TESTING_CODENAME=trixie

RUN <<EOF
set -e
# Добавляем репозиторий Debian Testing (Trixie)
echo "deb http://deb.debian.org/debian ${TESTING_CODENAME} main" > /etc/apt/sources.list.d/testing.list

# Настраиваем APT Pinning
# Отдаем предпочтение пакетам из основного релиза (Bookworm)
echo "Package: *" > /etc/apt/preferences.d/99pinning
echo "Pin: release n=${BASE_CODENAME}" >> /etc/apt/preferences.d/99pinning
echo "Pin-Priority: 900" >> /etc/apt/preferences.d/99pinning
echo "" >> /etc/apt/preferences.d/99pinning
# Разрешаем установку пакетов из Testing (Trixie), но с низким приоритетом
echo "Package: *" >> /etc/apt/preferences.d/99pinning
echo "Pin: release n=${TESTING_CODENAME}" >> /etc/apt/preferences.d/99pinning
echo "Pin-Priority: 500" >> /etc/apt/preferences.d/99pinning

# Обновляем список пакетов ПОСЛЕ добавления репозитория и настройки pinning
apt-get update

# Устанавливаем ffmpeg ИЗ TESTING (-t ${TESTING_CODENAME})
# Также устанавливаем ca-certificates, необходимые для https
# Используем --no-install-recommends для минимизации размера
apt-get install -y --no-install-recommends -t ${TESTING_CODENAME} ffmpeg ca-certificates

# Очистка кэша apt
apt-get clean
rm -rf /var/lib/apt/lists/*
# Удаляем ненужные файлы настроек apt
rm /etc/apt/sources.list.d/testing.list
rm /etc/apt/preferences.d/99pinning
EOF

# Проверяем установленную версию FFmpeg (должна быть ~6.1)
RUN echo "Verifying FFmpeg installation:" && \
    ffmpeg -version | head -n 1

# Этап 3: Установка рабочей директории
WORKDIR /app

# Этап 4: Установка зависимостей Python
# Сначала скопируйте файл requirements.txt
COPY requirements.txt .
# Обновляем pip и устанавливаем зависимости
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Этап 5: Копирование кода приложения
COPY . .

# Этап 6: Открытие порта (если используете стандартный порт FastAPI)
# EXPOSE 8000

# Этап 7: Команда запуска приложения
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]