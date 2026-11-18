
from pyrogram import Client, filters
from helper.database import jishubotz


@Client.on_message(filters.private & filters.command("mode"))
async def set_output_mode(client, message):
    user_id = message.from_user.id

    if len(message.command) < 2:
        current = await jishubotz.get_output_mode(user_id)

        if not current:
            current = "ask"

        return await message.reply_text(
            f"**Current Output Mode:** `{current.upper()}`\n\n"
            "**Available Commands:**\n"
            "`/mode document` - Always send as Document\n"
            "`/mode video` - Always send as Video\n"
            "`/mode ask` - Ask for output type every time",
            quote=True
        )

    mode = message.command[1].lower()

    if mode not in ["document", "video", "ask"]:
        return await message.reply_text(
            "**Invalid mode!**\n\n"
            "Use `/mode document`, `/mode video`, or `/mode ask`.",
            quote=True
        )

    if mode == "ask":
        await jishubotz.clear_output_mode(user_id)

        return await message.reply_text(
            "✅ **Output mode reset successfully!**\n\n"
            "The bot will ask you to select the output type every time.",
            quote=True
        )

    await jishubotz.set_output_mode(user_id, mode)

    await message.reply_text(
        f"✅ **Output mode saved: {mode.upper()}**\n\n"
        "Your selected format will now be used automatically.\n"
        "The bot will still ask you for a new filename every time.",
        quote=True
    )
  
