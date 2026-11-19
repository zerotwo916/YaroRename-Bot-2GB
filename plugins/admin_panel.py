
import os, sys, time, asyncio, logging, datetime
import aiohttp
from datetime import timezone, timedelta
from config import Config
from pyrogram import Client, filters
from helper.database import jishubotz
from pyrogram.types import Message
from pyrogram.errors import FloodWait, InputUserDeactivated, UserIsBlocked, PeerIdInvalid


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
 




@Client.on_message(filters.command(["stats", "status", "s"]) & filters.user(Config.ADMIN))
async def get_stats(bot, message):
    total_users = await jishubotz.total_users_count()
    uptime = time.strftime("%Hh%Mm%Ss", time.gmtime(time.time() - bot.uptime))    
    start_t = time.time()
    st = await message.reply('**Processing The Details.....**', quote=True)    
    end_t = time.time()
    time_taken_s = (end_t - start_t) * 1000
    await st.edit(text=f"**--Bot Status--** \n\n**⌚ Bot Uptime:** `{uptime}` \n**🐌 Current Ping:** `{time_taken_s:.3f} ms` \n**👭 Total Users:** `{total_users}`")



@Client.on_message(filters.command(["restart", "r"]) & filters.user(Config.ADMIN))
async def restart_bot(bot, message):
    msg = await bot.send_message(text="🔄 Processes Stoped. Bot Is Restarting...", chat_id=message.chat.id)       
    await asyncio.sleep(3)
    await msg.edit("✅️ Bot Is Restarted. Now You Can Use Me")
    os.execl(sys.executable, sys.executable, *sys.argv)



@Client.on_message(filters.private & filters.command(["ping", "p"]))
async def ping(_, message):
    start_t = time.time()
    rm = await message.reply_text("Pinging....", quote=True)
    end_t = time.time()
    time_taken_s = (end_t - start_t) * 1000
    await rm.edit(f"Ping 🔥!\n{time_taken_s:.3f} ms")
    return time_taken_s



@Client.on_message(filters.command(["broadcast", "b"]) & filters.user(Config.ADMIN) & filters.reply)
async def broadcast_handler(bot: Client, m: Message):
    await bot.send_message(Config.LOG_CHANNEL, f"{m.from_user.mention} or {m.from_user.id} Is Started The Broadcast......")
    all_users = await jishubotz.get_all_users()
    broadcast_msg = m.reply_to_message
    sts_msg = await m.reply_text("Broadcast Started..!", quote=True) 
    done = 0
    failed = 0
    success = 0
    start_time = time.time()
    total_users = await jishubotz.total_users_count()
    async for user in all_users:
        sts = await send_msg(user['_id'], broadcast_msg)
        if sts == 200:
           success += 1
        else:
           failed += 1
        if sts == 400:
           await jishubotz.delete_user(user['_id'])
        done += 1
        if not done % 20:
           await sts_msg.edit(f"**Broadcast In Progress:** \n\nTotal Users {total_users} \nCompleted: {done} / {total_users}\nSuccess: {success}\nFailed: {failed}")
    completed_in = datetime.timedelta(seconds=int(time.time() - start_time))
    await sts_msg.edit(f"**Broadcast Completed:** \n\nCompleted In `{completed_in}`.\n\nTotal Users {total_users}\nCompleted: {done} / {total_users}\nSuccess: {success}\nFailed: {failed}")
           
async def send_msg(user_id, message):
    try:
        await message.copy(chat_id=int(user_id))
        return 200
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return send_msg(user_id, message)
    except InputUserDeactivated:
        logger.info(f"{user_id} : Deactivated")
        return 400
    except UserIsBlocked:
        logger.info(f"{user_id} : Blocked The Bot")
        return 400
    except PeerIdInvalid:
        logger.info(f"{user_id} : User ID Invalid")
        return 400
    except Exception as e:
        logger.error(f"{user_id} : {e}")
        return 500
 







# Jishu Developer 
# Don't Remove Credit 🥺
# Telegram Channel @MadflixBotz
# Backup Channel @JishuBotz
# Developer @JishuDeveloper
# Contact @MadflixSupport

# Track private-chat message IDs as updates arrive. Telegram bots cannot read
# chat history through MTProto, so /clear can only remove messages observed
# since this process started (and still inside Telegram's 48-hour window).
_tracked_private_messages = {}


@Client.on_message(filters.private, group=999)
async def track_private_chat_messages(_, message):
    try:
        sent_at = message.date
        if sent_at and sent_at.tzinfo is None:
            sent_at = sent_at.replace(tzinfo=timezone.utc)
        timestamp = sent_at.timestamp() if sent_at else time.time()
        chat_id = message.chat.id
        messages = _tracked_private_messages.setdefault(chat_id, {})
        cutoff_timestamp = time.time() - (48 * 60 * 60)

        # Keep only deletable recent messages and cap memory use per chat.
        messages = {
            message_id: created_at
            for message_id, created_at in messages.items()
            if created_at >= cutoff_timestamp
        }
        messages[message.id] = timestamp

        if len(messages) > 5000:
            messages = dict(sorted(messages.items(), key=lambda item: item[1])[-5000:])

        _tracked_private_messages[chat_id] = messages
    except Exception:
        logger.exception("Could not track private message ID")


async def _delete_private_message(session, chat_id, message_id, semaphore):
    url = f"https://api.telegram.org/bot{Config.BOT_TOKEN}/deleteMessage"
    async with semaphore:
        try:
            async with session.post(
                url,
                json={"chat_id": chat_id, "message_id": message_id},
                timeout=aiohttp.ClientTimeout(total=20),
            ) as response:
                result = await response.json()
                if response.status == 200 and result.get("ok"):
                    return message_id, True
                logger.warning(
                    "Telegram could not delete private message %s: %s",
                    message_id,
                    result.get("description", "Unknown Bot API error"),
                )
        except Exception:
            logger.exception("Delete request failed for message %s", message_id)

    return message_id, False


@Client.on_message(filters.private & filters.command("clear"))
async def clear_private_chat(client, message):
    """Delete tracked recent private-chat messages without touching saved settings."""
    chat_id = message.chat.id
    now = time.time()
    cutoff_timestamp = now - (48 * 60 * 60)

    # The tracker runs in a later handler group, so include /clear explicitly.
    tracked = _tracked_private_messages.setdefault(chat_id, {})
    tracked[message.id] = now
    message_ids = [
        message_id
        for message_id, created_at in tracked.items()
        if created_at >= cutoff_timestamp
    ]

    if not message_ids:
        return

    semaphore = asyncio.Semaphore(10)
    try:
        async with aiohttp.ClientSession() as session:
            results = await asyncio.gather(
                *(
                    _delete_private_message(session, chat_id, message_id, semaphore)
                    for message_id in message_ids
                )
            )

        # Retain failed IDs so a later /clear can retry them.
        _tracked_private_messages[chat_id] = {
            message_id: tracked[message_id]
            for message_id, deleted in results
            if not deleted and message_id in tracked
        }
    except Exception:
        logger.exception(" /clear failed for chat %s", chat_id)
