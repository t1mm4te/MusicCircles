import os
from dotenv import load_dotenv
from yandex_music import Client, Track

load_dotenv()
YANDEX_MUSIC_TOKEN = os.getenv('YANDEX_MUSIC_API_TOKEN')
if not YANDEX_MUSIC_TOKEN:
    raise ValueError("Не найден YANDEX_MUSIC_API_TOKEN в .env файле")
client = Client(YANDEX_MUSIC_TOKEN).init()


def find_tracks_by_name(search_query: str) -> list | None:
    found_tracks = client.search(search_query, type_='track').tracks
    return found_tracks.results if found_tracks is not None else None


def get_track_info(track_id: int | str):
    return client.tracks(track_id)[0]


def get_track_cover(track: Track):
    cover = track.download_cover_bytes(size='200x200')
    return cover


def get_track(track: Track):
    download_info = track.get_download_info()
    if download_info is None:
        return None
    download_info = download_info[0]
    track_source = track.download_bytes(download_info['codec'], download_info['bitrate_in_kbps'])
    return track_source
