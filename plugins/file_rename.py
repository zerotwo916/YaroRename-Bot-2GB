
import os
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


def _get_media(message):
    if not message or not message.media:
        return None
    return getattr(message, message.media.value, None)


def _add_prefix_suffix(filename, prefix=None, suffix=None):
    stem, extension = os.path.splitext(filename)
    prefix = prefix or ""
    suffix = suffix or ""
    return f"{prefix}{stem}{(' ' + suffix) if suffix else ''}{extension}"


def _selection_message(filename):
    return (
        "Select The Output File Type\n\n"
        f"File Name :- {filename}"
    )


def _safe_remove(path):
    if path and os.path.isfile(path):
        try:
            os.remove(path)
        except OSError as error:
            print(f"Cleanup error for {path}: {error}")


def _safe_remove_dir(path):
    if path and os.path.isdir(path):
        try:
            shutil.rmtree(path, ignore_errors=True)
        except OSError as error:
            print(f"Directory cleanup error for {path}: {error}")


@Client.on_message(filters.private & (filters.document | filters.audio | filters.video))
async def rename_start(client, message):
    media = _get_media(message)
    if not media:
        return

    filename = media.file_name or f"file_{message.id}"
    extension = os.path.splitext(filename)[1] or "Not available"
    mime_type = getattr(media, "mime_type", None) or "Not available"
    dc_id = getattr(media, "dc_id", None)
    dc_text = str(dc_id) if dc_id is not None else "Not available"

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
        f"◈ <b>DC ID:</b> <code>{html.escape(dc_text)}</code>"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✏️ Rename", callback_data="rename_file"),
            InlineKeyboardButton("✖️ Cancel", callback_data="cancel_rename"),
        ]
    ])

    thumbs = getattr(media, "thumbs", None) or []

    if thumbs:
        try:
            await message.reply_photo(
                photo=thumbs[-1].file_id,
                caption=info,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
                reply_to_message_id=message.id,
            )
            return
        except Exception as error:
            print(f"Could not display media thumbnail: {error}")

    await message.reply_text(
        text=info,
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard,
        reply_to_message_id=message.id,
    )


@Client.on_callback_query(filters.regex("^rename_file$"))
async def start_rename_prompt(client, query):
    original_file = query.message.reply_to_message if query.message else None

    if not original_file:
        await query.answer(
            "Original file not found. Please send it again.",
            show_alert=True,
        )
        return

    await original_file.reply_text(
        "Please Enter The New Filename.",
        reply_markup=ForceReply(True),
        quote=True,
        parse_mode=ParseMode.DISABLED,
    )

    await query.message.delete()
    await query.answer("Now send the new filename.")


