import json
import os
import pathlib
import subprocess
import sys
import time
from pathlib import Path

import requests
from mcp.server.fastmcp import Context, FastMCP

app = FastMCP("vlc_movie_player")

ROOT_VIDEO_FOLDER = os.getenv("ROOT_VIDEO_FOLDER")
if not ROOT_VIDEO_FOLDER:
    print("ROOT_VIDEO_FOLDER not found in environment variables.", file=sys.stderr)
    sys.exit(1)

MODEL_NAME = "claude-3-5-haiku-20241022"
VLC_HTTP_HOST = os.getenv("VLC_HTTP_HOST", "localhost")
VLC_HTTP_PORT = os.getenv("VLC_HTTP_PORT", "8081")
VLC_HTTP_PASSWORD = os.getenv("VLC_HTTP_PASSWORD", "your_password")


async def vlc_command(ctx: Context, command, val=None, option=None, input=None):
    """Execute a VLC HTTP API command."""
    url = f"http://{VLC_HTTP_HOST}:{VLC_HTTP_PORT}/requests/status.xml"
    params = {"command": command}

    if val is not None:
        params["val"] = val
    if option is not None:
        params["option"] = option
    if input is not None:
        params["input"] = input

    await ctx.info(f"Sending VLC command: URL={url}, Params={params}")

    try:
        response = requests.get(url, params=params, auth=("", VLC_HTTP_PASSWORD), timeout=10)
        await ctx.info(f"VLC response status: {response.status_code}")
        response.raise_for_status()
        return True, ""
    except requests.RequestException as e:
        await ctx.error(f"VLC command failed: {e}")
        return False, f"VLC command error: {e}"


async def vlc_play_video(ctx: Context, video_path, subtitle_id=None):
    """Play a video in VLC with optional subtitle."""
    await vlc_command(ctx, "volume", val=256)
    option = None if subtitle_id is None else f"sub-track={subtitle_id}"

    video_uri = pathlib.Path(video_path).as_uri()

    success, error_message = await vlc_command(ctx, "in_play", input=video_uri, option=option)
    if success:
        time.sleep(4)  # wait for the video to start
        success, error_message = await vlc_command(ctx, "fullscreen", val=1)
    return success, error_message


@app.tool()
async def get_status(ctx: Context) -> str:
    """Get the current status of VLC playback."""
    try:
        status_url = f"http://{VLC_HTTP_HOST}:{VLC_HTTP_PORT}/requests/status.json"
        await ctx.info(f"Sending VLC command: URL={status_url}")
        response = requests.get(status_url, auth=("", VLC_HTTP_PASSWORD), timeout=10)
        response.raise_for_status()
        status = response.json()

        filename = status.get("information", {}).get("category", {}).get("meta", {}).get("filename", "unknown")

        message = (
            f"Status: {status.get('state', 'unknown')}, time: {status.get('time', 0)}/"
            f"{status.get('length', 0)} seconds, File: {filename}"
        )
        return message
    except requests.RequestException as e:
        return f"Failed to get status: {e}"


@app.tool()
async def seek(ctx: Context, value: str):
    """Seek to a specific position in the video. + or - seek relative to the current position and otherwise absolute.

    Allowed values are of the form:
        [+ or -][<int><h>:][<int><m>:][<int><s>]
    Examples:
        -10s -> seek 10 seconds backward
        +1h:2m:3s -> seek 1 hour, 2 minutes and 3 seconds forward
        30s -> seek to the 30th second
    """
    success, error_message = await vlc_command(ctx, "seek", val=value)
    return success, error_message


@app.tool()
async def vlc_control(ctx: Context, action: str) -> str:
    """Control VLC playback with actions: play, pause, stop, fullscreen."""
    success = False
    message = ""
    error_message = f"Unknown action: {action}. Use: play, pause, stop, fullscreen."

    if action == "play":
        success, error_message = await vlc_command(ctx, "pl_forceresume")
        message = "Resumed playback."
    elif action == "pause":
        success, error_message = await vlc_command(ctx, "pl_forcepause")
        message = "Paused playback."
    elif action == "stop":
        success, error_message = await vlc_command(ctx, "pl_stop")
        message = "Stopped playback."
    elif action == "fullscreen":
        success, error_message = await vlc_command(ctx, "fullscreen", val=1)
        message = "Fullscreen mode enabled."

    return message if success else f"VLC command failed: {error_message}"


