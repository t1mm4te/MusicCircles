from audio_receiver_utils import *
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response, StreamingResponse
from typing import Optional

app = FastAPI(title="Yandex Music API Wrapper")


@app.get("/search/")
async def search_tracks(query: str, limit: Optional[int] = 5):
    """
    Поиск треков по названию
    """
    try:
        tracks = find_tracks_by_name(query)
        if not tracks:
            raise HTTPException(status_code=404, detail="Треки не найдены")

        result = []
        for track in tracks[:limit]:
            result.append({
                "id": track.id,
                "title": track.title,
                "artists": [artist.name for artist in track.artists],
                "duration": track.duration_ms
                # noqa
            })

        return {"results": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/track/{track_id}/info")
async def track_info(track_id: str):
    """
    Получение полной информации о треке по его ID
    """
    try:
        track = get_track_info(track_id)
        if not track:
            raise HTTPException(status_code=404, detail="Трек не найден")

        return {
            "title": track.title,
            "artists": [{"id": artist.id, "name": artist.name} for artist in track.artists],
            "duration": track.duration_ms
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/track/{track_id}/cover")
async def get_track_cover_image(track_id: str):
    """
    Получение обложки трека
    """
    try:
        track = client.tracks(track_id)[0]
        cover_bytes = get_track_cover(track)
        if not cover_bytes:
            raise HTTPException(status_code=404, detail="Обложка не найдена")

        return Response(content=cover_bytes, media_type="image/jpeg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/track/{track_id}/stream")
async def stream_track(track_id: str):
    """
    Потоковое воспроизведение трека
    """
    try:
        track = client.tracks(track_id)[0]
        track_bytes = get_track(track)
        if not track_bytes:
            raise HTTPException(status_code=404, detail="Трек не найден")

        return StreamingResponse(
            iter([track_bytes]),
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": f"inline; filename={track.title}.mp3",
                "Content-Length": str(len(track_bytes))
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)