@Client.on_callback_query(filters.regex("^cancel_rename$"))
async def cancel_rename(client, query):
    await query.answer("Rename cancelled.")
    if query.message:
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
        await message.reply_text(
            "Please send only a filename, without folder paths."
        )
        return

    await message.delete()

    prompt_message = await client.get_messages(
        message.chat.id,
        reply_message.id,
    )

    original_file = (
        prompt_message.reply_to_message
        if prompt_message else None
    )

    if not original_file:
        return await message.reply_text(
            "Could not find the original file. Please send it again."
        )

    media = _get_media(original_file)

    if not media:
        return await message.reply_text(
            "The original message has no supported file."
        )

    if not os.path.splitext(new_name)[1]:
        original_filename = media.file_name or "file.mkv"
        original_extension = os.path.splitext(original_filename)[1] or ".mkv"
        new_name += original_extension

    await reply_message.delete()

    saved_mode = await jishubotz.get_output_mode(message.from_user.id)

    if saved_mode == "document":
        status = await message.reply(
            text=_selection_message(new_name),
            reply_to_message_id=original_file.id,
            parse_mode=ParseMode.DISABLED,
        )

        automatic_update = SimpleNamespace(
            message=status,
            data="upload_document",
            from_user=message.from_user,
            original_file=original_file,
        )

        await doc(client, automatic_update)
        return

    if saved_mode == "video" and original_file.media in (
        MessageMediaType.VIDEO,
        MessageMediaType.DOCUMENT,
    ):
        status = await message.reply(
            text=_selection_message(new_name),
            reply_to_message_id=original_file.id,
            parse_mode=ParseMode.DISABLED,
        )

        automatic_update = SimpleNamespace(
            message=status,
            data="upload_video",
            from_user=message.from_user,
            original_file=original_file,
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

    await message.reply(
        text=_selection_message(new_name),
        reply_to_message_id=original_file.id,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.DISABLED,
    )


@Client.on_callback_query(filters.regex("^upload"))
async def doc(bot, update):
    status_text = update.message.text or ""
    marker = "File Name :-"

    if marker not in status_text:
        return await update.message.edit(
            "Could not read the selected filename. Please send the file again."
        )

    requested_filename = status_text.split(marker, 1)[1].strip()

    if not requested_filename:
        return await update.message.edit(
            "Filename is empty. Please send the file again."
        )

    if (
        "/" in requested_filename
        or "\\" in requested_filename
        or "\x00" in requested_filename
    ):
        return await update.message.edit("Invalid filename.")

    prefix = await jishubotz.get_prefix(update.message.chat.id)
    suffix = await jishubotz.get_suffix(update.message.chat.id)

    new_filename = _add_prefix_suffix(
        requested_filename,
        prefix,
        suffix,
    )

    # Give every rename task its own unique working directory.
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

    if original_file is None:
        original_file = update.message.reply_to_message

    if original_file is None:
        _safe_remove_dir(work_dir)
        return await update.message.edit(
            "Download error: Original file message was not found. Please send the file again."
        )

    status = await update.message.edit("🚀 Try To Download... ⚡")

    try:
        # Ensure the destination directory exists immediately before download.
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        downloaded_path = await bot.download_media(
            message=original_file,
            file_name=file_path,
            progress=progress_for_pyrogram,
            progress_args=(
                "🚀 Try To Downloading... ⚡",
                status,
                time.time(),
            ),
        )

        if not downloaded_path or not os.path.isfile(downloaded_path):
            raise FileNotFoundError(
                "Downloaded file was not created. Please try again."
            )

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
            print(f"Could not read media duration: {error}")

        finally:
            if parser:
                parser.close()

        media = _get_media(original_file)

        if not media:
            return await status.edit(
                "Could not read the original media details."
            )

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
            caption = f"<code>{html.escape(new_filename)}</code>"
            caption_parse_mode = ParseMode.HTML

        if media.thumbs or custom_thumb:
            if custom_thumb:
                try:
                    thumb_path = await bot.download_media(custom_thumb)

                    if thumb_path:
                        _, _, thumb_path = await fix_thumb(thumb_path)

                except Exception as error:
                    thumb_path = None
                    print(f"Could not prepare custom thumbnail: {error}")

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
                    print(f"Could not create thumbnail: {error}")

        await status.edit("💠 Try To Upload... ⚡")

        output_type = update.data.split("_", 1)[1]

        common = {
            "caption": caption,
            "parse_mode": caption_parse_mode,
            "thumb": thumb_path,
            "file_name": new_filename,
            "progress": progress_for_pyrogram,
            "progress_args": (
                "💠 Try To Uploading... ⚡",
                status,
                time.time(),
            ),
        }

        if output_type == "document":
            await bot.send_document(
                update.message.chat.id,
                document=upload_path,
                **common,
            )

        elif output_type == "video":
            await bot.send_video(
                update.message.chat.id,
                video=upload_path,
                duration=duration,
                **common,
            )

        elif output_type == "audio":
            await bot.send_audio(
                update.message.chat.id,
                audio=upload_path,
                duration=duration,
                **common,
            )

        else:
            return await status.edit(
                "Unknown output format selected."
            )

        await status.delete()

    except FloodWait as error:
        await sleep(error.value)
        try:
            await status.edit(
                "Telegram asked the bot to wait. Please try the rename again."
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
        # Remove this task's files without affecting another active download.
        _safe_remove(thumb_path)
        _safe_remove(screenshot_path)

        if thumb_path and os.path.abspath(thumb_path).startswith(work_dir):
            pass
        else:
            _safe_remove(thumb_path)

        _safe_remove_dir(work_dir)
        
