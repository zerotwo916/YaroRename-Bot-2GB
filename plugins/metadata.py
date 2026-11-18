from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from helper.database import jishubotz


FIELDS = {
    "title": ("settitle", "deltitle", "File title"),
    "author": ("setauthor", "delauthor", "Author"),
    "artist": ("setartist", "delartist", "Artist"),
    "video": ("setvideo", "delvideo", "Video track name"),
    "audio": ("setaudio", "delaudio", "Audio track name"),
    "subtitle": ("setsubtitle", "delsubtitle", "Subtitle track name"),
}

SET_HELP = (
    "**Metadata SET mode is active.**\n\n"
    "Use the commands below with the name you want:\n"
    "`/settitle Your title`\n"
    "`/setauthor Your author`\n"
    "`/setartist Your artist`\n"
    "`/setvideo Your video name`\n"
    "`/setaudio Your audio name`\n"
    "`/setsubtitle Your subtitle name`\n\n"
    "You can set more than one field. Open `/metadata` again to change mode."
)

DELETE_HELP = (
    "**Metadata DELETE mode is active.**\n\n"
    "Use the command for the field you want to clear:\n"
    "`/deltitle`\n"
    "`/delauthor`\n"
    "`/delartist`\n"
    "`/delvideo`\n"
    "`/delaudio`\n"
    "`/delsubtitle`\n\n"
    "You can delete more than one field. Open `/metadata` again to change mode."
)


def metadata_keyboard(enabled):
    status = "ON ✅" if enabled else "OFF ❌"
    toggle_data = "meta:toggle_off" if enabled else "meta:toggle_on"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Metadata: {status}", callback_data=toggle_data)],
        [
            InlineKeyboardButton("✏️ SET fields", callback_data="meta:mode_set"),
            InlineKeyboardButton("🗑 DELETE fields", callback_data="meta:mode_delete"),
        ],
    ])


@Client.on_message(filters.private & filters.command("metadata"))
async def handle_metadata(client: Client, message: Message):
    user_id = message.from_user.id
    enabled = await jishubotz.get_metadata(user_id)
    fields = await jishubotz.get_metadata_fields(user_id)
    mode = await jishubotz.get_metadata_mode(user_id)

    def show(value):
        if value is None:
            return "Original value (unchanged)"
        if value == "":
            return "Cleared"
        return value

    text = (
        "**⚙️ Independent Metadata Settings**\n\n"
        f"**Metadata processing:** {'ON ✅' if enabled else 'OFF ❌'}\n"
        f"**Current command mode:** `{mode or 'Not selected'}`\n\n"
        "**Saved fields:**\n"
        f"• Title: `{show(fields.get('title'))}`\n"
        f"• Author: `{show(fields.get('author'))}`\n"
        f"• Artist: `{show(fields.get('artist'))}`\n"
        f"• Video: `{show(fields.get('video'))}`\n"
        f"• Audio: `{show(fields.get('audio'))}`\n"
        f"• Subtitle: `{show(fields.get('subtitle'))}`\n\n"
        "Choose SET or DELETE mode. The field commands only work after you choose a mode here."
    )
    await message.reply_text(
        text,
        quote=True,
        reply_markup=metadata_keyboard(enabled)
    )


