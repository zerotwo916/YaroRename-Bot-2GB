
import os
import re
import time
import random
import html
import shutil
from types import SimpleNamespace
from asyncio import sleep

from pyrogram import Client, filters
from pyrogram.enums import MessageMediaType, ParseMode
from pyrogram.errors import FloodWait
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ForceReply,
)

from hachoir.metadata import extractMetadata
from hachoir.parser import createParser

from helper.ffmpeg import fix_thumb, take_screen_shot, add_metadata
from helper.utils import progress_for_pyrogram, convert, humanbytes
from helper.database import jishubotz


_PENDING_RENAMES = {}


def _get_media(message):
    if not message or not message.media:
        return None
    return getattr(message, message.media.value, None)


def _normalize_filename(filename):
    """
    Replace filename underscores with spaces, but preserve valid
    Telegram @usernames exactly as written.
    """
    value = str(filename or "")
    usernames = []

    def protect_username(match):
        usernames.append(match.group(0))
        return f"ZZZTELEGRAMUSERNAME{len(usernames) - 1}ZZZ"

    value = re.sub(
        r"@[A-Za-z][A-Za-z0-9_]{3,30}[A-Za-z0-9]",
        protect_username,
        value,
    )
    value = " ".join(value.replace("_", " ").split())

    for index, username in enumerate(usernames):
        value = value.replace(f"ZZZTELEGRAMUSERNAME{index}ZZZ", username)

    return value


def _add_prefix_suffix(filename, prefix=None, suffix=None):
    filename = _normalize_filename(filename)
    stem, extension = os.path.splitext(filename)
    prefix = _normalize_filename(prefix or "")
    suffix = _normalize_filename(suffix or "")
    result = f"{prefix}{stem}{(' ' + suffix) if suffix else ''}{extension}"
    return _normalize_filename(result)


def _selection_message(filename):
    return (
        "Select The Output File Type\n\n"
        f"File Name :- {filename}"
    )


def _format_filename_caption(filename):
    """
    Show the filename as code while rendering a Telegram @username
    inside it as a clickable blue link.
    """
    match = re.search(
        r"@[A-Za-z][A-Za-z0-9_]{3,30}[A-Za-z0-9]",
        filename,
    )

    if not match:
        return f"<code>{html.escape(filename)}</code>"

    before = html.escape(filename[:match.start()])
    username = match.group(0)
    after = html.escape(filename[match.end():])

    # Match the filename's monospace style; keep only the @username clickable.
    return (
        f"<code>{before}</code>"
        f'<a href="https://t.me/{username[1:]}">{html.escape(username)}</a>'
        f"<code>{after}</code>"
    )


def _safe_remove(path):
    if path and os.path.isfile(path):
        try:
            os.remove(path)
        except OSError as error:
            print(f"Cleanup error: {error}")


def _safe_remove_dir(path):
    if path and os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)


