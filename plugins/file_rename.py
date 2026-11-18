
from pyrogram import Client, filters
from pyrogram.enums import MessageMediaType, ParseMode
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from hachoir.metadata import extractMetadata
from helper.ffmpeg import fix_thumb, take_screen_shot, add_metadata
from hachoir.parser import createParser
from helper.utils import progress_for_pyrogram, convert, humanbytes, add_prefix_suffix
from helper.database import jishubotz
from asyncio import sleep
from PIL import Image
from types import SimpleNamespace
import os, time, re, random, asyncio, html


@Client.on_message(filters.private & (filters.document | filters.audio | filters.video))
async def rename_start(client, message):
    media = getattr(message, message.media.value)
    filename = media.file_name or f"file_{message.id}"
    extension = os.path.splitext(filename)[1] or "Not available"
    mime_type = getattr(media, "mime_type", None) or "Not available"
    dc_id = getattr(media, "dc_id", None)
    dc_text = str(dc_id) if dc_id is not None else "Not available"

    if media.file_size > 2000 * 1024 * 1024:
        return await message.reply_text(
            "Sorry Bro This Bot Doesn't Support Uploading Files Bigger Than 2GB",
            quote=True
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
        [InlineKeyboardButton("✏️ Rename", callback_data="rename_file"),
         InlineKeyboardButton("✖️ Cancel", callback_data="cancel_rename")]
    ])

    # Reuse Telegram's existing media thumbnail when one is available.
    thumbs = getattr(media, "thumbs", None) or []
    if thumbs:
        try:
            await message.reply_photo(
                photo=thumbs[-1].file_id,
                caption=info,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
                reply_to_message_id=message.id
            )
            return
        except Exception as e:
            print(f"Could not display media thumbnail: {e}")

    await message.reply_text(
        text=info,
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard,
        reply_to_message_id=message.id
    )


