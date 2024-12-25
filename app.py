from flask import Flask, render_template, request, session, send_file
import os

from openai_funcs import (
    generate_video_topic,
    generate_script,
    generate_search_terms,
    generate_detailed_prompts,
    generate_video_title_and_hashtags
)
from elevenlabs_funcs import generate_audio_files_elevenlabs
from gtts_funcs import generate_audio_files_gtts
from pixabay_funcs import process_videos_pixabay
from pexels_funcs import process_videos_pexels
from storyblocks_funcs import process_videos_storyblocks
from lumaai_funcs import process_videos_luma
from youtube_funcs import upload_video
from helper_funcs import clear_files_in_folder, sanitize_filename_component, get_final_filename

app = Flask(__name__)
app.secret_key = "some_secret_key"

@app.route("/", methods=["GET"])
def index():
    os.makedirs('temp/video', exist_ok=True)
    os.makedirs('temp/audio', exist_ok=True)
    os.makedirs('output', exist_ok=True)
    return render_template("index.html")

@app.route("/generate_video", methods=["POST"])
def generate_video():
    audio_dir = os.path.join("temp", "audio")
    video_temp_dir = os.path.join("temp", "video")
    final_dir = "output"
    clear_files_in_folder(audio_dir)
    clear_files_in_folder(video_temp_dir)

    user_topic = request.form.get("user_topic", "").strip()
    user_script = request.form.get("user_script", "").strip()
    audio_source = request.form.get("audio_source", "gtts")
    video_source = request.form.get("video_source", "pixabay")
    upload_option = request.form.get("upload_option", "local")

    if user_script and not user_topic:
        main_topic = user_script
    elif user_topic and not user_script:
        main_topic = generate_video_topic(user_topic)
    elif user_topic and user_script:
        main_topic = user_script
    else:
        main_topic = generate_video_topic("Fun and lesser known facts")

    scripts = generate_script(main_topic, 20) or [main_topic]
    if not scripts:
        return render_template("index.html", result_message="No script generated.")

    title_and_hashtags = generate_video_title_and_hashtags(main_topic)
    video_title = title_and_hashtags.get("title", "NoTitle")
    hashtags = title_and_hashtags.get("hashtags", [])
    final_name = get_final_filename(audio_source, video_source, video_title)

    if audio_source == "elevenlabs":
        generate_audio_files_elevenlabs(scripts, audio_dir)
    else:
        generate_audio_files_gtts(scripts, audio_dir)

    final_path = os.path.join(final_dir, final_name)

    if video_source == "luma":
        detailed_prompts = generate_detailed_prompts(scripts)
        process_videos_luma(detailed_prompts, audio_dir, final_path)
    else:
        search_terms = generate_search_terms(main_topic, scripts)
        if video_source == "pexels":
            process_videos_pexels(scripts, search_terms, audio_dir, final_path)
        elif video_source == "storyblocks":
            process_videos_storyblocks(scripts, search_terms, audio_dir, final_path)
        elif video_source == "pixabay":
            process_videos_pixabay(scripts, search_terms, audio_dir, final_path)
        else:
            return render_template("index.html", result_message="Invalid video source selected.")

    if upload_option == "youtube":
        upload_video("token.json", "client_secret.json", final_path, video_title)

    clear_files_in_folder(audio_dir)
    clear_files_in_folder(video_temp_dir)

    return send_file(final_path, as_attachment=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(port=port, host='0.0.0.0')
