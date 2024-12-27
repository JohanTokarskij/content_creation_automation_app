import os
import datetime
import pytz
import json

import google.auth
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from flask import session


def upload_video(video_file_path, video_name, youtube_secret_json, video_hashtags=None):
    SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
    time_now = datetime.datetime.now(pytz.timezone('Europe/Stockholm')).strftime('%Y-%m-%d %H:%M')

    # Try loading token from session if it exists
    creds = None
    token_json = session.get('YOUTUBE_TOKEN', '')

    if token_json:
        try:
            creds = Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
        except Exception as e:
            print(f"Error parsing stored token from session: {e}")
            creds = None

    # If creds are missing or invalid, do the OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # If we have an expired token with a refresh_token, just refresh
            creds.refresh(Request())
        else:
            # parse the user-pasted JSON from session
            try:
                client_secret_data = json.loads(youtube_secret_json)
            except Exception as e:
                print(f"Error parsing client secret JSON: {e}")
                return

            flow = InstalledAppFlow.from_client_config(client_secret_data, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save the new or refreshed creds to session
        session['YOUTUBE_TOKEN'] = creds.to_json()

    # Build the YouTube API client
    youtube = build('youtube', 'v3', credentials=creds)

    # Define the video metadata
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

    # Upload the video
    media = MediaFileUpload(video_file_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(
        part='snippet,status',
        body=video_metadata,
        media_body=media
    )

    response = request.execute()
    print(f"Video uploaded. Video ID: {response['id']}")