@Client.on_callback_query(filters.regex("^rename_file$"))
async def start_rename_prompt(client, query):
    original_file = query.message.reply_to_message if query.message else None
    if not original_file:
        await query.answer("Original file not found. Please send it again.", show_alert=True)
        return

    # Keep the ForceReply prompt attached to the original media message.
    # The existing rename handler reads the original file from this reply.
    await original_file.reply_text(
        "**Please Enter The New Filename.**",
        reply_markup=ForceReply(True),
        quote=True
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

    if (reply_message.reply_markup) and isinstance(reply_message.reply_markup, ForceReply):
        new_name = message.text

        if not new_name:
            return

        await message.delete()

        msg = await client.get_messages(message.chat.id, reply_message.id)
        file = msg.reply_to_message

        if not file:
            return await message.reply_text(
                "**Could not find the original file. Please send it again.**"
            )

        media = getattr(file, file.media.value)

        if "." not in new_name:
            if "." in media.file_name:
                extn = media.file_name.rsplit('.', 1)[-1]
            else:
                extn = "mkv"

            new_name = new_name + "." + extn

        await reply_message.delete()

        # Read the user's saved output mode.
        saved_mode = await jishubotz.get_output_mode(message.from_user.id)

        # Automatically send as Document.
        if saved_mode == "document":
            status = await message.reply(
                text=f"**Select The Output File Type**\n\n**File Name :-** `{new_name}`",
                reply_to_message_id=file.id
            )

            automatic_update = SimpleNamespace(
                message=status,
                data="upload_document",
                from_user=message.from_user,
                original_file=file
            )

            await doc(client, automatic_update)
            return

        # Automatically send video/document files as Video.
        if saved_mode == "video" and file.media in [
            MessageMediaType.VIDEO,
            MessageMediaType.DOCUMENT
        ]:
            status = await message.reply(
                text=f"**Select The Output File Type**\n\n**File Name :-** `{new_name}`",
                reply_to_message_id=file.id
            )

            automatic_update = SimpleNamespace(
                message=status,
                data="upload_video",
                from_user=message.from_user,
                original_file=file
            )

            await doc(client, automatic_update)
            return

        # No saved mode: show the original selection buttons.
        button = [
            [InlineKeyboardButton("📁 Document", callback_data="upload_document")]
        ]

        if file.media in [MessageMediaType.VIDEO, MessageMediaType.DOCUMENT]:
            button.append(
                [InlineKeyboardButton("🎥 Video", callback_data="upload_video")]
            )

        elif file.media == MessageMediaType.AUDIO:
            button.append(
                [InlineKeyboardButton("🎵 Audio", callback_data="upload_audio")]
            )

        await message.reply(
            text=f"**Select The Output File Type**\n\n**File Name :-** `{new_name}`",
            reply_to_message_id=file.id,
            reply_markup=InlineKeyboardMarkup(button)
        )


@Client.on_callback_query(filters.regex("^upload"))
async def doc(bot, update):
    os.makedirs("Metadata", exist_ok=True)

    prefix = await jishubotz.get_prefix(update.message.chat.id)
    suffix = await jishubotz.get_suffix(update.message.chat.id)

    new_name = update.message.text
    new_filename_ = new_name.split(":-", 1)[1]

    try:
        new_filename = add_prefix_suffix(new_filename_, prefix, suffix)

    except Exception as e:
        return await update.message.edit(
            f"Something Went Wrong Can't Able To Set Prefix Or Suffix 🥺\n\n"
            f"**Contact My Creator :** @CallAdminRobot\n\n**Error :** `{e}`"
        )

    file_path = os.path.join(
        "downloads",
        str(update.from_user.id),
        new_filename
    )

    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    # IMPORTANT: Automatic mode supplies original_file directly.
    # Normal button mode continues using reply_to_message.
    file = getattr(update, "original_file", None)

    if file is None:
        file = update.message.reply_to_message

    if file is None:
        return await update.message.edit(
            "**Download error:** Original file message was not found. Please send the file again."
        )

    ms = await update.message.edit("🚀 Try To Download... ⚡")

    try:
        path = await bot.download_media(
            message=file,
            file_name=file_path,
            progress=progress_for_pyrogram,
            progress_args=("🚀 Try To Downloading... ⚡", ms, time.time())
        )

        if not path:
            return await ms.edit("**Download failed. Please try again.**")

        file_path = path

    except Exception as e:
        return await ms.edit(f"**Download error:** `{e}`")

    # Existing metadata processing.
    metadata_file_path = None
    metadata_enabled = await jishubotz.get_metadata(update.message.chat.id)

    if metadata_enabled:
        metadata_fields = await jishubotz.get_metadata_fields(update.message.chat.id)

        if metadata_fields:
            metadata_file_path = os.path.join("Metadata", new_filename)

            metadata_file_path = await add_metadata(
                file_path,
                metadata_file_path,
                metadata_fields,
                ms
            )

    else:
        await ms.edit("⏳ Mode Changing... ⚡")

    upload_path = (
        metadata_file_path
        if metadata_file_path and os.path.exists(metadata_file_path)
        else file_path
    )

    duration = 0

    try:
        parser = createParser(file_path)

        if parser:
            metadata = extractMetadata(parser)

            if metadata and metadata.has("duration"):
                duration = metadata.get("duration").seconds

            parser.close()

    except:
        pass

    ph_path = None
    media = getattr(file, file.media.value)

    c_caption = await jishubotz.get_caption(update.message.chat.id)
    c_thumb = await jishubotz.get_thumbnail(update.message.chat.id)

    if c_caption:
        try:
            caption = c_caption.format(
                filename=new_filename,
                filesize=humanbytes(media.file_size),
                duration=convert(duration)
            )

        except Exception as e:
            return await ms.edit(
                f"Your Caption Error Except Keyword Argument : ({e})"
            )

    else:
        caption = f"**{new_filename}**"

    if media.thumbs or c_thumb:
        if c_thumb:
            ph_path = await bot.download_media(c_thumb)
            width, height, ph_path = await fix_thumb(ph_path)

        else:
            try:
                shot_time = random.randint(0, max(duration - 1, 0))

                ph_path_ = await take_screen_shot(
                    file_path,
                    os.path.dirname(os.path.abspath(file_path)),
                    shot_time
                )

                width, height, ph_path = await fix_thumb(ph_path_)

            except Exception as e:
                ph_path = None
                print(e)

    await ms.edit("💠 Try To Upload... ⚡")

    output_type = update.data.split("_", 1)[1]

    try:
        if output_type == "document":
            await bot.send_document(
                update.message.chat.id,
                document=upload_path,
                thumb=ph_path,
                caption=caption,
                progress=progress_for_pyrogram,
                progress_args=("💠 Try To Uploading... ⚡", ms, time.time())
            )

        elif output_type == "video":
            await bot.send_video(
                update.message.chat.id,
                video=upload_path,
                caption=caption,
                thumb=ph_path,
                duration=duration,
                progress=progress_for_pyrogram,
                progress_args=("💠 Try To Uploading... ⚡", ms, time.time())
            )

        elif output_type == "audio":
            await bot.send_audio(
                update.message.chat.id,
                audio=upload_path,
                caption=caption,
                thumb=ph_path,
                duration=duration,
                progress=progress_for_pyrogram,
                progress_args=("💠 Try To Uploading... ⚡", ms, time.time())
            )

    except Exception as e:
        for cleanup_path in (file_path, metadata_file_path, ph_path):
            if cleanup_path and os.path.exists(cleanup_path):
                try:
                    os.remove(cleanup_path)
                except OSError:
                    pass

        return await ms.edit(f"**Error :** `{e}`")

    await ms.delete()

    for cleanup_path in (file_path, metadata_file_path, ph_path):
        if cleanup_path and os.path.exists(cleanup_path):
            try:
                os.remove(cleanup_path)
            except OSError:
                pass
                
