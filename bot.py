from datetime import datetime
from pytz import timezone

from pyrogram import Client, __version__
from pyrogram.raw.all import layer
from config import Config
from aiohttp import web
from route import web_server

import pyromod
import pyrogram.utils


pyrogram.utils.MIN_CHANNEL_ID = -100999999999999


class Bot(Client):

    def __init__(self):
        super().__init__(
            name="renamer",
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            bot_token=Config.BOT_TOKEN,
            workers=200,
            plugins={"root": "plugins"},
            sleep_threshold=15,
            # Permit parallel Telegram file-part transfers. This can improve
            # download throughput while keeping concurrency at a conservative
            # level to avoid overwhelming the Railway instance/network.
            max_concurrent_transmissions=8,
        )

    async def start(self):
        await super().start()

        me = await self.get_me()
        self.mention = me.mention
        self.username = me.username
        self.uptime = Config.BOT_UPTIME

        if Config.WEBHOOK:
            app = web.AppRunner(await web_server())
            await app.setup()
            await web.TCPSite(app, "0.0.0.0", 8080).start()

        print(f"{me.first_name} Is Started.....✨️")

        for id in Config.ADMIN:
            try:
                await self.send_message(
                    id,
                    f"**{me.first_name} Is Started...**"
                )
            except Exception:
                pass

        if Config.LOG_CHANNEL:
            try:
                curr = datetime.now(timezone("Asia/Kolkata"))
                date = curr.strftime('%d %B, %Y')
                current_time = curr.strftime('%I:%M:%S %p')

                await self.send_message(
                    Config.LOG_CHANNEL,
                    f"**{me.mention} Is Restarted !!**\n\n"
                    f"📅 Date : `{date}`\n"
                    f"⏰ Time : `{current_time}`\n"
                    f"🌐 Timezone : `Asia/Kolkata`\n\n"
                    f"🉐 Version : `v{__version__} (Layer {layer})`"
                )

            except Exception:
                print("Please Make This Bot Admin In Your Log Channel")


Bot().run()


# Original project attribution:
# AnimeYaroo
# Telegram Channel @AnimeYaroo
# Backup Channel @AnimeYaroo
# Developer @AnimeYaroo
# Contact @AnimeYaroo
