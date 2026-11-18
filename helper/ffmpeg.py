import time
import os
import asyncio
import json
import re
from PIL import Image
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from pyrogram.types import Message


async def fix_thumb(thumb):
    width = 0
    height = 0
    try:
        if thumb != None:
            parser = createParser(thumb)
            metadata = extractMetadata(parser)
            if metadata.has("width"):
                width = metadata.get("width")
            if metadata.has("height"):
                height = metadata.get("height")

            with Image.open(thumb) as img:
                img.convert("RGB").save(thumb)
                resized_img = img.resize((width, height))
                resized_img.save(thumb, "JPEG")
            parser.close()
    except Exception as e:
        print(e)
        thumb = None

    return width, height, thumb


async def take_screen_shot(video_file, output_directory, ttl):
    out_put_file_name = f"{output_directory}/{time.time()}.jpg"
    file_genertor_command = [
        "ffmpeg", "-ss", str(ttl), "-i", video_file,
        "-vframes", "1", out_put_file_name
    ]
    process = await asyncio.create_subprocess_exec(
        *file_genertor_command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await process.communicate()
    if os.path.lexists(out_put_file_name):
        return out_put_file_name
    return None


_LANGUAGE_NAMES = {
    "eng": "English", "jpn": "Japanese", "hin": "Hindi",
    "tam": "Tamil", "tel": "Telugu", "kor": "Korean",
    "chi": "Chinese", "zho": "Chinese", "fra": "French",
    "fre": "French", "deu": "German", "ger": "German",
    "spa": "Spanish", "ita": "Italian", "rus": "Russian",
    "ara": "Arabic", "und": None,
}


async def _probe_file(path):
    command = [
        "ffprobe", "-v", "error", "-show_streams",
        "-show_format", "-of", "json", path
    ]
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise RuntimeError(stderr.decode(errors="replace").strip() or "ffprobe failed")
    return json.loads(stdout.decode("utf-8", errors="replace"))


def _language_label(stream):
    tags = stream.get("tags") or {}
    old_title = tags.get("title", "")

    # Extract only the bracketed language label from an existing stream title.
    match = re.search(r"(\[[^\]]+\])\s*$", old_title)
    if match:
        return match.group(1)

    language = tags.get("language")
    language_name = _LANGUAGE_NAMES.get(str(language).lower()) if language else None
    if language_name:
        return f"[{language_name}]"

    # If the source has no readable language label, don't invent one.
    return ""


async def add_metadata(input_path, output_path, metadata_fields, ms):
    """
    Apply only the metadata fields the user has explicitly set or deleted.
    Missing keys are left unchanged. Empty values explicitly clear a field.
    """
    try:
        await ms.edit("<i>Applying your independent metadata settings ⚡</i>")

        probe = await _probe_file(input_path)
        streams = probe.get("streams", [])

        command = [
            "ffmpeg", "-y", "-i", input_path,
            "-map", "0", "-map_metadata", "0", "-c", "copy"
        ]

        # Global MKV metadata. Only keys present in the user's settings are changed.
        global_keys = {
            "title": "title",
            "author": "author",
            "artist": "artist",
        }
        for field, ffmpeg_key in global_keys.items():
            if field in metadata_fields:
                command.extend(["-metadata", f"{ffmpeg_key}={metadata_fields[field] or ''}"])

        # Per-stream names. FFmpeg's type-relative indexes target every track
        # independently while preserving all other stream tags.
        type_indexes = {"video": 0, "audio": 0, "subtitle": 0}
        for stream in streams:
            codec_type = stream.get("codec_type")
            if codec_type not in ("video", "audio", "subtitle"):
                continue

            field = {
                "video": "video",
                "audio": "audio",
                "subtitle": "subtitle",
            }[codec_type]

            if field not in metadata_fields:
                type_indexes[codec_type] += 1
                continue

            value = metadata_fields[field]
            if codec_type in ("audio", "subtitle"):
                language_label = _language_label(stream)
                if value:
                    # Custom text goes before the original language label.
                    stream_title = f"{value} - {language_label}" if language_label else value
                else:
                    # Delete only the custom text; retain just the language label.
                    stream_title = language_label
            else:
                # Deleting video metadata clears the track title completely.
                stream_title = value or ""

            stream_index = type_indexes[codec_type]
            specifier = {"video": "v", "audio": "a", "subtitle": "s"}[codec_type]
            command.extend([
                f"-metadata:s:{specifier}:{stream_index}",
                f"title={stream_title}"
            ])
            type_indexes[codec_type] += 1

        command.append(output_path)

        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        error_text = stderr.decode(errors="replace").strip()
        print(error_text)
        if stdout:
            print(stdout.decode(errors="replace").strip())

        if process.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            await ms.edit("<i>Your selected metadata settings were applied successfully ✅</i>")
            return output_path

        print(f"FFmpeg metadata process failed: {error_text}")
        await ms.edit("<i>Could not apply metadata. The original renamed file will be sent instead.</i>")
        return None

    except Exception as e:
        print(f"Error occurred while adding metadata: {e}")
        try:
            await ms.edit("<i>Could not apply metadata. The original renamed file will be sent instead.</i>")
        except Exception:
            pass
        return None
