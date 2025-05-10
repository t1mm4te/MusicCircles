# Этап 1: Базовый образ Python
FROM python:3.12.3-slim

# Установка переменных окружения
ENV PYTHONUNBUFFERED=1

# Этап 2: Установка системных зависимостей (включая FFmpeg)
RUN apt-get update

RUN apt install -y ffmpeg

RUN apt-get update && \
    # Устанавливаем ffmpeg и ca-certificates (нужны для HTTPS)
    # Утилиты wget и p7zip-full больше не нужны
    apt-get install -y --no-install-recommends ca-certificates && \
    # Очистка кэша apt
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*


# !!! ВАЖНОЕ ЗАМЕЧАНИЕ !!!
# Стандартная сборка ffmpeg из репозиториев Debian (на котором основан slim)
# может НЕ включать поддержку кодеков, таких как libx264 (для H.264).
# Ваше приложение использует vcodec='libx264' в create_video_from_audio_and_cover_files.
# Если после сборки и запуска видео не будет создаваться с H.264,
# возможно, потребуется включить репозиторий non-free в Debian и
# установить ffmpeg оттуда, или вернуться к статической сборке.
# Пример (НЕ РАСКОММЕНТИРОВАТЬ БЕЗ НЕОБХОДИМОСТИ, усложняет Dockerfile):
# RUN echo "deb http://deb.debian.org/debian/ $(grep VERSION_CODENAME /etc/os-release) main contrib non-free" >> /etc/apt/sources.list && \
#     apt-get update && \
#     apt-get install -y --no-install-recommends ffmpeg && \
#     apt-get clean && \
#     rm -rf /var/lib/apt/lists/*

# Проверяем установленную версию FFmpeg (опционально)
RUN echo "Verifying FFmpeg installation:" && \
    ffmpeg -version

# Этап 3: Установка рабочей директории
WORKDIR /app

# Этап 4: Установка зависимостей Python
# Сначала скопируйте файл requirements.txt
COPY requirements.txt .
# Обновляем pip и устанавливаем зависимости
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# RUN pip install uvicorn
# RUN pip install pip install uvicorn
# Этап 5: Копирование кода приложения
# Копируем все файлы из текущей директории (где лежит Dockerfile) в рабочую директорию контейнера (/app)
COPY . .

# Этап 6: Открытие порта
# Открываем порт 8000, на котором будет работать FastAPI по умолчанию
# EXPOSE 8000

# Этап 7: Команда запуска приложения
# Запускаем uvicorn сервер, который будет слушать на всех интерфейсах (0.0.0.0)
# main - имя вашего python файла (например, main.py)
# app - имя экземпляра FastAPI в вашем файле (app = FastAPI())
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]