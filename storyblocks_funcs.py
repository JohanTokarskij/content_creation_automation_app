import os
import time
import hmac
import hashlib
from urllib.parse import urlencode
from typing import Optional, List, Dict, Any

import requests
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips
from moviepy.video.fx.all import crop

from helper_funcs import configure_moviepy


BASE_URL = "https://api.storyblocks.com"


def generate_hmac(private_key: str, resource: str, expires: str) -> str:
    """
    Generate an HMAC signature using the provided private key, resource, and expiration time.

    Args:
        private_key (str): The private key used for HMAC generation.
        resource (str): The resource string for which the HMAC is generated.
        expires (str): The expiration timestamp as a string.

    Returns:
        str: The hexadecimal representation of the HMAC signature.
    """
    message = private_key + expires
    hmac_builder = hmac.new(
        bytearray(message, 'utf-8'),
        resource.encode('utf-8'),
        hashlib.sha256
    )
    return hmac_builder.hexdigest()


def search_videos_storyblocks(
    search_term: str,
    min_duration: int,
    private_api_key: str,
    public_api_key: str
) -> List[Dict[str, Any]]:
    """
    Search Storyblocks for videos matching the given keyword. Optionally filter by minimum duration.

    Args:
        search_term (str): The keyword to search for in Storyblocks.
        min_duration (int, optional): Minimum duration of videos in seconds. Defaults to None.
        per_page (int, optional): Number of results per page. Defaults to 10.
        private_api_key (str): Private API key for authentication.
        public_api_key (str): Public API key for authentication.

    Returns:
        List[Dict[str, Any]]: A list of dictionaries containing video information.
    """
    search_resource = "/api/v2/videos/search"
    expires = str(int(time.time()) + 3600)
    hmac_sig = generate_hmac(private_api_key, search_resource, expires)

    params = {
        "APIKEY": public_api_key,
        "EXPIRES": expires,
        "HMAC": hmac_sig,
        "keywords": search_term,
        "content_type": "all",
        "sort_by": "most_relevant",
        "sort_order": "DESC",
        "project_id": hmac_sig,
        "user_id": f"johtok{hmac_sig}"
    }
    try:
        response = requests.get(BASE_URL + search_resource, params=params)
        response.raise_for_status()
        data = response.json()
        hits = data.get("results", [])
        if min_duration is not None:
            hits = [hit for hit in hits if hit.get("duration", 0) >= min_duration]
        return hits
    except Exception as e:
        print(f"Error searching Storyblocks: {e}")
        return []


def download_video_storyblocks(
    video_id: str,
    output_path: str,
    private_api_key: str,
    public_api_key: str
) -> bool:
    """
    Download a Storyblocks video by its video ID and save it to the specified output path.

    Args:
        video_id (str): The unique identifier of the Storyblocks video to download.
        output_path (str): The file system path where the downloaded video will be saved.
        private_api_key (str): Private API key for authentication.
        public_api_key (str): Public API key for authentication.

    Returns:
        bool: True if the download was successful, False otherwise.
    """
    download_resource = f"/api/v2/videos/stock-item/download/{video_id}"
    expires = str(int(time.time()) + 3600)
    hmac_sig = generate_hmac(private_api_key, download_resource, expires)

    params = {
        "APIKEY": public_api_key,
        "EXPIRES": expires,
        "HMAC": hmac_sig,
        "project_id": hmac_sig,
        "user_id": f"johtok{hmac_sig}"
    }

    try:
        response = requests.get(BASE_URL + download_resource, params=params)
        response.raise_for_status()
        data = response.json()

        mp4_formats = data.get("MP4", {})
        if mp4_formats:
            def resolution_key(res_key):
                try:
                    return int(res_key.strip("_p"))
                except:
                    return 0
            sorted_keys = sorted(mp4_formats.keys(), key=resolution_key, reverse=True)
            video_url = mp4_formats[sorted_keys[0]]
        else:
            mov_formats = data.get("MOV", {})
            if mov_formats:
                sorted_keys = sorted(mov_formats.keys(), key=lambda k: int(k.strip("_p")), reverse=True)
                video_url = mov_formats[sorted_keys[0]]
            else:
                print("No downloadable video formats found.")
                return False

        if not video_url:
            print("No video URL found in download response.")
            return False

        resp = requests.get(video_url, stream=True)
        resp.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024*1024):
                if chunk:
                    f.write(chunk)
        print(f"Storyblocks video downloaded to {output_path}")
        return True
    except Exception as e:
        print(f"Error downloading Storyblocks video {video_id}: {e}")
        return False