@app.tool()
async def set_volume(ctx: Context, volume_level: int) -> str:
    """Set the volume level of VLC (0-200, where 100 is normal volume).

    Args:
        volume_level: An integer between 0 and 200 representing the volume percentage
    """
    # Validate volume level
    if not 0 <= volume_level <= 200:
        return f"Invalid volume level: {volume_level}. Please use a value between 0 and 200."

    # VLC uses values from 0-512, where 256 is 100% volume
    vlc_volume = int(volume_level * 256 / 100)

    success, error_message = await vlc_command(ctx, "volume", val=vlc_volume)

    if success:
        return f"Volume set to {volume_level}%."
    else:
        return f"Failed to set volume: {error_message}"


@app.tool()
async def get_volume(ctx: Context) -> str:
    """Get the current volume level of VLC (as a percentage)."""
    try:
        status_url = f"http://{VLC_HTTP_HOST}:{VLC_HTTP_PORT}/requests/status.json"
        await ctx.info(f"Sending VLC command: URL={status_url}")
        response = requests.get(status_url, auth=("", VLC_HTTP_PASSWORD), timeout=10)
        response.raise_for_status()
        status = response.json()

        # VLC volume range is 0-512, where 256 is 100%
        vlc_volume = status.get("volume", 0)
        percentage = int(vlc_volume * 100 / 256)

        return f"Current volume: {percentage}%"
    except requests.RequestException as e:
        return f"Failed to get volume: {e}"


@app.tool()
async def adjust_volume(ctx: Context, change: int) -> str:
    """Increase or decrease the volume by a specified percentage.

    Args:
        change: An integer representing the percentage to change the volume by.
               Positive values increase volume, negative values decrease it.
    """
    try:
        # First get current volume
        status_url = f"http://{VLC_HTTP_HOST}:{VLC_HTTP_PORT}/requests/status.json"
        response = requests.get(status_url, auth=("", VLC_HTTP_PASSWORD), timeout=10)
        response.raise_for_status()
        status = response.json()

        # Get current volume and convert to percentage
        current_vlc_volume = status.get("volume", 0)
        current_percentage = int(current_vlc_volume * 100 / 256)

        # Calculate new volume percentage
        new_percentage = current_percentage + change
        new_percentage = max(0, min(200, new_percentage))  # Clamp to 0-200%

        # Convert back to VLC volume value
        new_vlc_volume = int(new_percentage * 256 / 100)

        # Set the new volume
        success, error_message = await vlc_command(ctx, "volume", val=new_vlc_volume)

        if success:
            return f"Volume adjusted from {current_percentage}% to {new_percentage}%"
        else:
            return f"Failed to adjust volume: {error_message}"
    except requests.RequestException as e:
        return f"Failed to adjust volume: {e}"


def get_available_subtitles(video_path) -> str:
    command = ["mediainfo", "--Output=JSON", video_path]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=True,
        encoding="utf-8",
    )
    media_data = json.loads(result.stdout)

    subtitle_list = []
    if "media" in media_data and "track" in media_data["media"]:
        for track in media_data["media"]["track"]:
            if track.get("@type") == "Text":
                subtitle_list.append(
                    {
                        "id": len(subtitle_list),
                        "language": track.get("Language", "und"),
                        "title": track.get("Title", None),
                    }
                )
    return subtitle_list


@app.tool()
def get_available_videos(ctx: Context) -> str:
    """Get all available videos with their path."""
    root_path = Path(ROOT_VIDEO_FOLDER)
    video_paths = []
    for ext in ["*.mkv", "*.mp4"]:
        for path in root_path.rglob(ext):
            relative_path = path.relative_to(root_path)
            video_paths.append(str(relative_path))

    video_paths.sort()
    return "\n".join(video_paths)


@app.tool()
async def show_video(ctx: Context, video_path: str, subtitle_language_code: str = "") -> str:
    """Show the video using the the video path and the subtitle language code. If the subtitle language code is an empty string, the video will play with no subtitle."""
    full_video_path = os.path.join(ROOT_VIDEO_FOLDER, video_path)
    await ctx.info(f"Full video path:\n{full_video_path}")

    if not os.path.exists(full_video_path):
        return f"The file {full_video_path} does not exist."

    subtitle_list = get_available_subtitles(full_video_path)

    subtitle_id = None
    if subtitle_language_code != "":
        for subtitle in subtitle_list:
            if subtitle_language_code == subtitle["language"]:
                subtitle_id = subtitle["id"]

        if subtitle_id is None:
            subtitle_str = ", ".join(
                [f"{subtitle_info['language']} - {subtitle_info['title']}" for subtitle_info in subtitle_list]
            )
            return (
                f"No matching subtitle with the language code {subtitle_language_code} "
                f"found for '{video_path}'. These are the available subtitles: {subtitle_str}"
            )

    success, error_message = await vlc_play_video(ctx, full_video_path, subtitle_id)
    if success:
        return "The video should now play."
    else:
        return f"Failed to start VLC playback. {error_message}"


def main():
    app.run()


if __name__ == "__main__":
    main()
