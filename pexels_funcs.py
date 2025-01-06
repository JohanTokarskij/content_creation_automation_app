import os

import requests
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips
from moviepy.video.fx.all import crop
from helper_funcs import configure_moviepy
from typing import List, Dict, Any, Optional


def search_videos_pexels(
    search_term: str,
    min_duration: int,
    api_key: str
) -> List[Dict[str, Any]]:
    """
    Search for videos on Pexels using the specified search term.

    This function queries the Pexels API for videos that match the given keyword. It
    allows for filtering by minimum duration and limits the number of results per page.

    Args:
        search_term (str): The keyword to search for in Pexels videos.
        min_duration (int): Minimum duration of videos in seconds.
        api_key (str): The Pexels API key for authentication.

    Returns:
        List[Dict[str, Any]]: A list of dictionaries containing video data.
    """
    base_url = "https://api.pexels.com/videos/search"
    params = {
        "query": search_term,
        "per_page": 10
    }
    try:
        response = requests.get(
            base_url, 
            headers={"Authorization": api_key}, 
            params=params
        )
        response.raise_for_status()
        data = response.json()
        hits = data.get("videos", [])
        if min_duration is not None:
            hits = [h for h in hits if h.get("duration", 0) >= min_duration]
        return hits
    except Exception as e:
        print(f"Error searching Pexels videos: {e}")
        return []


def download_video_pexels(
    video_data: Dict[str, Any],
    output_path: str
) -> bool:
    """
    Download a single Pexels video to the specified output path.

    This function retrieves the video URL from the provided video data and downloads
    the video file, saving it to the designated location on the local file system.

    Args:
        video_data (Dict[str, Any]): A dictionary containing information about the Pexels video.
        output_path (str): The file system path where the downloaded video will be saved.

    Returns:
        bool: True if the download was successful, False otherwise.
    """
    try:
        video_files = video_data.get("video_files", [])
        video_files.sort(
            key=lambda vf: vf.get("width", 0) * vf.get("height", 0), 
            reverse=True
        )
        if not video_files:
            print("No video files in Pexels response.")
            return False
        
        best_file = video_files[0]
        video_url = best_file.get("link")
        if not video_url:
            print("No video URL found in the selected video file.")
            return False

        resp = requests.get(video_url, stream=True)
        resp.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
        print(f"Pexels video downloaded to {output_path}")
        return True
    except Exception as e:
        print(f"Error downloading Pexels video: {e}")
        return False


def process_videos_pexels(
    scripts: List[str],
    search_terms: List[str],
    audio_dir: str,
    output_path: str,
    api_key: str
) -> None:
    """
    Create a final video by processing multiple Pexels videos and corresponding audio files.

    This function performs the following steps:
    1. Configures MoviePy settings.
    2. Searches for Pexels videos based on provided search terms and scripts.
    3. Downloads selected videos.
    4. Synchronizes videos with corresponding audio files.
    5. Concatenates all processed video clips into a single final output video.

    Args:
        scripts (List[str]): A list of script texts for each scene.
        search_terms (List[str]): A list of search terms corresponding to each script.
        audio_dir (str): Directory containing audio files for each scene.
        output_path (str): The file system path where the final video will be saved.
        api_key (str): The Pexels API key for authentication.
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
            print(f"Audio for scene {idx} not found. Skipping.")
            continue
        
        try:
            audio_clip = AudioFileClip(audio_file)
            audio_duration = audio_clip.duration
        except Exception as e:
            print(f"Error loading audio {audio_file}: {e}")
            continue
        
        if idx - 1 < len(search_terms):
            search_term = search_terms[idx - 1]
        else:
            search_term = "generic"  # fallback if not enough terms

        min_duration = int(audio_duration) + 1
        hits = search_videos_pexels(search_term, min_duration=min_duration, api_key=api_key)
        suitable_hits = [h for h in hits if h.get("duration", 0) >= audio_duration]
        if not suitable_hits:
            print(f"No suitable Pexels videos for scene {idx}.")
            audio_clip.close()
            continue

        video_data = suitable_hits[0]
        downloaded_path = os.path.join(temp_video_dir, f"scene_{idx}.mp4")
        if not download_video_pexels(video_data, downloaded_path):
            audio_clip.close()
            print(f"Failed to download scene {idx} from Pexels.")
            continue
        
        try:
            video_clip = VideoFileClip(downloaded_path)
            if video_clip.duration >= audio_duration:
                final_clip = video_clip.subclip(0, audio_duration)
            else:
                print(f"Scene {idx} video is shorter than audio.")
                final_clip = video_clip  # Or skip entirely

            # Crop/resize to 9:16
            aspect_ratio = final_clip.w / final_clip.h
            if aspect_ratio < 0.5625:  # narrower
                new_height = final_clip.w / 0.5625
                final_clip = crop(
                    final_clip, 
                    width=final_clip.w, 
                    height=new_height,
                    x_center=final_clip.w/2,
                    y_center=final_clip.h/2
                )
            else:  # wider
                new_width = 0.5625 * final_clip.h
                final_clip = crop(
                    final_clip,
                    width=new_width,
                    height=final_clip.h,
                    x_center=final_clip.w/2,
                    y_center=final_clip.h/2
                )
            
            final_clip = final_clip.resize((1080, 1920))
            final_clip = final_clip.set_audio(audio_clip)
            final_clips.append(final_clip)
            video_clips_to_close.append(video_clip)
            audio_clips_to_close.append(audio_clip)

            print(f"Scene {idx} processed.")
        except Exception as e:
            print(f"Error processing scene {idx}: {e}")
            audio_clip.close()
            if "video_clip" in locals():
                video_clip.close()

    if final_clips:
        try:
            print("Concatenating all Pexels clips into final video...")
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
            print(f"Final Pexels video written to {output_path}")
        except Exception as e:
            print(f"Error finalizing Pexels video: {e}")
    else:
        print("No final clips to concatenate.")

    for clip in final_clips:
        clip.close()
    for vc in video_clips_to_close:
        vc.close()
    for ac in audio_clips_to_close:
        ac.close()
