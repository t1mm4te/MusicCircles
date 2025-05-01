1) Создать папку с окружением, файлом main.py и добавить туда любой *mp3.

2) Установить зависимые библиотеки в окружение: pip install fastapi, uvicorn, pydub.

3) Установить pip install uvicorn и зависимость pip install python-multipart.

4) Зайти на сайт https://ffmpeg.org/download.html
Для Windows: Cкачать и установить программу https://www.gyan.dev/ffmpeg/builds/ffmpeg-git-essentials.7z и добавить путь к папке bin в Path.

После проделанной подготовки можно запускать uvicorn.
В cmd №1:
uvicorn main:app --reload

В cmd №2, где «file=@test1.mp3» — путь к файлу:

curl -X POST -F "file=@test1.mp3" -F "start=5" -F "end=10" http://127.0.0.1:8000/trim_audio --output trimmed_audio1.mp3

curl -X POST -F "file=@test2.wav" -F "start=5" -F "end=10" http://127.0.0.1:8000/trim_audio --output trimmed_audio2.mp3

curl -X POST -F "file=@test3.ogg" -F "start=5" -F "end=10" http://127.0.0.1:8000/trim_audio --output trimmed_audio3.mp3

Curl выдаст ошибку, если ввести криво путь к файлу.
Если ввести start>0, но меньше реального конца трека, и end ввести больше, чем реальное окончание трека, ошибки не будет. Файл запишется до реального конца. Пример:
curl -X POST -F "file=@test1.mp3" -F "start=30" -F "end=5000" http://127.0.0.1:8000/trim_audio --output trimmed_audio.mp3

Если ввести start>реального конца трека и end ввести больше, чем реальное окончание трека,
ИЛИ
Если ввести start<0
ТО файл будет битый.
Пример к не надо:
curl -X POST -F "file=@test1.mp3" -F "start=3000" -F "end=5000" http://127.0.0.1:8000/trim_audio --output trimmed_audio.mp3
Пример к не надо:
curl -X POST -F "file=@test1.mp3" -F "start=-3000" -F "end=10" http://127.0.0.1:8000/trim_audio --output trimmed_audio.mp3

Если ввести start>0, но меньше реального конца трека, и end<0, отсчет отрезки конца будет происходить с конца — справа налево. Пример:
curl -X POST -F "file=@test1.mp3" -F "start=0" -F "end=-90" http://127.0.0.1:8000/trim_audio --output trimmed_audio.mp3

ТЕСТИРОВАНИЕ ВЗАИМОДЕЙСТВИЯ С ВИДЕО НЕ ПРОВОДИЛОСЬ
пример для curl
curl -X POST -F "audio_file=@/путь/к/аудиофайлу.mp3" -F "image_file=@/путь/к/изображению.png" http://127.0.0.1:8000/create_video --output output.mp4

curl -X POST -F "audio_file=@test1.mp3" -F "image_file=@VK logo.png" http://127.0.0.1:8000/create_video --output output.mp4


curl -X POST -F "file=@test1.mp3" -F "start=5" -F "end=65" http://127.0.0.1:8000/trim_audio --output trimmed_audio1.mp3
curl -X POST -F "audio_file=@trimmed_audio1.mp3" -F "image_file=@VK logo.png" http://127.0.0.1:8000/create_video --output output.mp4
