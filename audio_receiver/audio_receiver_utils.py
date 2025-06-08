import os
from dotenv import load_dotenv
from yandex_music import ClientAsync, Track

load_dotenv()
YANDEX_MUSIC_TOKEN = os.getenv('YANDEX_MUSIC_API_TOKEN')
if not YANDEX_MUSIC_TOKEN:
    raise ValueError("Не найден YANDEX_MUSIC_API_TOKEN в .env файле")
client = None


async def init_client():
    global client
    client = await ClientAsync(YANDEX_MUSIC_TOKEN).init()


async def find_tracks_by_name(search_query: str):
    found_tracks = await client.search(search_query, type_='track')
    return found_tracks.tracks.results if found_tracks.tracks is not None else None


async def get_track_info(track_id: int | str):
    tracks = await client.tracks(track_id)
    return tracks[0]


async def get_track_cover(track: Track):
    cover = await track.download_cover_bytes_async(size='200x200')
    return cover


async def get_track_bytes(track: Track):
    download_info_list = await track.get_download_info_async()
    if download_info_list is None:
        return None
    download_info = download_info_list[0]
    track_source = await track.download_bytes_async(download_info.codec, download_info.bitrate_in_kbps)
    return track_source