@Client.on_callback_query(filters.regex(r"^meta:"), group=1)
async def metadata_callbacks(client: Client, query: CallbackQuery):
    if not query.message or query.from_user.id != query.message.chat.id:
        await query.answer("This menu is not for you.", show_alert=True)
        return

    data = query.data

    if data == "meta:mode_set":
        await jishubotz.set_metadata_mode(query.from_user.id, "set")
        await query.answer("SET mode enabled")
        await query.message.edit_text(SET_HELP)
        return

    if data == "meta:mode_delete":
        await jishubotz.set_metadata_mode(query.from_user.id, "delete")
        await query.answer("DELETE mode enabled")
        await query.message.edit_text(DELETE_HELP)
        return

    if data == "meta:toggle_on":
        await jishubotz.set_metadata(query.from_user.id, True)
    elif data == "meta:toggle_off":
        await jishubotz.set_metadata(query.from_user.id, False)
    else:
        await query.answer()
        return

    enabled = await jishubotz.get_metadata(query.from_user.id)
    fields = await jishubotz.get_metadata_fields(query.from_user.id)
    mode = await jishubotz.get_metadata_mode(query.from_user.id)

    def show(value):
        if value is None:
            return "Original value (unchanged)"
        if value == "":
            return "Cleared"
        return value

    text = (
        "**⚙️ Independent Metadata Settings**\n\n"
        f"**Metadata processing:** {'ON ✅' if enabled else 'OFF ❌'}\n"
        f"**Current command mode:** `{mode or 'Not selected'}`\n\n"
        "**Saved fields:**\n"
        f"• Title: `{show(fields.get('title'))}`\n"
        f"• Author: `{show(fields.get('author'))}`\n"
        f"• Artist: `{show(fields.get('artist'))}`\n"
        f"• Video: `{show(fields.get('video'))}`\n"
        f"• Audio: `{show(fields.get('audio'))}`\n"
        f"• Subtitle: `{show(fields.get('subtitle'))}`\n\n"
        "Choose SET or DELETE mode. The field commands only work after you choose a mode here."
    )
    await query.message.edit_text(text, reply_markup=metadata_keyboard(enabled))


async def _set_field(message: Message, field: str, label: str):
    user_id = message.from_user.id
    mode = await jishubotz.get_metadata_mode(user_id)

    if mode != "set":
        return await message.reply_text(
            "First open `/metadata` and choose **SET fields**.",
            quote=True
        )

    # Preserve spaces inside the supplied value; trim only its outer whitespace.
    value = message.text.partition(" ")[2].strip()
    if not value:
        command = FIELDS[field][0]
        return await message.reply_text(
            f"**Please provide a value.**\n\nExample: `/{command} Your {label.lower()}`",
            quote=True
        )

    await jishubotz.set_metadata_field(user_id, field, value)
    await message.reply_text(f"**{label} metadata saved successfully ✅**", quote=True)


async def _delete_field(message: Message, field: str, label: str):
    user_id = message.from_user.id
    mode = await jishubotz.get_metadata_mode(user_id)

    if mode != "delete":
        return await message.reply_text(
            "First open `/metadata` and choose **DELETE fields**.",
            quote=True
        )

    # Empty string is a deliberate clear operation, distinct from an untouched field.
    await jishubotz.set_metadata_field(user_id, field, "")
    await message.reply_text(f"**{label} metadata will be cleared ✅**", quote=True)


# Register the twelve metadata commands. These handlers are intentionally
# restricted to the selected mode and do not affect any other bot settings.
@Client.on_message(filters.private & filters.command("settitle"))
async def set_title(client, message):
    await _set_field(message, "title", "File title")


@Client.on_message(filters.private & filters.command("setauthor"))
async def set_author(client, message):
    await _set_field(message, "author", "Author")


@Client.on_message(filters.private & filters.command("setartist"))
async def set_artist(client, message):
    await _set_field(message, "artist", "Artist")


@Client.on_message(filters.private & filters.command("setvideo"))
async def set_video(client, message):
    await _set_field(message, "video", "Video track")


@Client.on_message(filters.private & filters.command("setaudio"))
async def set_audio(client, message):
    await _set_field(message, "audio", "Audio track")


@Client.on_message(filters.private & filters.command("setsubtitle"))
async def set_subtitle(client, message):
    await _set_field(message, "subtitle", "Subtitle track")


@Client.on_message(filters.private & filters.command("deltitle"))
async def delete_title(client, message):
    await _delete_field(message, "title", "File title")


@Client.on_message(filters.private & filters.command("delauthor"))
async def delete_author(client, message):
    await _delete_field(message, "author", "Author")


@Client.on_message(filters.private & filters.command("delartist"))
async def delete_artist(client, message):
    await _delete_field(message, "artist", "Artist")


@Client.on_message(filters.private & filters.command("delvideo"))
async def delete_video(client, message):
    await _delete_field(message, "video", "Video track")


@Client.on_message(filters.private & filters.command("delaudio"))
async def delete_audio(client, message):
    await _delete_field(message, "audio", "Audio track")


@Client.on_message(filters.private & filters.command("delsubtitle"))
async def delete_subtitle(client, message):
    await _delete_field(message, "subtitle", "Subtitle track")
