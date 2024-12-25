import os
import re
import platform
from functools import lru_cache

from io import BytesIO
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
from moviepy.config import change_settings
import adlfs


_STORAGE_ACCOUNT = 'ycapstg'
FILESYSTEM = 'ycap'


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
    print(f"{base_dir=}")
    ffmpeg_dir = os.path.join(base_dir, 'ffmpeg_bin')
    
    if platform.system() == "Windows":
        ffmpeg_path = os.path.join(ffmpeg_dir, 'windows', 'ffmpeg.exe')
    elif platform.system() == "Linux":
        ffmpeg_path = os.path.join(ffmpeg_dir, 'linux', 'ffmpeg')
    else:
        raise OSError("Unsupported operating system. FFmpeg binaries are only provided for Windows and Linux.")
    
    if not os.path.exists(ffmpeg_path):
        raise FileNotFoundError(f"FFmpeg binary not found at {ffmpeg_path}. Please ensure it is downloaded and placed correctly.")
    
    # On Linux, ensure the ffmpeg binary has execute permissions
    if platform.system() == "Linux":
        os.chmod(ffmpeg_path, os.stat(ffmpeg_path).st_mode | 0o111)  # Adds execute permissions
    
    return ffmpeg_path


# def get_ffmpeg_path(storage_account, filesystem):
#     """
#     Downloads the appropriate FFmpeg binary from Azure Blob Storage to a local temporary path,
#     sets execute permissions if needed, and returns the local path to the FFmpeg binary.
#     """
#     try:
#         # Determine the operating system
#         os_name = platform.system()
#         if os_name == "Windows":
#             ffmpeg_file_name = 'ffmpeg.exe'
#             temp_dir = os.environ.get('TEMP', 'D:\\local\\Temp')
#             ffmpeg_directory_path = 'ffmpeg_bin/windows'
#         elif os_name == "Linux":
#             ffmpeg_file_name = 'ffmpeg'
#             temp_dir = '/tmp'
#             ffmpeg_directory_path = 'ffmpeg_bin/linux'
#         else:
#             raise OSError("Unsupported operating system. FFmpeg binaries are only provided for Windows and Linux.")

#         # Define the local path to the FFmpeg binary in the temporary directory
#         local_ffmpeg_path = os.path.join(temp_dir, ffmpeg_file_name)

#         # Build the remote path to the FFmpeg binary
#         ffmpeg_file_path = f"{ffmpeg_directory_path}/{ffmpeg_file_name}"

#         # Authenticate using DefaultAzureCredential
#         credential = DefaultAzureCredential()

#         # Create BlobServiceClient
#         blob_service_client = BlobServiceClient(
#             account_url=f"https://{storage_account}.blob.core.windows.net",
#             credential=credential
#         )

#         # Get the container client
#         container_client = blob_service_client.get_container_client(filesystem)

#         # Get the blob client
#         blob_client = container_client.get_blob_client(ffmpeg_file_path)

#         # Download the blob if it doesn't already exist locally
#         if not os.path.exists(local_ffmpeg_path):
#             with open(local_ffmpeg_path, "wb") as download_file:
#                 download_stream = blob_client.download_blob()
#                 download_file.write(download_stream.readall())

#         # On Linux, ensure the FFmpeg binary has execute permissions
#         if os_name == "Linux":
#             os.chmod(local_ffmpeg_path, os.stat(local_ffmpeg_path).st_mode | 0o111)  # Adds execute permissions

#         return local_ffmpeg_path

#     except Exception as e:
#         print(f"An error occurred while getting the FFmpeg path: {e}")
#         raise


# def save_file_to_adls(adls_fs, local_file_path, adls_destination_path):
#     with open(local_file_path, "rb") as local_file:
#         adls_fs.put(local_file, adls_destination_path)


# def download_file_from_adls(adls_fs, adls_source_path, local_file_path):
#     with adls_fs.open(adls_source_path, "rb") as remote_file:
#         data = remote_file.read()
#     with open(local_file_path, "wb") as local_file:
#         local_file.write(data)



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