@Client.on_message(filters.private & (filters.document | filters.audio | filters.video))
async def rename_start(client, message):
    media = _get_media(message)
    if not media:
        return

    filename = media.file_name or f"file_{message.id}"
    extension = os.path.splitext(filename)[1] or "Not available"
    mime_type = getattr(media, "mime_type", None) or "Not available"
    dc_id = getattr(media, "dc_id", None)

    if media.file_size and media.file_size > 2000 * 1024 * 1024:
        return await message.reply_text(
            "Sorry Bro This Bot Doesn't Support Uploading Files Bigger Than 2GB",
            quote=True,
        )

    info = (
        "<b>📁 Media Info</b>\n\n"
        f"◈ <b>File Name:</b> <code>{html.escape(filename)}</code>\n"
        f"◈ <b>File Size:</b> <code>{humanbytes(media.file_size)}</code>\n"
        f"◈ <b>File Extension:</b> <code>{html.escape(extension)}</code>\n"
        f"◈ <b>MIME Type:</b> <code>{html.escape(mime_type)}</code>\n"
        f"◈ <b>DC ID:</b> <code>{dc_id if dc_id is not None else 'Not available'}</code>"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✏️ Rename", callback_data="rename_file"),
            InlineKeyboardButton("✖️ Cancel", callback_data="cancel_rename"),
        ]
    ])

    thumbs = getattr(media, "thumbs", None) or []
    pending = {
        "file_id": media.file_id,
        "media_type": message.media,
        "file_name": filename,
        "file_size": media.file_size,
        "mime_type": mime_type,
        "dc_id": dc_id,
        "thumbs": thumbs,
        "original_message_id": message.id,
    }

    info_message = None
    if thumbs:
        try:
            info_message = await message.reply_photo(
                photo=thumbs[-1].file_id,
                caption=info,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
                reply_to_message_id=message.id,
            )
        except Exception as error:
            print(f"Thumbnail display error: {error}")

    if info_message is None:
        info_message = await message.reply_text(
            text=info,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
            reply_to_message_id=message.id,
        )

    _PENDING_RENAMES[info_message.id] = pending

    # Remove the user's original upload after the bot has shown its controls.
    try:
        await message.delete()
    except Exception as error:
        print(f"Original upload delete error: {error}")


@Client.on_callback_query(filters.regex("^rename_file$"))
async def start_rename_prompt(client, query):
    pending = _PENDING_RENAMES.get(query.message.id) if query.message else None
    if not pending:
        return await query.answer(
            "File information expired. Please send the file again.",
            show_alert=True,
        )

    prompt = await query.message.reply_text(
        "Please Enter The New Filename.",
        reply_markup=ForceReply(True),
        parse_mode=ParseMode.DISABLED,
    )
    _PENDING_RENAMES[prompt.id] = pending

    await query.message.delete()
    _PENDING_RENAMES.pop(query.message.id, None)
    await query.answer("Now send the new filename.")


@Client.on_callback_query(filters.regex("^cancel_rename$"))
async def cancel_rename(client, query):
    await query.answer("Rename cancelled.")
    if query.message:
        _PENDING_RENAMES.pop(query.message.id, None)
        await query.message.delete()


@Client.on_message(filters.private & filters.reply)
async def refunc(client, message):
    reply_message = message.reply_to_message

    if not reply_message or not reply_message.reply_markup:
        return

    if not isinstance(reply_message.reply_markup, ForceReply):
        return

    new_name = (message.text or "").strip()

    if not new_name:
        return

    if "/" in new_name or "\\" in new_name or "\x00" in new_name:
        return await message.reply_text(
            "Please send only a filename, without folder paths."
        )

    await message.delete()

    pending = _PENDING_RENAMES.get(reply_message.id)
    if not pending:
        return await message.reply_text(
            "File information expired. Please send the file again."
        )

    media = SimpleNamespace(
        file_id=pending["file_id"],
        file_name=pending["file_name"],
        file_size=pending["file_size"],
        mime_type=pending["mime_type"],
        dc_id=pending["dc_id"],
        thumbs=pending["thumbs"],
    )
    original_file = SimpleNamespace(
        id=pending["original_message_id"],
        media=pending["media_type"],
        **{pending["media_type"].value: media},
    )
    source_file_id = pending["file_id"]


    if not os.path.splitext(new_name)[1]:
        original_filename = media.file_name or "file.mkv"
        new_name += os.path.splitext(original_filename)[1] or ".mkv"

    await reply_message.delete()

    saved_mode = await jishubotz.get_output_mode(message.from_user.id)

    if saved_mode in ("document", "video"):
        if saved_mode == "video" and original_file.media not in (
            MessageMediaType.VIDEO,
            MessageMediaType.DOCUMENT,
        ):
            saved_mode = None
        else:
            status = await message.reply(
                text=_selection_message(new_name),
                reply_to_message_id=original_file.id,
                parse_mode=ParseMode.DISABLED,
            )

            automatic_update = SimpleNamespace(
                message=status,
                data=f"upload_{saved_mode}",
                from_user=message.from_user,
                original_file=original_file,
                source_file_id=source_file_id,
            )

            await doc(client, automatic_update)
            return

    buttons = [
        [
            InlineKeyboardButton(
                "📁 Document",
                callback_data="upload_document",
            )
        ]
    ]

    if original_file.media in (
        MessageMediaType.VIDEO,
        MessageMediaType.DOCUMENT,
    ):
        buttons.append([
            InlineKeyboardButton(
                "🎥 Video",
                callback_data="upload_video",
            )
        ])
    elif original_file.media == MessageMediaType.AUDIO:
        buttons.append([
            InlineKeyboardButton(
                "🎵 Audio",
                callback_data="upload_audio",
            )
        ])

    selection = await message.reply(
        text=_selection_message(new_name),
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.DISABLED,
    )
    _PENDING_RENAMES[selection.id] = pending


