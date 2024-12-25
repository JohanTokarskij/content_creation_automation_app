import os
import datetime
import pytz

import google.auth
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Path to token.json and client_secret.json
# Works with johtok59@gmail.com
YOUTUBE_TOKEN_PATH = 'token.json'
YOUTUBE_CLIENT_SECRET_PATH = 'client_secret.json'

def upload_video(YOUTUBE_TOKEN_PATH, YOUTUBE_CLIENT_SECRET_PATH, video_file_path, video_name):
    SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

    time_now = datetime.datetime.now(pytz.timezone('Europe/Stockholm')).strftime('%Y-%m-%d %H:%M:%S')

    # Load credentials from token.json
    creds = None
    if os.path.exists(YOUTUBE_TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(YOUTUBE_TOKEN_PATH, SCOPES)
    else:
        flow = InstalledAppFlow.from_client_secrets_file(YOUTUBE_CLIENT_SECRET_PATH, SCOPES)
        creds = flow.run_local_server(port=0)

    # Refresh token if needed
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    elif not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(YOUTUBE_CLIENT_SECRET_PATH, SCOPES)
        creds = flow.run_local_server(port=0)

    # Save the credentials for the next run
    with open(YOUTUBE_TOKEN_PATH, 'w') as token:
        token.write(creds.to_json())

    # Build the YouTube API client
    youtube = build('youtube', 'v3', credentials=creds)

    # Define the video metadata
    video_metadata = {
        'snippet': {
            'title': video_name,
            'description': f'This is an automated upload using Python at {time_now}',
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


#upload_video(YOUTUBE_TOKEN_PATH, YOUTUBE_CLIENT_SECRET_PATH, 'output/[gtts][pexels] Unveiling the Mystery of the Tittle The Dot Over i and j.mp4', "[gtts][pexels] Unveiling the Mystery of the Tittle The Dot Over i and j")