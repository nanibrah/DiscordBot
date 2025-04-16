import discord
from discord.ext import commands
import asyncio
import os
from dotenv import load_dotenv
import threading
import datetime
import aiohttp
import subprocess

# Load token
load_dotenv()
TOKEN = os.getenv('DISCORD_BOT_TOKEN')

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="/", intents=intents)

log_user_ids = set()
log_server_ids = set()

DanhSachLenh = """📖 Danh sách lệnh:
  help                     - Gửi lại danh sách lệnh
  say <nội_dung>           - Bot gửi tin nhắn thay bạn.
  clear <số_lượng>         - Xoá số lượng tin nhắn nhất định (1-100).
  clear_all                - Xoá toàn bộ tin nhắn trong kênh.
  channel                  - Đổi kênh gửi lệnh.
  servers                  - Hiển thị danh sách server và kênh.
  dm <user_id> <nội_dung>  - Gửi tin nhắn riêng (DM).
  loguser <user.id>        - Bắt đầu log người dùng.
  unloguser <user.id>      - Dừng log người dùng.
  listloguser              - Liệt kê người đang được log.
  logserver <server_id>    - Bắt đầu log toàn server.
  unlogserver <server_id>  - Dừng log server.
  listlogserver            - Liệt kê các server đang log.
  exit                     - Tắt bot.
"""

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

def format_time():
    return datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S:%f")[:-3]

def safe_filename(s):
    return "".join(c for c in s if c.isalnum() or c in (' ', '.', '_', '-')).rstrip()

def get_date_folder():
    return datetime.datetime.now().strftime("%d-%m-%Y")

def get_user_log_path(message):
    user = message.author
    if message.guild:
        folder = f"loguser/{get_date_folder()}/{safe_filename(message.guild.name)}_{message.guild.id}"
    else:
        folder = f"loguser/{get_date_folder()}/DM"
    ensure_dir(folder)
    return os.path.join(folder, f"{safe_filename(user.name)}_{user.id}.txt")

def get_user_img_path(message):
    user = message.author
    if message.guild:
        folder = f"loguser/{get_date_folder()}/{safe_filename(message.guild.name)}_{message.guild.id}/img_{safe_filename(user.name)}_{user.id}"
    else:
        folder = f"loguser/{get_date_folder()}/DM/img_{safe_filename(user.name)}_{user.id}"
    ensure_dir(folder)
    return folder

def get_user_voice_path(message):
    user = message.author
    if message.guild:
        folder = f"loguser/{get_date_folder()}/{safe_filename(message.guild.name)}_{message.guild.id}/voice_{safe_filename(user.name)}_{user.id}"
    else:
        folder = f"loguser/{get_date_folder()}/DM/voice_{safe_filename(user.name)}_{user.id}"
    ensure_dir(folder)
    return folder

def get_server_log_path(guild, channel):
    folder = f"logserver/{get_date_folder()}/{safe_filename(guild.name)}_{guild.id}"
    ensure_dir(folder)
    return os.path.join(folder, f"{safe_filename(channel.name)}.txt")

def get_server_img_path(guild, channel):
    folder = f"logserver/{get_date_folder()}/{safe_filename(guild.name)}_{guild.id}/img_{safe_filename(channel.name)}"
    ensure_dir(folder)
    return folder

