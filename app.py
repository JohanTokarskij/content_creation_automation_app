import os
import threading

from flask import (Flask, 
                   render_template, 
                   request, 
                   send_from_directory, 
                   redirect, 
                   url_for, 
                   session)

from openai_funcs import (
    init_openai_client,
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
from helper_funcs import (clear_files_in_folder, 
                          get_final_filename, 
                          custom_secure_filename)


# Flask app initialization
app = Flask(__name__)
app.secret_key = "some_secret_key"

# Define directories
AUDIO_DIR = os.path.join("temp", "audio")
VIDEO_TEMP_DIR = os.path.join("temp", "video")
FINAL_DIR = "output"

@app.route("/", methods=["GET"])
def index():
    # Ensure folders exist
    os.makedirs(AUDIO_DIR, exist_ok=True)
    os.makedirs(VIDEO_TEMP_DIR, exist_ok=True)
    os.makedirs(FINAL_DIR, exist_ok=True)
    return render_template("index.html")

@app.route("/generate_video", methods=["POST"])
def generate_video():
    # Get form data
    user_topic = request.form.get("user_topic", "").strip()
    user_script = request.form.get("user_script", "").strip()
    audio_source = request.form.get("audio_source", "gtts")
    video_source = request.form.get("video_source", "pixabay")
    upload_option = request.form.get("upload_option", "local")

    # Check required keys based on user selections
    user_openai_key = session.get("OPENAI_API_KEY", "")
    if not user_openai_key:
        return render_template("index.html", result_message="No OpenAI API key.")

    if audio_source == "elevenlabs":
        elevenlabs_key = session.get('ELEVENLABS_API_KEY', '')
        if not elevenlabs_key:
            return render_template("index.html", result_message="No ElevenLabs API key.")

    if video_source == "luma":
        luma_key = session.get('LUMAAI_API_KEY', '')
        if not luma_key:
            return render_template("index.html", result_message="No LumaAI API key.")

    if video_source == "pixabay":
        pixabay_key = session.get('PIXABAY_API_KEY', '')
        if not pixabay_key:
            return render_template("index.html", result_message="No Pixabay API key.")

    if video_source == "pexels":
        pexels_key = session.get('PEXELS_API_KEY', '')
        if not pexels_key:
            return render_template("index.html", result_message="No Pexels API key.")

    if video_source == "storyblocks":
        public_key = session.get('STORYBLOCKS_PUBLIC_API_KEY', '')
        private_key = session.get('STORYBLOCKS_PRIVATE_API_KEY', '')
        if not public_key or not private_key:
            return render_template("index.html", result_message="No Storyblocks keys.")

    if upload_option == "youtube":
        youtube_secret_json = session.get('YOUTUBE_CLIENT_SECRET', '')
        if not youtube_secret_json:
            return render_template("index.html", result_message="No YouTube client_secret.")

    # Initialize OpenAI
    init_openai_client(user_openai_key)

    # Clear temp
    clear_files_in_folder(AUDIO_DIR)
    clear_files_in_folder(VIDEO_TEMP_DIR)


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

    # Get final filename
    final_name = get_final_filename(audio_source, video_source, video_title)
    secure_name = custom_secure_filename(final_name)

    # Generate audio
    if audio_source == "elevenlabs":
        generate_audio_files_elevenlabs(scripts, AUDIO_DIR, api_key=elevenlabs_key)
    else:
        generate_audio_files_gtts(scripts, AUDIO_DIR)

    # Define final path
    final_path = os.path.join(FINAL_DIR, secure_name)

    # Generate video
    if video_source == "luma":
        detailed_prompts = generate_detailed_prompts(scripts)
        process_videos_luma(detailed_prompts, AUDIO_DIR, final_path, api_key=luma_key)
    else:
        search_terms = generate_search_terms(main_topic, scripts)

        if video_source == "pexels":
            process_videos_pexels(scripts, search_terms, AUDIO_DIR, final_path, api_key=pexels_key)

        elif video_source == "storyblocks":
            process_videos_storyblocks(scripts, search_terms, AUDIO_DIR, final_path,
                                       private_api_key=private_key,
                                       public_api_key=public_key)

        elif video_source == "pixabay":
            process_videos_pixabay(scripts, search_terms, AUDIO_DIR, final_path, api_key=pixabay_key)
        else:
            return render_template("index.html", result_message="Invalid video source selected.")

    # Upload to YouTube if selected
    if upload_option == "youtube":
        youtube_title = f"{final_name.replace('.mp4', '')}"
        upload_video(
            video_file_path=final_path,
            video_name=youtube_title,
            youtube_secret_json=youtube_secret_json,
            video_hashtags=hashtags
        )

    # Clear temp files
    clear_files_in_folder(AUDIO_DIR)
    clear_files_in_folder(VIDEO_TEMP_DIR)

    # Download link
    download_url = url_for('download_file', filename=secure_name)
    timer = threading.Timer(60, delete_file, args=[secure_name])
    timer.start()

    # Redirect to result
    return redirect(url_for('result', filename=secure_name))

@app.route("/result/<filename>", methods=["GET"])
def result(filename):
    secure_name = custom_secure_filename(filename)
    download_url = url_for('download_file', filename=secure_name)
    return render_template("result.html", download_url=download_url)

@app.route("/download/<filename>", methods=["GET"])
def download_file(filename):
    secure_name = custom_secure_filename(filename)
    file_path = os.path.join(FINAL_DIR, secure_name)
    if not os.path.exists(file_path):
        return render_template("result.html", download_url=None, error_message="File not found or has been deleted.")
    return send_from_directory(FINAL_DIR, secure_name, as_attachment=True)

@app.route("/update_settings", methods=["POST"])
def update_settings():
    # Store values in session
    session['ELEVENLABS_API_KEY'] = request.form.get('elevenlabs_api', '').strip()
    session['OPENAI_API_KEY'] = request.form.get('openai_api', '').strip()
    session['PIXABAY_API_KEY'] = request.form.get('pixabay_api', '').strip()
    session['PEXELS_API_KEY'] = request.form.get('pexels_api', '').strip()
    session['STORYBLOCKS_PUBLIC_API_KEY'] = request.form.get('storyblocks_public', '').strip()
    session['STORYBLOCKS_PRIVATE_API_KEY'] = request.form.get('storyblocks_private', '').strip()
    session['LUMAAI_API_KEY'] = request.form.get('luma_api', '').strip()
    session['YOUTUBE_CLIENT_SECRET'] = request.form.get('youtube_client_secret', '').strip()
    return redirect(url_for('index'))

@app.route("/settings", methods=["GET"])
def settings():
    # Pass current session values to the template
    return render_template(
        "settings.html",
        openai_api=session.get('OPENAI_API_KEY',''),
        elevenlabs_api=session.get('ELEVENLABS_API_KEY',''),
        pixabay_api=session.get('PIXABAY_API_KEY',''),
        pexels_api=session.get('PEXELS_API_KEY',''),
        storyblocks_public=session.get('STORYBLOCKS_PUBLIC_API_KEY',''),
        storyblocks_private=session.get('STORYBLOCKS_PRIVATE_API_KEY',''),
        luma_api=session.get('LUMAAI_API_KEY',''),
        youtube_client_secret=session.get('YOUTUBE_CLIENT_SECRET','')
    )

def delete_file(filename):
    try:
        file_path = os.path.join(FINAL_DIR, filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"Deleted file: {file_path}")
    except Exception as e:
        print(f"Error deleting file {filename}: {e}")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(port=port, host='0.0.0.0')
