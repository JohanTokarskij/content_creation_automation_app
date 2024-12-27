import os

import requests


def generate_audio_files_elevenlabs(scripts, output_dir, api_key=None):
    CHUNK_SIZE = 1024
    VOICE_ID = 'onwK4e9ZLuTAKqWW03F9'
    URL_TEMPLATE = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"

    HEADERS = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": api_key
    }

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    total_scripts = len(scripts)
    for idx, script in enumerate(scripts):
        # Determine previous_text and next_text
        previous_text = scripts[idx - 1] if idx > 0 else ""
        next_text = scripts[idx + 1] if idx < total_scripts - 1 else ""

        data = {
            "text": script,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.5
            },
            "previous_text": previous_text,
            "next_text": next_text
        }
        response = requests.post(URL_TEMPLATE, json=data, headers=HEADERS)
        if response.status_code == 200:
            output_file = os.path.join(output_dir, f'scene_{idx+1}.mp3')
            with open(output_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                    if chunk:
                        f.write(chunk)
            print(f"Audio file saved: {output_file}")
        else:
            print(f"Failed to generate audio for script {idx+1}: {response.text}")
