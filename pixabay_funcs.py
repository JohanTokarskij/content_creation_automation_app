import os
from urllib.parse import urlencode

import requests
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips
from moviepy.video.fx.all import crop

from helper_funcs import configure_moviepy


def search_videos_pixabay(search_term, safesearch=True, api_key=None):
    """
    Search for videos on Pixabay by 'search_term'. Returns a list of video data dicts.
    """
    base_url = 'https://pixabay.com/api/videos/'
    params = {
        'key': api_key,
        'q': search_term,
        'video_type': 'film',
        'safesearch': str(safesearch).lower(),
        'per_page': 10
    }
    try:
        url = f"{base_url}?{urlencode(params)}"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return data.get('hits', [])
    except Exception as e:
        print(f"Error searching Pixabay videos: {e}")
        return []


def download_video_pixabay(video_data, output_path):
    """
    Downloads a single Pixabay video to 'output_path'.
    """
    try:
        medium_info = video_data.get('videos', {}).get('medium', {})
        video_url = medium_info.get('url')
        if not video_url:
            print("No video URL found in video data.")
            return False

        resp = requests.get(video_url, stream=True)
        resp.raise_for_status()
        with open(output_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
        print(f"Pixabay video downloaded to {output_path}")
        return True
    except Exception as e:
        print(f"Error downloading Pixabay video: {e}")
        return False


def process_videos_pixabay(scripts, search_terms, audio_dir, output_path, api_key=None):
    """
    Creates a single final video at 'output_path' from the given scripts/search terms.
    """
    configure_moviepy()
    temp_folder = 'temp'
    temp_video_dir = os.path.join(temp_folder, 'video')
    os.makedirs(temp_video_dir, exist_ok=True)

    final_clips = []
    video_clips_to_close = []
    audio_clips_to_close = []

    for idx, script in enumerate(scripts, start=1):
        audio_file = os.path.join(audio_dir, f"scene_{idx}.mp3")
        if not os.path.exists(audio_file):
            print(f"No audio file for scene {idx}. Skipping.")
            continue

        try:
            audio_clip = AudioFileClip(audio_file)
            audio_duration = audio_clip.duration
        except Exception as e:
            print(f"Error loading audio for scene {idx}: {e}")
            continue

        if idx - 1 < len(search_terms):
            search_term = search_terms[idx - 1]
        else:
            search_term = "generic"

        hits = search_videos_pixabay(search_term, safesearch=True, api_key=api_key)
        suitable_hits = [h for h in hits if h.get('duration', 0) >= audio_duration]
        if not suitable_hits:
            print(f"No suitable Pixabay videos found for scene {idx}.")
            audio_clip.close()
            continue

        video_data = suitable_hits[0]
        downloaded_path = os.path.join(temp_video_dir, f"scene_{idx}.mp4")
        if not download_video_pixabay(video_data, downloaded_path):
            audio_clip.close()
            print(f"Failed to download scene {idx} from Pixabay.")
            continue

        try:
            video_clip = VideoFileClip(downloaded_path)
            if video_clip.duration >= audio_duration:
                final_clip = video_clip.subclip(0, audio_duration)
            else:
                print(f"Video shorter than audio for scene {idx}.")
                final_clip = video_clip  # or skip entirely

            aspect_ratio = final_clip.w / final_clip.h
            # Crop to 9:16
            if aspect_ratio < 0.5625:
                new_height = final_clip.w / 0.5625
                final_clip = crop(
                    final_clip,
                    width=final_clip.w,
                    height=new_height,
                    x_center=final_clip.w / 2,
                    y_center=final_clip.h / 2
                )
            else:
                new_width = 0.5625 * final_clip.h
                final_clip = crop(
                    final_clip,
                    width=new_width,
                    height=final_clip.h,
                    x_center=final_clip.w / 2,
                    y_center=final_clip.h / 2
                )

            final_clip = final_clip.resize((1080, 1920)).set_audio(audio_clip)
            final_clips.append(final_clip)
            video_clips_to_close.append(video_clip)
            audio_clips_to_close.append(audio_clip)
            print(f"Scene {idx} processed.")
        except Exception as e:
            print(f"Error processing Pixabay scene {idx}: {e}")
            audio_clip.close()
            video_clip.close()

    if final_clips:
        try:
            print("Concatenating all Pixabay clips into the final video...")
            temp_moviepy_path = os.path.join(temp_folder, 'temp_moviepy.mp4')
            final_video = concatenate_videoclips(final_clips, method="compose")
            final_video.write_videofile(
                output_path,
                codec="libx264",
                audio_codec="aac",
                temp_audiofile=temp_moviepy_path,
                remove_temp=True
            )
            final_video.close()
            print(f"Final Pixabay video saved to {output_path}")
        except Exception as e:
            print(f"Error finalizing Pixabay video: {e}")
    else:
        print("No final clips to concatenate.")

    for c in final_clips:
        c.close()
    for vc in video_clips_to_close:
        vc.close()
    for ac in audio_clips_to_close:
        ac.close()
