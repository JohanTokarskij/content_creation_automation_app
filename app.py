from flask import Flask, render_template, request, send_from_directory, redirect, url_for
import os
import threading


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
from helper_funcs import clear_files_in_folder, sanitize_filename_component, get_final_filename, custom_secure_filename

app = Flask(__name__)
app.secret_key = "some_secret_key"

# Define directories
AUDIO_DIR = os.path.join("temp", "audio")
VIDEO_TEMP_DIR = os.path.join("temp", "video")
FINAL_DIR = "output"

@app.route("/", methods=["GET"])
def index():
    os.makedirs(AUDIO_DIR, exist_ok=True)
    os.makedirs(VIDEO_TEMP_DIR, exist_ok=True)
    os.makedirs(FINAL_DIR, exist_ok=True)
    return render_template("index.html")

@app.route("/generate_video", methods=["POST"])
def generate_video():
    # Clear temporary directories
    clear_files_in_folder(AUDIO_DIR)
    clear_files_in_folder(VIDEO_TEMP_DIR)

    # Get form data
    user_topic = request.form.get("user_topic", "").strip()
    user_script = request.form.get("user_script", "").strip()
    audio_source = request.form.get("audio_source", "gtts")
    video_source = request.form.get("video_source", "pixabay")
    upload_option = request.form.get("upload_option", "local")

    # Determine main topic
    if user_script and not user_topic:
        main_topic = user_script
    elif user_topic and not user_script:
        main_topic = generate_video_topic(user_topic)
    elif user_topic and user_script:
        main_topic = user_script
    else:
        main_topic = generate_video_topic("Fun and lesser known facts")

    # Generate scripts
    scripts = generate_script(main_topic, 20) or [main_topic]
    if not scripts:
        return render_template("index.html", result_message="No script generated.")

    # Generate title and hashtags
    title_and_hashtags = generate_video_title_and_hashtags(main_topic)
    video_title = title_and_hashtags.get("title", "NoTitle")
    hashtags = title_and_hashtags.get("hashtags", [])
    
    # Generate final filename
    final_name = get_final_filename(audio_source, video_source, video_title)
    
    # Sanitize the filename using the custom function
    secure_name = custom_secure_filename(final_name)
    
    # Generate audio
    if audio_source == "elevenlabs":
        generate_audio_files_elevenlabs(scripts, AUDIO_DIR)
    else:
        generate_audio_files_gtts(scripts, AUDIO_DIR)

    # Define final video path using the sanitized filename
    final_path = os.path.join(FINAL_DIR, secure_name)

    # Generate video
    if video_source == "luma":
        detailed_prompts = generate_detailed_prompts(scripts)
        process_videos_luma(detailed_prompts, AUDIO_DIR, final_path)
    else:
        search_terms = generate_search_terms(main_topic, scripts)
        if video_source == "pexels":
            process_videos_pexels(scripts, search_terms, AUDIO_DIR, final_path)
        elif video_source == "storyblocks":
            process_videos_storyblocks(scripts, search_terms, AUDIO_DIR, final_path)
        elif video_source == "pixabay":
            process_videos_pixabay(scripts, search_terms, AUDIO_DIR, final_path)
        else:
            return render_template("index.html", result_message="Invalid video source selected.")

    # Upload to YouTube if selected
    if upload_option == "youtube":
        upload_video("token.json", "client_secret.json", final_path, video_title)

    # Clear temporary directories
    clear_files_in_folder(AUDIO_DIR)
    clear_files_in_folder(VIDEO_TEMP_DIR)

    # Define download URL using the sanitized filename
    download_url = url_for('download_file', filename=secure_name)

    # Start a timer to delete the file after 1 minute
    timer = threading.Timer(60, delete_file, args=[secure_name])
    timer.start()

    # Redirect to the result page with the filename
    return redirect(url_for('result', filename=secure_name))

@app.route("/result/<filename>", methods=["GET"])
def result(filename):
    # Secure the filename using the custom sanitizer
    secure_name = custom_secure_filename(filename)
    download_url = url_for('download_file', filename=secure_name)
    return render_template("result.html", download_url=download_url)

@app.route("/download/<filename>", methods=["GET"])
def download_file(filename):
    # Secure the filename to prevent directory traversal
    secure_name = custom_secure_filename(filename)
    file_path = os.path.join(FINAL_DIR, secure_name)
    if not os.path.exists(file_path):
        return render_template("result.html", download_url=None, error_message="File not found or has been deleted.")
    return send_from_directory(FINAL_DIR, secure_name, as_attachment=True)

def delete_file(filename):
    try:
        file_path = os.path.join(FINAL_DIR, filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"Deleted file: {file_path}")
    except Exception as e:
        print(f"Error deleting file {filename}: {e}")

# Optional: Settings route
@app.route("/settings", methods=["GET"])
def settings():
    return render_template("settings.html")  # You can create a simple settings.html or leave it as a placeholder

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(port=port, host='0.0.0.0')
