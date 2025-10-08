import os
import json


def extract_format_data(format_data):
    extension = format_data["ext"]
    format_name = format_data["format"]
    return {
        "extension": extension,
        "format_name": format_name,
        "url": format_data["url"]
    }

def extract_video_data_from_url(url):
    command = f'yt-dlp "{url}" -j'
    output = os.popen(command).read()
    if not output.strip():
        return {
            "title": "Error",
            "formats": [],
            "thumbnail": "",
            "duration": "",
            "error": "Could not fetch video data. Please check the URL."
        }
    try:
        video_data = json.loads(output)
    except json.JSONDecodeError:
        return {
            "title": "Error",
            "formats": [],
            "thumbnail": "",
            "duration": "",
            "error": "Invalid response from yt-dlp. Please try again."
        }
    title = video_data.get("title", "No Title")
    formats = video_data.get("formats", [])
    thumbnail = video_data.get("thumbnail", "")
    duration = video_data.get("duration")
    # Convert duration (seconds) to mm:ss
    if duration:
        mins = int(duration // 60)
        secs = int(duration % 60)
        duration_str = f"{mins}:{secs:02d}"
    else:
        duration_str = ""
    # Sort formats by resolution (height), highest first
    video_formats = [f for f in formats if f.get("height")]
    video_formats.sort(key=lambda x: x.get("height", 0), reverse=True)
    other_formats = [f for f in formats if not f.get("height")]
    sorted_formats = video_formats + other_formats
    formats = [extract_format_data(format_data) for format_data in sorted_formats]
    # Use default thumbnail if missing
    if not thumbnail:
        thumbnail = "https://www.shutterstock.com/image-vector/vector-graphic-no-thumbnail-symbol-260nw-1391095985.jpg"
    return {
        "title": title,
        "formats": formats,
        "thumbnail": thumbnail,
        "duration": duration_str
    }

