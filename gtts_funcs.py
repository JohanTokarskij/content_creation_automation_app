import os
from typing import List

from gtts import gTTS


def generate_audio_files_gtts(scripts: List[str], output_dir: str) -> None:
    """
    Generates MP3 audio files for each scene using Google gTTS.

    Args:
        scripts (List[str]): A list of script texts for each scene.
        output_dir (str): The directory where the audio files will be saved.

    Returns:
        None
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for idx, script in enumerate(scripts):
        audio_path = os.path.join(output_dir, f'scene_{idx+1}.mp3')
        try:
            tts = gTTS(script, lang='en', slow=False)
            tts.save(audio_path)
            print(f"Audio file saved: {audio_path}")
        except Exception as e:
            print(f"Failed to generate audio for script {idx+1}: {e}")