@Client.on_callback_query(filters.regex("^upload"))
async def doc(bot, update):
    status_text = update.message.text or ""
    marker = "File Name :-"

    if marker not in status_text:
        return await update.message.edit(
            "Could not read the selected filename."
        )

    requested_filename = status_text.split(marker, 1)[1].strip()

    if not requested_filename:
        return await update.message.edit("Filename is empty.")

    if (
        "/" in requested_filename
        or "\\" in requested_filename
        or "\x00" in requested_filename
    ):
        return await update.message.edit("Invalid filename.")

    prefix = await jishubotz.get_prefix(update.message.chat.id)
    suffix = await jishubotz.get_suffix(update.message.chat.id)

    new_filename = _normalize_filename(
        _add_prefix_suffix(
            requested_filename,
            prefix,
            suffix,
        )
    )

    # Keep Telegram usernames intact; _normalize_filename handles other underscores.
    print(f"Requested upload filename: {new_filename!r}")

    work_dir = os.path.abspath(
        os.path.join(
            "downloads",
            str(update.from_user.id),
            f"job_{time.time_ns()}",
        )
    )

    os.makedirs(work_dir, exist_ok=True)

    file_path = os.path.join(work_dir, new_filename)
    metadata_file_path = None
    thumb_path = None
    screenshot_path = None

    original_file = getattr(update, "original_file", None)
    source_file_id = getattr(update, "source_file_id", None)

    if original_file is None:
        pending = _PENDING_RENAMES.get(update.message.id)
        if pending:
            media_obj = SimpleNamespace(
                file_id=pending["file_id"],
                file_name=pending["file_name"],
                file_size=pending["file_size"],
                mime_type=pending["mime_type"],
                dc_id=pending["dc_id"],
                thumbs=pending["thumbs"],
            )
            original_file = SimpleNamespace(
                id=pending["original_message_id"],
                media=pending["media_type"],
                **{pending["media_type"].value: media_obj},
            )
            source_file_id = pending["file_id"]
        else:
            original_file = update.message.reply_to_message

    if original_file is None:
        _safe_remove_dir(work_dir)
        return await update.message.edit(
            "Original file message was not found."
        )

    status = await update.message.edit("🚀 Try To Download... ⚡")

    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        downloaded_path = await bot.download_media(
            message=source_file_id or original_file,
            file_name=file_path,
            progress=progress_for_pyrogram,
            progress_args=(
                "🚀 Try To Downloading... ⚡",
                status,
                time.time(),
            ),
        )

        if not downloaded_path or not os.path.isfile(downloaded_path):
            raise FileNotFoundError("Downloaded file was not created.")

        file_path = os.path.abspath(downloaded_path)

    except Exception as error:
        _safe_remove_dir(work_dir)
        return await status.edit(f"Download error: `{error}`")

    try:
        metadata_enabled = await jishubotz.get_metadata(
            update.message.chat.id
        )

        if metadata_enabled:
            metadata_fields = await jishubotz.get_metadata_fields(
                update.message.chat.id
            )

            if metadata_fields:
                metadata_dir = os.path.join(work_dir, "Metadata")
                os.makedirs(metadata_dir, exist_ok=True)

                metadata_target = os.path.join(
                    metadata_dir,
                    new_filename,
                )

                metadata_file_path = await add_metadata(
                    file_path,
                    metadata_target,
                    metadata_fields,
                    status,
                )

        else:
            await status.edit("⏳ Mode Changing... ⚡")

        upload_path = (
            metadata_file_path
            if metadata_file_path and os.path.isfile(metadata_file_path)
            else file_path
        )

        duration = 0
        parser = None

        try:
            parser = createParser(file_path)

            if parser:
                parsed_metadata = extractMetadata(parser)

                if parsed_metadata and parsed_metadata.has("duration"):
                    duration = parsed_metadata.get("duration").seconds

        except Exception as error:
            print(f"Duration error: {error}")

        finally:
            if parser:
                parser.close()

        media = _get_media(original_file)

        if not media:
            return await status.edit("Could not read original media details.")

        custom_caption = await jishubotz.get_caption(
            update.message.chat.id
        )

        custom_thumb = await jishubotz.get_thumbnail(
            update.message.chat.id
        )

        if custom_caption:
            try:
                caption = custom_caption.format(
                    filename=new_filename,
                    filesize=humanbytes(media.file_size),
                    duration=convert(duration),
                )
                caption_parse_mode = None

            except Exception as error:
                return await status.edit(
                    f"Your Caption Error Except Keyword Argument: ({error})"
                )

        else:
            caption = _format_filename_caption(new_filename)
            caption_parse_mode = ParseMode.HTML

        if media.thumbs or custom_thumb:
            if custom_thumb:
                try:
                    thumb_path = await bot.download_media(custom_thumb)

                    if thumb_path:
                        _, _, thumb_path = await fix_thumb(thumb_path)

                except Exception as error:
                    thumb_path = None
                    print(f"Custom thumbnail error: {error}")

            else:
                try:
                    screenshot_time = random.randint(
                        0,
                        max(duration - 1, 0),
                    )

                    screenshot_path = await take_screen_shot(
                        file_path,
                        work_dir,
                        screenshot_time,
                    )

                    if screenshot_path:
                        _, _, thumb_path = await fix_thumb(screenshot_path)

                except Exception as error:
                    thumb_path = None
                    print(f"Screenshot error: {error}")

        await status.edit("💠 Try To Upload... ⚡")

        output_type = update.data.split("_", 1)[1]

        common = {
            "caption": caption,
            "parse_mode": caption_parse_mode,
            "thumb": thumb_path,
            "progress": progress_for_pyrogram,
            "progress_args": (
                "💠 Try To Uploading... ⚡",
                status,
                time.time(),
            ),
        }

        # Pass the exact filename directly to each upload method.
        if output_type == "document":
            await bot.send_document(
                update.message.chat.id,
                document=upload_path,
                file_name=new_filename,
                **common,
            )

        elif output_type == "video":
            await bot.send_video(
                update.message.chat.id,
                video=upload_path,
                duration=duration,
                file_name=new_filename,
                **common,
            )

        elif output_type == "audio":
            await bot.send_audio(
                update.message.chat.id,
                audio=upload_path,
                duration=duration,
                file_name=new_filename,
                **common,
            )

        else:
            return await status.edit("Unknown output format selected.")

        await status.delete()
        _PENDING_RENAMES.pop(update.message.id, None)

    except FloodWait as error:
        await sleep(error.value)
        try:
            await status.edit(
                "Telegram asked the bot to wait. Please try again."
            )
        except Exception:
            pass

    except Exception as error:
        print(f"Rename/upload error: {error}")

        try:
            await status.edit(f"Error: `{error}`")
        except Exception:
            pass

    finally:
        _safe_remove(thumb_path)
        _safe_remove(screenshot_path)
        _safe_remove_dir(work_dir)
        
