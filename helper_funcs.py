import os
import re
import platform

from moviepy.config import change_settings


def clear_files_in_folder(folder_path: str) -> None:
    """
    Removes all files in the specified folder.

    This function iterates through all items in the given directory and deletes the files.
    It skips subdirectories and only removes regular files.

    Args:
        folder_path (str): The path to the folder to be cleared.

    Raises:
        ValueError: If the provided path is not a valid directory.
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


def get_local_ffmpeg_path() -> str:
    """
    Determines the operating system and returns the path to the appropriate ffmpeg binary.

    This function checks the current operating system (Windows or Linux) and constructs the
    path to the corresponding ffmpeg executable. It verifies the existence of the binary and
    sets execute permissions for Linux systems.

    Returns:
        str: The file system path to the ffmpeg binary.

    Raises:
        OSError: If the operating system is not supported.
        FileNotFoundError: If the ffmpeg binary is not found at the expected location.
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


def configure_moviepy() -> None:
    """
    Configures MoviePy to use the specified ffmpeg binary.

    This function sets the environment variable and MoviePy settings to point to the local
    ffmpeg binary, ensuring that MoviePy uses the correct executable for video processing.
    """
    ffmpeg_path = get_local_ffmpeg_path()
    
    os.environ["IMAGEIO_FFMPEG_EXE"] = ffmpeg_path
    
    change_settings({"FFMPEG_BINARY": ffmpeg_path})


def custom_secure_filename(filename: str) -> str:
    """
    Sanitizes the filename by allowing brackets while replacing other unsafe characters with underscores.

    This function ensures that filenames are safe for use in various operating systems by removing
    or replacing characters that are not typically allowed in file names.

    Args:
        filename (str): The original filename to be sanitized.

    Returns:
        str: A sanitized version of the filename with unsafe characters replaced by underscores.
    """
    # Allow letters, numbers, underscores, hyphens, dots, brackets, apostrophes, and spaces
    return re.sub(r"[^A-Za-z0-9_.\-\[\]\' ]+", '_', filename)


def get_final_filename(audio_tech: str, video_tech: str, video_title: str) -> str:
    """
    Constructs a sanitized and formatted filename for the final video.

    This function combines audio technology, video technology, and the video title into a single
    filename. It ensures that each component is sanitized to remove or replace unsafe characters.

    Args:
        audio_tech (str): The audio technology used (e.g., "voiceover").
        video_tech (str): The video technology used (e.g., "LumaAI").
        video_title (str): The title of the video.

    Returns:
        str: A formatted and sanitized filename in the format "[audio_tech][video_tech] video_title.mp4".
    """
    safe_audio = custom_secure_filename(audio_tech)
    safe_video = custom_secure_filename(video_tech)
    safe_title = custom_secure_filename(video_title)
    return f"[{safe_audio}][{safe_video}] {safe_title}.mp4"


def delete_file(file_path: str) -> None:
    """
    Deletes a specified file from the final output directory.

    Args:
        filename (str): The name of the file to delete.
    """
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"Deleted file: {file_path}")
    except Exception as e:
        print(f"Error deleting file {file_path}: {e}")