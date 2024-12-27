import os
import re
import platform

from moviepy.config import change_settings


def clear_files_in_folder(folder_path: str):
    """
    Removes all files in the specified folder.

    Args:
        folder_path (str): The path to the folder to be cleared.

    Raises:
        ValueError: If the provided path is not a valid folder.
    """
    try:
        if not os.path.isdir(folder_path):
            raise ValueError(f"'{folder_path}' is not a valid directory.")
        
        for item in os.listdir(folder_path):
            item_path = os.path.join(folder_path, item)
            if os.path.isfile(item_path):
                os.unlink(item_path)

        print(f"Cleared folder: {folder_path}\n")
    except Exception as e:
        print(f"An error occurred while clearing '{folder_path}': {e}\n")


def get_local_ffmpeg_path():
    """
    Determines the operating system and returns the path to the appropriate ffmpeg binary.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    ffmpeg_dir = os.path.join(base_dir, 'ffmpeg_bin')
    
    if platform.system() == "Windows":
        ffmpeg_path = os.path.join(ffmpeg_dir, 'windows', 'ffmpeg.exe')
    elif platform.system() == "Linux":
        ffmpeg_path = os.path.join(ffmpeg_dir, 'linux', 'ffmpeg')
    else:
        raise OSError("Unsupported operating system. FFmpeg binaries are only provided for Windows and Linux.")
    
    if not os.path.exists(ffmpeg_path):
        raise FileNotFoundError(f"FFmpeg binary not found at {ffmpeg_path}. Please ensure it is downloaded and placed correctly.")
    
    if platform.system() == "Linux":
        os.chmod(ffmpeg_path, os.stat(ffmpeg_path).st_mode | 0o111)  # Adds execute permissions
    
    return ffmpeg_path


def configure_moviepy():
    """
    Configures moviepy to use the specified ffmpeg binary.
    """
    ffmpeg_path = get_local_ffmpeg_path()
    
    os.environ["IMAGEIO_FFMPEG_EXE"] = ffmpeg_path
    
    change_settings({"FFMPEG_BINARY": ffmpeg_path})


def sanitize_filename_component(s: str) -> str:
    """
    Removes (or substitutes) characters that are unsafe on most file systems.
    Allows letters, digits, underscores, hyphens, spaces.
    Strips leading/trailing spaces and collapses multiple spaces to a single space.
    """
    # Replace any disallowed chars with ''
    s = re.sub(r'[^a-zA-Z0-9_\-\s]', '', s)
    # Collapse multiple spaces into one
    s = re.sub(r'\s+', ' ', s)
    # Trim leading/trailing space
    return s.strip()


def get_final_filename(audio_tech: str, video_tech: str, video_title: str) -> str:
    """
    Builds a file name
    """
    safe_audio = sanitize_filename_component(audio_tech)
    safe_video = sanitize_filename_component(video_tech)
    safe_title = sanitize_filename_component(video_title)
    return f"[{safe_audio}][{safe_video}] {safe_title}.mp4"


def custom_secure_filename(filename):
    """
    Sanitizes the filename, allowing brackets while replacing other unsafe characters with underscores.
    """
    # Allow letters, numbers, underscores, hyphens, dots, and brackets
    return re.sub(r'[^A-Za-z0-9_.\-\[\]]+', '_', filename)