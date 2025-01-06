import os
import time
from typing import List, Dict, Optional, Any, Union

import requests
from lumaai import LumaAI
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips, vfx


def poll_generation(client: LumaAI, generation_id: str, max_retries: int = 3) -> Any:
    """
    Polls the LumaAI generation status until it is completed or fails.
    
    This function repeatedly checks the status of a video generation request. If the generation
    is completed, it returns the generation object. If it fails, it retries up to a specified
    number of times before raising an error.
    
    Args:
        client (LumaAI): The LumaAI client instance used to interact with the API.
        generation_id (str): The unique identifier of the generation request.
        max_retries (int, optional): The maximum number of retries allowed if the generation fails. Defaults to 3.
    
    Returns:
        Any: The completed generation object.
    
    Raises:
        RuntimeError: If the generation fails after the maximum number of retries.
    """
    retries = 0
    while True:
        generation = client.generations.get(id=generation_id)
        if generation.state == "completed":
            return generation
        elif generation.state == "failed":
            retries += 1
            if retries >= max_retries:
                raise RuntimeError(f"Generation failed: {generation.failure_reason}")
            else:
                print(f"Generation failed, retrying... attempt {retries}/{max_retries}")
                time.sleep(3)
                continue
        print("Dreaming...")
        time.sleep(3)


def download_luma_video(generation: Any, output_path: str) -> bool:
    """
    Downloads the generated LumaAI video to the specified output path.
    
    This function retrieves the video URL from the generation object and downloads the video
    file, saving it to the designated location on the local file system.
    
    Args:
        generation (Any): The generation object containing information about the video.
        output_path (str): The file system path where the downloaded video will be saved.
    
    Returns:
        bool: True if the download was successful, False otherwise.
    """
    video_url = generation.assets.video
    response = requests.get(video_url, stream=True)
    response.raise_for_status()
    with open(output_path, 'wb') as file:
        for chunk in response.iter_content(chunk_size=1024*1024):
            if chunk:
                file.write(chunk)
    print(f"File downloaded as {output_path}")


def generate_luma_video(
    prompt: str,
    aspect_ratio: str = "9:16",
    max_retries: int = 3,
    api_key: str = None
) -> Optional[Any]:
    """
    Generates a LumaAI video based on the provided prompt.
    
    This function sends a prompt to the LumaAI API to generate a video clip with the specified
    aspect ratio. It handles retries in case of failures and returns the generation object upon success.
    
    Args:
        prompt (str): The text prompt describing the desired video content.
        aspect_ratio (str, optional): The aspect ratio for the generated video (e.g., "9:16"). Defaults to "9:16".
        max_retries (int, optional): The maximum number of retries allowed if the generation fails. Defaults to 3.
        api_key (str): The API key for authenticating with LumaAI. Defaults to None.
    
    Returns:
        Optional[Any]: The completed generation object if successful, or None if all retries fail.
    """
    client = LumaAI(auth_token=api_key)
    retries = 0
    while retries < max_retries:
        try:
            generation = client.generations.create(prompt=prompt, aspect_ratio=aspect_ratio)
            generation = poll_generation(client, generation.id, max_retries=max_retries)
            return generation
        except Exception as e:
            retries += 1
            print(f"LumaAI generation attempt {retries} failed: {e}")
            if retries == max_retries:
                print("Max retries reached. Generation failed.")
                return None
    return None


def process_videos_luma(detailed_prompts, audio_dir, output_path, max_retries=3, api_key=None):
    """
    Generates a single final Luma video at 'output_path' using a list of detailed prompts.
    We create exactly one ~5s Luma clip per scene, then speed up or slow it down to match
    the entire audio duration (no extra clips, no multi-clip logic).
    """
    temp_folder = 'temp'
    temp_video_dir = os.path.join(temp_folder, 'video')
    os.makedirs(temp_video_dir, exist_ok=True)

    final_clips = []
    video_clips_to_close = []
    audio_clips_to_close = []

    for idx, prompt in enumerate(detailed_prompts, start=1):
        audio_file = os.path.join(audio_dir, f"scene_{idx}.mp3")
        if not os.path.exists(audio_file):
            print(f"Audio file {audio_file} does not exist. Skipping scene {idx}.")
            continue

        try:
            audio_clip = AudioFileClip(audio_file)
            audio_duration = audio_clip.duration
        except Exception as e:
            print(f"Error loading audio file {audio_file}: {e}")
            continue

        print(f"\nProcessing scene {idx}: Audio duration = {audio_duration:.2f}s")

        # Generate exactly one Luma clip
        generation = generate_luma_video(prompt, 
                                         aspect_ratio="9:16", 
                                         max_retries=max_retries,
                                         api_key=api_key)
        if not generation:
            print(f"Failed to generate Luma clip for scene {idx}.")
            audio_clip.close()
            continue

        # Download the ~5s Luma clip
        downloaded_path = os.path.join(temp_video_dir, f"scene_{idx}_{generation.id}.mp4")
        download_luma_video(generation, downloaded_path)

        try:
            luma_clip = VideoFileClip(downloaded_path)
            original_luma_duration = luma_clip.duration
            print(f" - Original Luma clip duration: {original_luma_duration:.2f}s")

            # Calculate speed factor so final matches audio length
            speed_factor = original_luma_duration / audio_duration
            # Speed up or slow down the Luma clip
            final_clip = luma_clip.fx(vfx.speedx, factor=speed_factor)
            # Then subclip to exactly the audio length
            final_clip = final_clip.subclip(0, audio_duration)
            final_clip = final_clip.set_audio(audio_clip)

            final_clips.append(final_clip)
            video_clips_to_close.append(luma_clip)
            audio_clips_to_close.append(audio_clip)
        except Exception as e:
            print(f"Error processing Luma clip for scene {idx}: {e}")
            audio_clip.close()
            if 'luma_clip' in locals():
                luma_clip.close()

    if final_clips:
        try:
            print("\nConcatenating all Luma scenes into final video...")
            temp_audio_file = os.path.join(temp_folder, 'temp_moviepy.mp4')
            final_video = concatenate_videoclips(final_clips, method="compose")
            final_video.write_videofile(output_path, codec='libx264', audio_codec='aac',
                                        temp_audiofile=temp_audio_file, remove_temp=True)
            final_video.close()
            print(f"Final Luma video written to {output_path}")

            for clip in final_clips:
                clip.close()
            for vc in video_clips_to_close:
                vc.close()
            for ac in audio_clips_to_close:
                ac.close()

        except Exception as e:
            print(f"Error finalizing Luma video: {e}")
    else:
        print("No final Luma clips to concatenate.")
