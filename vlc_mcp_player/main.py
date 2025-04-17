import json
import os
import pathlib
import subprocess
import sys
import time

import requests
from anthropic import Anthropic
from mcp.server.fastmcp import Context, FastMCP

app = FastMCP("watch_movie")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    print("ANTHROPIC_API_KEY not found in environment variables.", file=sys.stderr)
    sys.exit(1)

ROOT_VIDEO_FOLDER = os.getenv("ROOT_VIDEO_FOLDER")
if not ROOT_VIDEO_FOLDER:
    print("ROOT_VIDEO_FOLDER not found in environment variables.", file=sys.stderr)
    sys.exit(1)

MODEL_NAME = "claude-3-5-haiku-20241022"
VLC_HTTP_HOST = os.getenv("VLC_HTTP_HOST", "localhost")
VLC_HTTP_PORT = os.getenv("VLC_HTTP_PORT", "8081")
VLC_HTTP_PASSWORD = os.getenv("VLC_HTTP_PASSWORD", "your_password")

client = Anthropic(api_key=ANTHROPIC_API_KEY)


def vlc_command(ctx: Context, command, val=None, option=None, input=None):
    """Execute a VLC HTTP API command."""
    url = f"http://{VLC_HTTP_HOST}:{VLC_HTTP_PORT}/requests/status.xml"
    params = {"command": command}

    if val is not None:
        params["val"] = val
    if option is not None:
        params["option"] = option
    if input is not None:
        params["input"] = input

    ctx.info(f"Sending VLC command: URL={url}, Params={params}")

    try:
        response = requests.get(url, params=params, auth=("", VLC_HTTP_PASSWORD), timeout=10)
        ctx.info(f"VLC response status: {response.status_code}")
        response.raise_for_status()
        return True, ""
    except requests.RequestException as e:
        ctx.error(f"VLC command failed: {e}")
        return False, f"VLC command error: {e}"


def vlc_play_video(ctx: Context, video_path, subtitle_id=None):
    """Play a video in VLC with optional subtitle."""
    vlc_command(ctx, "volume", val=256)
    option = None if subtitle_id is None else f"sub-track={subtitle_id}"

    video_uri = pathlib.Path(video_path).as_uri()

    success, error_message = vlc_command(ctx, "in_play", input=video_uri, option=option)
    if success:
        time.sleep(2) # wait for the video to start
        success, error_message = vlc_command(ctx, "fullscreen", val=1)
    return success, error_message


@app.tool()
def get_status(ctx: Context) -> str:
    """Get the current status of VLC playback."""
    try:
        status_url = f"http://{VLC_HTTP_HOST}:{VLC_HTTP_PORT}/requests/status.json"
        ctx.info(f"Sending VLC command: URL={status_url}")
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
def seek(ctx: Context, value: str):
    """Seek to a specific position in the video. + or - seek relative to the current position and otherwise absolute.

    Allowed values are of the form:
        [+ or -][<int><h>:][<int><m>:][<int><s>]
    Examples:
        -10s -> seek 10 seconds backward
        +1h:2m:3s -> seek 1 hour, 2 minutes and 3 seconds forward
        30s -> seek to the 30th second
    """
    success, error_message = vlc_command(ctx, "seek", val=value)
    return success, error_message


@app.tool()
def vlc_control(ctx: Context, action: str) -> str:
    """Control VLC playback with actions: play, pause, stop."""
    result = False
    message = ""

    if action == "play":
        result = vlc_command(ctx, "pl_forceresume")
        message = "Resumed playback."
    elif action == "pause":
        result = vlc_command(ctx, "pl_forcepause")
        message = "Paused playback."
    elif action == "stop":
        result = vlc_command(ctx, "pl_stop")
        message = "Stopped playback."
    else:
        message = f"Unknown action: {action}. Use: play, pause, stop."

    return message if result else f"VLC command failed: {message}"


def get_available_videos_paths() -> str:
    """Gets a sorted list of relative video file paths within ROOT_VIDEO_FOLDER."""
    command = f"find {ROOT_VIDEO_FOLDER} -type f \\( -name '*.mkv' -o -name '*.mp4' \\) -printf '%P\\n' | sort"
    result = subprocess.run(command, shell=True, capture_output=True, text=True, check=True)
    return result.stdout.strip()


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
    """Display the video with the subtitle"""
    videos_paths = get_available_videos_paths()

    prompt = (
        "Summarize the list of available videos. The output should look like this for movies: "
        "- <director> - <title1> (<year>), <title2> (<year>)"
        "and like this for series for example: - <director> - <title> (Season 1-3)\n"
        f"The available movies are:\n{videos_paths}"
    )
    ctx.info(f"Getting available videos using an LLM from {len(videos_paths)} video paths.")

    message = client.messages.create(
        model=MODEL_NAME,
        max_tokens=2000,
        temperature=0.2,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


@app.tool()
def show_video(ctx: Context, video_title: str, subtitle_language_code: str = "") -> str:
    """Show the video using the the video title and the subtitle language code. If the subtitle language code is an empty string, the video will play with no subtitle."""
    videos_paths = get_available_videos_paths()
    prompt = (
        "Here's a list of available videos paths:\n"
        f"{videos_paths}\n"
        f"Based on this list, which path best matches the title '{video_title}'?"
        f"Please respond only with the full path of the best match, or 'None' if there's no good match."
    )
    ctx.info(f"Getting the best matching video path for '{video_title}' using an LLM.")

    message = client.messages.create(
        model=MODEL_NAME,
        max_tokens=200,
        temperature=0.2,
        messages=[{"role": "user", "content": prompt}],
    )

    relative_video_path = message.content[0].text.strip()

    if relative_video_path.lower() == "none":
        return f"No matching video found for '{video_title}'."

    full_video_path = os.path.join(ROOT_VIDEO_FOLDER, relative_video_path)
    ctx.info(f"Full video path:\n{full_video_path}")

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
                f"found for '{video_title}'. These are the available subtitles: {subtitle_str}"
            )

    success, error_message = vlc_play_video(ctx, full_video_path, subtitle_id)
    if success:
        return "The video should now play."
    else:
        return f"Failed to start VLC playback. {error_message}"


def main():
    app.run()


if __name__ == "__main__":
    main()
