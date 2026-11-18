
import os
import re
import time

id_pattern = re.compile(r'^.\d+$')


class Config(object):
    # Pyrogram client configuration
    API_ID = os.environ.get("API_ID", "")
    API_HASH = os.environ.get("API_HASH", "")
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

    # MongoDB configuration
    DATABASE_NAME = os.environ.get("DATABASE_NAME", "")
    DATABASE_URL = os.environ.get("DATABASE_URL", "")

    # Other configuration
    BOT_UPTIME = time.time()
    START_PIC = os.environ.get("START_PIC", "")

    ADMIN = [
        int(admin) if id_pattern.search(admin) else admin
        for admin in os.environ.get("ADMIN", "").split()
    ]

    # Channel configuration
    FORCE_SUBS = os.environ.get("FORCE_SUBS", "")

    _log_channel = os.environ.get("LOG_CHANNEL", "").strip()
    LOG_CHANNEL = int(_log_channel) if _log_channel else None

    # Only explicit true-like values enable webhook mode.
    WEBHOOK = os.environ.get("WEBHOOK", "").strip().lower() in {
        "1", "true", "yes", "on"
    }


class Txt(object):
    START_TXT = """Hello {} 👋

➻ This Is An Advanced And Yet Powerful Rename Bot.

➻ Using This Bot You Can Rename And Change Thumbnail Of Your Files.

➻ You Can Also Convert Video To File And File To Video.
➻ This Bot Also Supports Custom Thumbnail And Custom Caption.

<b>Bot Is Made By :</b> @AnimeYaroo"""

    ABOUT_TXT = """
╭───────────────⍟
├<b>🤖 My Name</b> : {}
├<b>🖥️ Developer</b> : <a href="https://t.me/AnimeYaroo">@AnimeYaroo</a>
├<b>👨‍💻 Programmer</b> : <a href="https://t.me/AnimeYaroo">@AnimeYaroo</a>
├<b>📕 Library</b> : <a href="https://github.com/pyrogram">Pyrogram</a>
├<b>✏️ Language</b> : <a href="https://www.python.org">Python 3</a>
├<b>💾 Database</b> : <a href="https://cloud.mongodb.com">Mongo DB</a>
├<b>📊 Build Version</b> : Rename v4.7.0
╰───────────────⍟
"""

    HELP_TXT = """
🌌 <b><u>How To Set Thumbnail</u></b>

➪ /start - Start The Bot And Send Any Photo To Automatically Set Thumbnail.
➪ /del_thumb - Use This Command To Delete Your Old Thumbnail.
➪ /view_thumb - Use This Command To View Your Current Thumbnail.

📑 <b><u>How To Set Custom Caption</u></b>
➪ /set_caption - Use This Command To Set A Custom Caption
➪ /see_caption - Use This Command To View Your Custom Caption
➪ /del_caption - Use This Command To Delete Your Custom Caption
➪ Example - <code>/set_caption 📕 Name ➠ : {filename}

🔗 Size ➠ : {filesize}

⏰ Duration ➠ : {duration}</code>

✏️ <b><u>How To Rename A File</u></b>

➪ Send Any File, tap Rename, enter the new filename, and select the output format.
𝗔𝗻𝘆 𝗢𝘁𝗵𝗲𝗿 𝗛𝗲𝗹𝗽 𝗖𝗼𝗻𝘁𝗮𝗰𝘁 :- <a href="https://t.me/AnimeYaroo">Developer</a>
"""

    PROGRESS_BAR = """\n
 <b>🔗 Size :</b> {1} | {2}
 <b>⏳️ Done :</b> {0}%
 <b>🚀 Speed :</b> {3}/s
 <b>⏰️ ETA :</b> {4}
"""

    DONATE_TXT = """
<b>🥲 Thanks For Showing Interest In Donation! ❤️</b>

If You Like My Bots & Projects, You Can 🎁 Donate Me Any Amount From 10 Rs Upto Your Choice.

<b>🛍 UPI ID:</b> <code>qwerty02@airtel</code>
"""

    SEND_METADATA = """<b><u>🖼️ HOW TO SET CUSTOM METADATA</u></b>

For Example :-
<code>By :- @AnimeYaroo</code>

💬 For Any Help Contact @AnimeYaroo
"""


# Original project attribution is retained in the source files.

# Original project attribution:
# AnimeYaroo
# Telegram Channel @AnimeYaroo
# Backup Channel @AnimeYaroo
# Developer @AnimeYaroo
# Contact @AnimeYaroo
