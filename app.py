import os
import threading
import json

from google_auth_oauthlib.flow import InstalledAppFlow
from flask import (Flask, 
                   render_template, 
                   request, 
                   send_from_directory, 
                   redirect, 
                   url_for, 
                   session, 
                   jsonify, 
                   flash)

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

# Ensure directories exist at startup
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(VIDEO_TEMP_DIR, exist_ok=True)
os.makedirs(FINAL_DIR, exist_ok=True)

@app.route("/", methods=["GET"])
def index():
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
        flash("No OpenAI API key.", "error")
        return render_template("index.html")

    if audio_source == "elevenlabs":
        elevenlabs_key = session.get('ELEVENLABS_API_KEY', '')
        if not elevenlabs_key:
            flash("No ElevenLabs API key.", "error")
            return render_template("index.html")

    if video_source == "luma":
        luma_key = session.get('LUMAAI_API_KEY', '')
        if not luma_key:
            flash("No LumaAI API key.", "error")
            return render_template("index.html")

    if video_source == "pixabay":
        pixabay_key = session.get('PIXABAY_API_KEY', '')
        if not pixabay_key:
            flash("No Pixabay API key.", "error")
            return render_template("index.html")

    if video_source == "pexels":
        pexels_key = session.get('PEXELS_API_KEY', '')
        if not pexels_key:
            flash("No Pexels API key.", "error")
            return render_template("index.html")

    if video_source == "storyblocks":
        public_key = session.get('STORYBLOCKS_PUBLIC_API_KEY', '')
        private_key = session.get('STORYBLOCKS_PRIVATE_API_KEY', '')
        if not public_key or not private_key:
            flash("No Storyblocks keys.", "error")
            return render_template("index.html")

    if upload_option == "youtube":
        if 'YOUTUBE_TOKEN' not in session:
            flash("You need to authorize YouTube in settings.", "error")
            return render_template("index.html")

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
        flash("No script generated.", "error")
        return render_template("index.html")

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
            flash("Invalid video source selected.", "error")
            return render_template("index.html")

    # Clear temp files
    clear_files_in_folder(AUDIO_DIR)
    clear_files_in_folder(VIDEO_TEMP_DIR)

    # Upload to YouTube if selected
    upload_to_youtube = False
    if upload_option == "youtube":
        upload_to_youtube = True
        youtube_title = f"{final_name.replace('.mp4', '')}"
        success, message = upload_video(
            video_file_path=final_path,
            video_name=youtube_title,
            video_hashtags=hashtags
        )
        if not success:
            flash(f"YouTube upload failed: {message}", "error")
            return render_template("index.html")
        
        # Delete the file immediately after uploading to YouTube
        delete_file(secure_name)
        
        # Redirect to result without providing a download link
        return redirect(url_for('result', upload_to_youtube=upload_to_youtube, youtube_video_url=message))
    else:
        # Generate download link and start timer to delete the file after 60 seconds
        download_url = url_for('download_file', filename=secure_name)
        timer = threading.Timer(60, delete_file, args=[secure_name])
        timer.start()

        # Redirect to result with download link
        return redirect(url_for('result', filename=secure_name, upload_to_youtube=upload_to_youtube))

@app.route("/result", methods=["GET"])
def result():
    # Get 'filename' and 'upload_to_youtube' from query parameters
    filename = request.args.get('filename', default=None, type=str)
    upload_to_youtube = request.args.get('upload_to_youtube', 'false').lower() == 'true'
    youtube_video_url = request.args.get('youtube_video_url', default=None, type=str)
    
    if upload_to_youtube:
        return render_template("result.html", upload_to_youtube=True, youtube_video_url=youtube_video_url)
    elif filename:
        download_url = url_for('download_file', filename=filename)
        return render_template("result.html", download_url=download_url, upload_to_youtube=False)
    else:
        flash("Invalid request parameters.", "error")
        return render_template("result.html", error_message="Invalid request parameters.")

@app.route("/download/<filename>", methods=["GET"])
def download_file(filename):
    secure_name = custom_secure_filename(filename)
    file_path = os.path.join(FINAL_DIR, secure_name)
    if not os.path.exists(file_path):
        flash("File not found or has been deleted.", "error")
        return render_template("result.html", download_url=None, error_message="File not found or has been deleted.")
    return send_from_directory(FINAL_DIR, secure_name, as_attachment=True)

@app.route("/update_settings", methods=["POST"])
def update_settings():
    # Store API keys and YouTube client_secret in session
    session['ELEVENLABS_API_KEY'] = request.form.get('elevenlabs_api', '').strip()
    session['OPENAI_API_KEY'] = request.form.get('openai_api', '').strip()
    session['PIXABAY_API_KEY'] = request.form.get('pixabay_api', '').strip()
    session['PEXELS_API_KEY'] = request.form.get('pexels_api', '').strip()
    session['STORYBLOCKS_PUBLIC_API_KEY'] = request.form.get('storyblocks_public', '').strip()
    session['STORYBLOCKS_PRIVATE_API_KEY'] = request.form.get('storyblocks_private', '').strip()
    session['LUMAAI_API_KEY'] = request.form.get('luma_api', '').strip()
    session['YOUTUBE_CLIENT_SECRET'] = request.form.get('youtube_client_secret', '').strip()
    return redirect(url_for('settings'))

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

@app.route("/get_youtube_auth_url", methods=["POST"])
def get_youtube_auth_url():
    data = request.get_json()
    client_secret_json = data.get('client_secret', '').strip()
    if not client_secret_json:
        return jsonify({'message': 'No YouTube client_secret provided.'}), 400
    
    try:
        client_secret_data = json.loads(client_secret_json)
    except json.JSONDecodeError:
        return jsonify({'message': 'Invalid YouTube client_secret JSON.'}), 400

    flow = InstalledAppFlow.from_client_config(
        client_secret_data,
        scopes=['https://www.googleapis.com/auth/youtube.upload'],
        redirect_uri='urn:ietf:wg:oauth:2.0:oob'  # Out-of-band flow for manual code entry
    )
    auth_url, _ = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    return jsonify({'auth_url': auth_url})

@app.route("/submit_youtube_auth_code", methods=["POST"])
def submit_youtube_auth_code():
    data = request.get_json()
    code = data.get('code', '').strip()
    client_secret_json = data.get('client_secret', '').strip()

    if not code:
        return jsonify({'success': False, 'message': 'Authorization code is required.'}), 400

    if not client_secret_json:
        return jsonify({'success': False, 'message': 'client_secret is required.'}), 400

    try:
        client_secret_data = json.loads(client_secret_json)
    except json.JSONDecodeError:
        return jsonify({'success': False, 'message': 'Invalid client_secret JSON.'}), 400

    flow = InstalledAppFlow.from_client_config(
        client_secret_data,
        scopes=['https://www.googleapis.com/auth/youtube.upload'],
        redirect_uri='urn:ietf:wg:oauth:2.0:oob'  # Out-of-band flow
    )
    try:
        flow.fetch_token(code=code)
        creds = flow.credentials
        session['YOUTUBE_TOKEN'] = creds.to_json()
        return jsonify({'success': True, 'message': 'YouTube authorization successful!'}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': f'Authorization failed: {str(e)}'}), 400

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
