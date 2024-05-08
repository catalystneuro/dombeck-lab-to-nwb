import os
import subprocess


def check_ffmpeg():
    """Check if ffmpeg is installed on the system. If not, raise a ValueError."""
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except subprocess.CalledProcessError:
        raise ValueError("The package 'ffmpeg' should be installed before running 'convert_tiff_to_avi' function.")


def convert_tiff_to_avi(folder_path, file_pattern, frame_rate, avi_file_name):
    """
    Utility function to convert a series of tiff files to an avi file using ffmpeg.
    To use this function, you must have ffmpeg installed on your system.

    Parameters
    ----------
    folder_path : str
        The folder containing the tiff files.
    file_pattern : str
        The file pattern to match the tiff files.
    frame_rate : int
        The frame rate of the output avi file.
    avi_file_name : str
        The name of the output avi file.
    """
    # Check if ffmpeg is installed
    check_ffmpeg()

    # Change directory to the specified folder_path
    os.chdir(folder_path)

    command = [
        "ffmpeg",
        "-framerate",
        str(frame_rate),
        "-i",
        file_pattern,
        "-c:v",
        "libx264",  # You can specify the codec here if needed
        avi_file_name,
    ]

    # Execute the ffmpeg command
    subprocess.run(command)
