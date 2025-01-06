import os
from urllib.parse import urlencode
from typing import List, Dict, Any

import requests
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips
from moviepy.video.fx.all import crop

from helper_funcs import configure_moviepy


def search_videos_pixabay(
    search_term: str,
    safesearch: bool,
    api_key: str
) -> List[Dict[str, Any]]:
    """
    Search for videos on Pixabay using the specified search term.

    This function queries the Pixabay API for videos that match the given keyword. It
    allows for safe search filtering and limits the number of results per page.

    Args:
        search_term (str): The keyword to search for in Pixabay videos.
        safesearch (bool): Enable or disable safe search. Defaults to True.
        api_key (str): The Pixabay API key for authentication.

    Returns:
        List[Dict[str, Any]]: A list of dictionaries containing video data.
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


def download_video_pixabay(
    video_data: Dict[str, Any],
    output_path: str
) -> bool:
    """
    Download a single Pixabay video to the specified output path.

    This function retrieves the video URL from the provided video data and downloads
    the video file, saving it to the designated location on the local file system.

    Args:
        video_data (Dict[str, Any]): A dictionary containing information about the Pixabay video.
        output_path (str): The file system path where the downloaded video will be saved.

    Returns:
        bool: True if the download was successful, False otherwise.
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


def process_videos_pixabay(
    scripts: List[str],
    search_terms: List[str],
    audio_dir: str,
    output_path: str,
    api_key: str
) -> None:
    """
    Create a final video by processing multiple Pixabay videos and corresponding audio files.

    This function performs the following steps:
    1. Configures MoviePy settings.
    2. Searches for Pixabay videos based on provided search terms and scripts.
    3. Downloads selected videos.
    4. Synchronizes videos with corresponding audio files.
    5. Concatenates all processed video clips into a single final output video.

    Args:
        scripts (List[str]): A list of script texts for each scene.
        search_terms (List[str]): A list of search terms corresponding to each script.
        audio_dir (str): Directory containing audio files for each scene.
        output_path (str): The file system path where the final video will be saved.
        api_key (str): The Pixabay API key for authentication.
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
