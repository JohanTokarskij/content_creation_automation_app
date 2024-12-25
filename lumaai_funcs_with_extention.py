import os
import time
import requests
from dotenv import load_dotenv
from lumaai import LumaAI
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips, vfx

load_dotenv()
LUMAAI_API_KEY = os.getenv('LUMAAI_API_KEY')


def _poll_generation(client, generation_id, max_retries=3):
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


def _download_luma_video(generation, output_path):
    video_url = generation.assets.video
    response = requests.get(video_url, stream=True)
    response.raise_for_status()
    with open(output_path, 'wb') as file:
        for chunk in response.iter_content(chunk_size=1024*1024):
            if chunk:
                file.write(chunk)
    print(f"File downloaded as {output_path}")


def generate_luma_video(prompt, aspect_ratio="9:16", max_retries=3):
    client = LumaAI(auth_token=LUMAAI_API_KEY)
    retries = 0
    while retries < max_retries:
        try:
            generation = client.generations.create(prompt=prompt, aspect_ratio=aspect_ratio)
            generation = _poll_generation(client, generation.id, max_retries=max_retries)
            return generation
        except Exception as e:
            retries += 1
            print(f"LumaAI generation attempt {retries} failed: {e}")
            if retries == max_retries:
                print("Max retries reached. Generation failed.")
                return None
    return None


def extend_luma_video(prompt, base_generation_id, aspect_ratio="9:16", max_retries=3):
    client = LumaAI(auth_token=LUMAAI_API_KEY)
    retries = 0
    while retries < max_retries:
        try:
            generation = client.generations.create(
                prompt=prompt,
                aspect_ratio=aspect_ratio,
                keyframes={
                    "frame0": {
                        "type": "generation",
                        "id": base_generation_id
                    }
                }
            )
            generation = _poll_generation(client, generation.id, max_retries=max_retries)
            return generation
        except Exception as e:
            retries += 1
            print(f"LumaAI extend attempt {retries} failed: {e}")
            if retries == max_retries:
                print("Max retries reached. Extension failed.")
                return None
    return None


def process_videos_luma(scripts, audio_dir, video_output_dir, max_retries=3):
    if not os.path.exists(video_output_dir):
        os.makedirs(video_output_dir)
    temp_folder = 'temp'
    temp_video_dir = os.path.join(temp_folder, 'video')
    if not os.path.exists(temp_video_dir):
        os.makedirs(temp_video_dir)

    final_clips = []
    video_clips_to_close = []
    audio_clips_to_close = []

    for idx, script in enumerate(scripts):
        scene_number = idx + 1
        audio_path = os.path.join(audio_dir, f'scene_{scene_number}.mp3')
        if not os.path.exists(audio_path):
            print(f"Audio file {audio_path} does not exist. Skipping scene {scene_number}.")
            continue

        try:
            audio_clip = AudioFileClip(audio_path)
            audio_duration = audio_clip.duration
        except Exception as e:
            print(f"Error loading audio file {audio_path}: {e}")
            continue

        print(f"Processing scene {scene_number}:")
        print(f" - Audio duration: {audio_duration:.2f} seconds")

        # Calculate how many 5-second increments we need
        clip_count = max(1, int((audio_duration // 5) + 1)) if audio_duration > 5 else 1

        # First call: generate a 5s video
        generation = generate_luma_video(prompt=script, aspect_ratio="9:16", max_retries=max_retries)
        if not generation:
            print(f"Failed to generate initial Luma video for scene {scene_number}.")
            audio_clip.close()
            continue

        last_generation_id = generation.id

        # If we need more than one 5s chunk, keep extending
        for _ in range(clip_count - 1):
            generation = extend_luma_video(script, base_generation_id=last_generation_id, aspect_ratio="9:16", max_retries=max_retries)
            if not generation:
                print(f"Failed to extend Luma video for scene {scene_number}.")
                audio_clip.close()
                last_generation_id = None
                break
            last_generation_id = generation.id

        if not last_generation_id:
            continue

        # Download the final extended video
        final_video_path = os.path.join(temp_video_dir, f'scene_{scene_number}_{last_generation_id}.mp4')
        _download_luma_video(generation, final_video_path)

        try:
            video_clip = VideoFileClip(final_video_path)
            video_duration = video_clip.duration
            if video_duration >= audio_duration:
                speed_factor = video_duration / audio_duration
                if abs(speed_factor - 1.0) < 0.1:
                    final_clip = video_clip.subclip(0, audio_duration)
                    print(f" - Trimmed final Luma clip from {video_duration:.2f} to {audio_duration:.2f}s")
                else:
                    final_clip = video_clip.fx(vfx.speedx, factor=speed_factor).subclip(0, audio_duration)
                    print(f" - Speed-adjusted final Luma clip by factor={speed_factor:.2f}")
            else:
                diff = abs(video_duration - audio_duration)
                if diff > 0.1:
                    speed_factor = video_duration / audio_duration
                    final_clip = video_clip.fx(vfx.speedx, factor=speed_factor).subclip(0, audio_duration)
                    print(f" - Slowed final Luma clip by factor={speed_factor:.2f}")
                else:
                    final_clip = video_clip.subclip(0, video_duration)
            final_clip = final_clip.set_audio(audio_clip)
            final_clips.append(final_clip)
            video_clips_to_close.append(video_clip)
            audio_clips_to_close.append(audio_clip)
        except Exception as e:
            print(f"Error processing Luma video for scene {scene_number}: {e}")
            video_clip.close()
            audio_clip.close()

    if final_clips:
        try:
            print("Concatenating all Luma scenes into final video...")
            temp_audio_path = os.path.join(temp_folder, 'temp_moviepy.mp4')
            final_video = concatenate_videoclips(final_clips, method="compose")
            output_path = os.path.join(video_output_dir, 'final_video_luma.mp4')
            final_video.write_videofile(output_path, codec='libx264', audio_codec='aac',
                                        temp_audiofile=temp_audio_path, remove_temp=True)
            print(f"Final concatenated Luma video saved to {output_path}")
            final_video.close()
            for clip in final_clips:
                clip.close()
            for vc in video_clips_to_close:
                vc.close()
            for ac in audio_clips_to_close:
                ac.close()
        except Exception as e:
            print(f"Error concatenating final Luma video: {e}")
    else:
        print("No final Luma clips to concatenate.")
