# Этап 1: Базовый образ Python
FROM python:3.10-slim

# Установка переменных окружения
ENV PYTHONUNBUFFERED=1 \
    # Указываем путь, где система будет искать FFmpeg (хотя копирование в /usr/local/bin должно быть достаточно)
    PATH="/usr/local/bin:${PATH}"

# Этап 2: Установка системных зависимостей (включая утилиты для скачивания и распаковки FFmpeg)
# Добавлена утилита p7zip-full для распаковки .7z архивов
RUN apt-get update && \
    apt-get install -y --no-install-recommends wget p7zip-full ca-certificates && \
    # Очистка кэша apt
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Этап 3: Скачивание и установка конкретной сборки FFmpeg (используем последнюю с gyan.dev в формате .7z)
# URL для последней полной git-сборки FFmpeg с gyan.dev (используем .7z)
# Проверьте https://www.gyan.dev/ffmpeg/builds/ для актуального URL, если потребуется
RUN FFMPEG_URL="https://www.gyan.dev/ffmpeg/builds/ffmpeg-git-full.7z" && \
    echo "Downloading FFmpeg from $FFMPEG_URL" && \
    # Скачиваем архив .7z
    wget --progress=bar:force:noscroll -q $FFMPEG_URL -O /tmp/ffmpeg.7z && \
    echo "Unzipping FFmpeg archive (.7z)" && \
    # Распаковываем архив .7z с помощью 7z
    # 'x' - извлечь с полными путями, '-o' - указать выходную директорию
    7z x /tmp/ffmpeg.7z -o/tmp/ffmpeg-build && \
    # Находим директорию внутри архива (имя включает хэш сборки)
    FFMPEG_DIR=$(find /tmp/ffmpeg-build -maxdepth 1 -type d -name 'ffmpeg-*-git-*-full_build*') && \
    echo "Found FFmpeg directory: $FFMPEG_DIR" && \
    # Копируем исполняемые файлы ffmpeg и ffprobe в стандартный путь
    cp $FFMPEG_DIR/bin/ffmpeg /usr/local/bin/ && \
    cp $FFMPEG_DIR/bin/ffprobe /usr/local/bin/ && \
    # Устанавливаем права на выполнение
    chmod +x /usr/local/bin/ffmpeg /usr/local/bin/ffprobe && \
    echo "Cleaning up temporary files" && \
    # Удаляем временные файлы (.7z и распапкованную директорию)
    rm -rf /tmp/ffmpeg.7z /tmp/ffmpeg-build && \
    # Проверяем установленную версию FFmpeg
    echo "Verifying FFmpeg installation:" && \
    ffmpeg -version

# Этап 4: Установка рабочей директории
WORKDIR /app

# Этап 5: Установка зависимостей Python
# Сначала скопируйте файл requirements.txt
COPY requirements.txt .
# Обновляем pip и устанавливаем зависимости
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Этап 6: Копирование кода приложения
# Копируем все файлы из текущей директории (где лежит Dockerfile) в рабочую директорию контейнера (/app)
COPY . .

# Этап 7: Открытие порта
# Открываем порт 8000, на котором будет работать FastAPI по умолчанию
EXPOSE 8000

# Этап 8: Команда запуска приложения
# Запускаем uvicorn сервер, который будет слушать на всех интерфейсах (0.0.0.0)
# main - имя вашего python файла (например, main.py)
# app - имя экземпляра FastAPI в вашем файле (app = FastAPI())
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
