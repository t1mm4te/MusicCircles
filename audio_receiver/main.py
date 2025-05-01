from audio_receiver_utils import *


if __name__ == '__main__':
    print("Hello world! It's yandex_music_utils test")
    bad_request = 'afafadfdfa21424easdf'
    good_request = 'booker по шаблону'
    searched_track = find_tracks_by_name(bad_request)
    if searched_track is None:
        print(f'track {bad_request} is not found')
    searched_track = find_tracks_by_name(good_request)[0]
    cover = get_track_cover(searched_track)
    track = get_track(searched_track)

    with open('audiotrack1.mp3', 'wb') as track_file, open('cover1.png', 'wb') as cover_file:
        cover_file.write(cover)
        track_file.write(track)
    print('Test is end, check files')