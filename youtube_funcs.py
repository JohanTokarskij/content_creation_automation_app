import os
import datetime
import pytz
import json
from typing import Optional, List, Tuple

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from flask import session, flash

def upload_video(
    video_file_path: str,
    video_name: str,
    video_hashtags: Optional[List[str]] = None
) -> Tuple[bool, str]:
    """
    Uploads a video to YouTube.

    Args:
        video_file_path (str): The file path to the video to be uploaded.
        video_name (str): The name/title of the video.
        video_hashtags (Optional[List[str]]): A list of hashtags associated with the video.

    Returns:
        Tuple[bool, str]: A tuple where the first element is a boolean indicating success,
                          and the second element is either the video URL on success or an error message on failure.
    """
    SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
    time_now = datetime.datetime.now(pytz.timezone('Europe/Stockholm')).strftime('%Y-%m-%d %H:%M')

    # Retrieve token from session
    token_json = session.get('YOUTUBE_TOKEN', '')
    
    if not token_json:
        print("No stored YouTube credentials.")
        flash("You need to authorize YouTube in settings.", "error")
        return False, "No YouTube credentials. Please authorize."

    try:
        creds = Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
    except Exception as e:
        print(f"Error parsing stored token: {e}")
        flash("Invalid YouTube credentials. Please re-authorize.", "error")
        return False, "Invalid YouTube credentials."

    # Refresh token if expired
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                session['YOUTUBE_TOKEN'] = creds.to_json()
            except Exception as e:
                print(f"Error refreshing token: {e}")
                flash("Token refresh failed. Please re-authorize YouTube.", "error")
                return False, "Token refresh failed. Please re-authorize YouTube."
        else:
            print("Credentials are invalid. User needs to authorize again.")
            flash("Credentials are invalid. Please re-authorize YouTube.", "error")
            return False, "Credentials are invalid. Please re-authorize YouTube."

    # Build YouTube client
    try:
        youtube = build('youtube', 'v3', credentials=creds)
    except Exception as e:
        print(f"Error building YouTube client: {e}")
        flash("Failed to build YouTube client.", "error")
        return False, "Failed to build YouTube client."

    # Define video metadata
    video_metadata = {
        'snippet': {
            'title': video_name,
            'description': f"This is an automated upload using Python at {time_now}\n\n{' '.join(video_hashtags or [])}",
            'tags': ['python', 'youtube', 'upload'],
            'categoryId': '22'
        },
        'status': {
            'privacyStatus': 'private',
        }
    }

    # Upload video
    media = MediaFileUpload(video_file_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(
        part='snippet,status',
        body=video_metadata,
        media_body=media
    )

    try:
        response = request.execute()
        print(f"Video uploaded. Video ID: {response['id']}")
        # flash(f"Video uploaded successfully! Video ID: {response['id']}", "success")
        video_id = response['id']
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        return True, video_url
    except Exception as e:
        print(f"Error uploading video: {e}")
        flash(f"Error uploading video: {e}", "error")
        return False, str(e)
