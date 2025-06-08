from fastapi import FastAPI
from app.api import router
import uvicorn

app = FastAPI()

app.include_router(router)

if __name__ == '__main__':
    uvicorn.run("main:app", port=8080, reload=True)


# Инструкции по запуску FastAPI (для локального тестирования):
# 1. Установите необходимые библиотеки: pip install fastapi uvicorn pydub ffmpeg-python
# 2. Сохраните этот код в файл, например, main.py
# 3. Убедитесь, что ffmpeg установлен и добавлен в системный PATH.
# 4. Запустите сервер FastAPI: uvicorn main:app --reload

# Для тестирования этого endpoint вы можете использовать такие инструменты, как curl или Postman.
# Например, с помощью curl:
# curl -X POST -F "audio_file=@/путь/к/аудиофайлу.mp3" -F "image_file=@/путь/к/изображению.png" http://127.0.0.1:8000/create_video --output output.mp4