async def save_attachments(message, folder):
    for attachment in message.attachments:
        ext = os.path.splitext(attachment.filename)[1]
        filename = f"{format_time().replace(':', '-')}_{message.id}{ext}"
        path = os.path.join(folder, filename)
        async with aiohttp.ClientSession() as session:
            async with session.get(attachment.url) as resp:
                if resp.status == 200:
                    with open(path, 'wb') as f:
                        f.write(await resp.read())
                        
        # Lưu voice nếu là voice message
        if ext == ".mp3" or "voice-message" in attachment.filename:
            voice_path = get_user_voice_path(message)
            await save_attachments(message, voice_path)

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    log_text = f"[{format_time()}] <{message.author.name}#{message.author.id}>: "
    if message.stickers:
        log_text += f"Đã gửi sticker: {', '.join(s.name for s in message.stickers)}"
    elif message.attachments:
        log_text += "Đã gửi hình ảnh"
    else:
        log_text += message.content

    # Log người dùng
    if message.author.id in log_user_ids:
        file_path = get_user_log_path(message)
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(log_text + "\n")
            if message.attachments or message.stickers:
                f.write("-" * 30 + "\n")
        if message.attachments:
            await save_attachments(message, get_user_img_path(message))

    # Log server
    if message.guild and message.guild.id in log_server_ids:
        file_path = get_server_log_path(message.guild, message.channel)
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(log_text + "\n")
            if message.attachments or message.stickers:
                f.write("-" * 30 + "\n")
        if message.attachments:
            await save_attachments(message, get_server_img_path(message.guild, message.channel))

    await bot.process_commands(message)