def process_videos_storyblocks(
    scripts: List[str],
    search_terms: List[str],
    audio_dir: str,
    output_path: str,
    private_api_key: str,
    public_api_key: str
) -> None:
    """
    Create a final video by processing multiple Storyblocks videos and corresponding audio files.

    This function searches for videos on Storyblocks based on the provided search terms and scripts,
    downloads the selected videos, synchronizes them with audio files, and concatenates them into
    a single output video.

    Args:
        scripts (List[str]): A list of script texts for each scene.
        search_terms (List[str]): A list of search terms corresponding to each script.
        audio_dir (str): Directory containing audio files for each scene.
        output_path (str): The file system path where the final video will be saved.
        private_api_key (str): Private API key for authentication.
        public_api_key (str): Public API key for authentication.
    """
    configure_moviepy()
    temp_folder = "temp"
    temp_video_dir = os.path.join(temp_folder, "video")
    os.makedirs(temp_video_dir, exist_ok=True)

    final_clips = []
    video_clips_to_close = []
    audio_clips_to_close = []

    for idx, script in enumerate(scripts, start=1):
        audio_file = os.path.join(audio_dir, f"scene_{idx}.mp3")
        if not os.path.exists(audio_file):
            print(f"No audio file for scene {idx}.")
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

        min_duration = int(audio_duration) + 1
        hits = search_videos_storyblocks(search_term, 
                                         min_duration=min_duration,
                                         private_api_key=private_api_key, 
                                         public_api_key=public_api_key)
        suitable_hits = [h for h in hits if h.get("duration", 0) >= audio_duration]
        if not suitable_hits:
            print(f"No suitable Storyblocks video found for scene {idx}.")
            audio_clip.close()
            continue

        chosen_hit = suitable_hits[0]
        video_id = chosen_hit.get("id")
        if not video_id:
            print("No video ID in chosen Storyblocks hit.")
            audio_clip.close()
            continue

        downloaded_path = os.path.join(temp_video_dir, f"scene_{idx}.mp4")
        if not download_video_storyblocks(video_id, 
                                          downloaded_path,
                                          private_api_key=private_api_key, 
                                          public_api_key=public_api_key):
            print(f"Failed to download storyblocks scene {idx}.")
            audio_clip.close()
            continue

        try:
            video_clip = VideoFileClip(downloaded_path)
            if video_clip.duration >= audio_duration:
                final_clip = video_clip.subclip(0, audio_duration)
            else:
                print(f"Video shorter than audio for scene {idx}.")
                final_clip = video_clip  # or skip entirely

            aspect_ratio = final_clip.w / final_clip.h
            if aspect_ratio < 0.5625:
                new_height = final_clip.w / 0.5625
                final_clip = crop(final_clip, width=final_clip.w, height=new_height,
                                  x_center=final_clip.w/2, y_center=final_clip.h/2)
            else:
                new_width = 0.5625 * final_clip.h
                final_clip = crop(final_clip, width=new_width, height=final_clip.h,
                                  x_center=final_clip.w/2, y_center=final_clip.h/2)

            final_clip = final_clip.resize((1080, 1920)).set_audio(audio_clip)
            final_clips.append(final_clip)
            video_clips_to_close.append(video_clip)
            audio_clips_to_close.append(audio_clip)
            print(f"Scene {idx} processed successfully.")
        except Exception as e:
            print(f"Error processing Storyblocks scene {idx}: {e}")
            audio_clip.close()
            video_clip.close()

    if final_clips:
        try:
            print("Concatenating all Storyblocks scenes into final video...")
            temp_moviepy_path = os.path.join(temp_folder, "temp_moviepy.mp4")
            final_video = concatenate_videoclips(final_clips, method="compose")
            final_video.write_videofile(
                output_path,
                codec="libx264",
                audio_codec="aac",
                temp_audiofile=temp_moviepy_path,
                remove_temp=True
            )
            final_video.close()
            print(f"Final Storyblocks video saved to {output_path}")
        except Exception as e:
            print(f"Error finalizing Storyblocks video: {e}")
    else:
        print("No final clips to concatenate.")

    for clip in final_clips:
        clip.close()
    for vc in video_clips_to_close:
        vc.close()
    for ac in audio_clips_to_close:
        ac.close()