def terminal_interface():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    selected_channel = None
    guild_map = {}

    def show_servers():
        guild_map.clear()
        print("\n📋 Danh sách server:")
        for i, guild in enumerate(bot.guilds, start=1):
            print(f"📌 [{i}] Server: {guild.name} (ID: {guild.id})")
            guild_map[str(i)] = guild
            guild_map[str(guild.id)] = guild

    def select_channel():
        show_servers()
        while True:
            server_input = input("\n🔧 Chọn server bằng số hoặc ID: ").strip()
            guild = guild_map.get(server_input)
            if guild:
                print(f"\n📌 Đã chọn server: {guild.name}")
                text_channels = list(guild.text_channels)
                channel_map = {}
                for idx, ch in enumerate(text_channels, start=1):
                    print(f"  [{idx}] #{ch.name} (ID: {ch.id})")
                    channel_map[str(idx)] = ch
                    channel_map[str(ch.id)] = ch
                while True:
                    channel_input = input("\n📺 Chọn kênh bằng số hoặc ID: ").strip()
                    selected = channel_map.get(channel_input)
                    if selected:
                        return selected
                    else:
                        print("❌ Không tìm thấy kênh. Nhập lại.")
            else:
                print("❌ Không tìm thấy server. Nhập lại.")

    print(DanhSachLenh)
    selected_channel = select_channel()

    while True:
        cmd = input("\nNhập lệnh: ").strip()

        if cmd.startswith("help"):
            print(DanhSachLenh)

        elif cmd.startswith("say "):
            msg = cmd[4:]

            async def send_message():
                content = msg
                words = msg.split()
                mentions = []
                message_words = []

                for word in words:
                    if word.startswith("@"):
                        name_or_id = word[1:]
                        if name_or_id.lower() == "everyone":
                            mentions.append("@everyone")
                            continue
                        if name_or_id.isdigit():
                            try:
                                user = await bot.fetch_user(int(name_or_id))
                                mentions.append(user.mention)
                                continue
                            except:
                                pass
                        for member in selected_channel.guild.members:
                            if member.name == name_or_id or member.display_name == name_or_id:
                                mentions.append(member.mention)
                                break
                        else:
                            message_words.append(word)
                    else:
                        message_words.append(word)

                mention_line = " ".join(mentions)
                message_line = " ".join(message_words)
                final_message = ""
                if mention_line:
                    final_message += mention_line + "\n"
                final_message += f"\n```{message_line}```\n"

                await selected_channel.send(final_message)

            future = asyncio.run_coroutine_threadsafe(send_message(), bot.loop)
            future.result()
            print("✅ Đã gửi tin nhắn.")

        elif cmd.startswith("clear "):
            try:
                amount = int(cmd[6:])
                if 1 <= amount <= 100:
                    async def do_clear():
                        await selected_channel.purge(limit=amount)
                        await selected_channel.send(f"\n```✅ Đã xoá {amount} tin nhắn.```\n", delete_after=5)
                    future = asyncio.run_coroutine_threadsafe(do_clear(), bot.loop)
                    future.result()
                    print(f"✅ Đã xoá {amount} tin nhắn.")
                else:
                    print("❌ Số lượng phải từ 1 đến 100.")
            except:
                print("❌ Sai cú pháp.")

        elif cmd == "clear_all":
            print("🧹 Đang xoá toàn bộ tin nhắn...")
            async def notify():
                await selected_channel.send("\n```🧹 Đang xoá toàn bộ tin nhắn...```\n")
            asyncio.run_coroutine_threadsafe(notify(), bot.loop)
            async def clear_all():
                deleted = 0
                while True:
                    messages = [msg async for msg in selected_channel.history(limit=100)]
                    if not messages:
                        break
                    await selected_channel.purge(limit=100)
                    deleted += len(messages)
                    await asyncio.sleep(.2)
                print(f"\n✅ Đã xoá tổng cộng {deleted} tin nhắn.\n")
                await selected_channel.send(f"\n```✅ Đã xoá tổng cộng {deleted} tin nhắn.```\n", delete_after=3)
            future = asyncio.run_coroutine_threadsafe(clear_all(), bot.loop)
            future.result()

        elif cmd.startswith("dm "):
            try:
                parts = cmd.split(" ", 2)
                user_id = int(parts[1])
                content = parts[2]
                async def send_dm():
                    user = await bot.fetch_user(user_id)
                    await user.send(f"```{content}```")
                    print(f"✅ Đã gửi tin nhắn đến {user.name}#{user.id}")
                future = asyncio.run_coroutine_threadsafe(send_dm(), bot.loop)
                future.result()
            except Exception as e:
                print(f"❌ Gửi DM thất bại: {e}")

        elif cmd.startswith("loguser "):
            try:
                user_id = int(cmd.split()[1])
                log_user_ids.add(user_id)
                print(f"✅ Bắt đầu log người dùng có ID: {user_id}")
            except:
                print("❌ Cú pháp sai.")

        elif cmd.startswith("unloguser "):
            try:
                user_id = int(cmd.split()[1])
                log_user_ids.discard(user_id)
                print(f"✅ Đã dừng log người dùng có ID: {user_id}")
            except:
                print("❌ Cú pháp sai.")

        elif cmd == "listloguser":
            if log_user_ids:
                print("👤 Đang log các user:")
                for uid in log_user_ids:
                    print(f" - {uid}")
            else:
                print("⚠️ Không có user nào đang được log.")

        elif cmd.startswith("logserver "):
            try:
                sid = int(cmd.split()[1])
                log_server_ids.add(sid)
                print(f"✅ Bắt đầu log server ID: {sid}")
            except:
                print("❌ Cú pháp sai.")

        elif cmd.startswith("unlogserver "):
            try:
                sid = int(cmd.split()[1])
                log_server_ids.discard(sid)
                print(f"✅ Đã dừng log server ID: {sid}")
            except:
                print("❌ Cú pháp sai.")

        elif cmd == "listlogserver":
            if log_server_ids:
                print("🖥️ Đang log các server:")
                for sid in log_server_ids:
                    print(f" - {sid}")
            else:
                print("⚠️ Không có server nào đang được log.")

        elif cmd == "channel":
            selected_channel = select_channel()

        elif cmd == "servers":
            show_servers()

        elif cmd == "exit":
            print("👋 Đang tắt bot...")
            asyncio.run_coroutine_threadsafe(bot.close(), bot.loop)
            break

        else:
            print("❌ Lệnh không hợp lệ.")

@bot.event
async def on_ready():
    print(f"\n✅ Bot đã đăng nhập với tài khoản: {bot.user} ({bot.user.id})")
    threading.Thread(target=terminal_interface, daemon=True).start()

bot.run(TOKEN)
