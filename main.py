#### Libraries ####
import discord, asyncio, json, datetime, os, threading, re, random, aiohttp, json, time, stat
from discord.ext import commands, tasks
from dotenv import load_dotenv

os.system('cls')  # on windows

#### Bot requirement ####
load_dotenv()
TOKEN = os.getenv('DISCORD_BOT_TOKEN')
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="/", intents=intents)

#### Current logging ####
log_server_ids = set()
log_user_ids = set()
responsesJsonPath = "json/responses.json"

#### Available commands ####
CommandsForTerminal = """📖 Danh sách lệnh:
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

#### Basic function ####  
def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)
        
def safe_filename(s):
    return "".join(c for c in s if c.isalnum() or c in (' ', '.', '_', '-')).rstrip()

def get_muted_file_path(guild: discord.Guild):
    folder = f"json/{safe_filename(guild.name)}_{guild.id}/muted_user"
    ensure_dir(folder)
    return os.path.join(folder, "muted_user.json")

def save_muted_data(guild: discord.Guild, muted_users_info: dict):
    path = get_muted_file_path(guild)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(muted_users_info, f, ensure_ascii=False, indent=4)
        
def ensure_warn_path(guild):
    path = f"json/{guild.name}_{guild.id}/warn_user"
    os.makedirs(path, exist_ok=True)
    return os.path.join(path, "warn_user.json")

def load_warn_data(guild):
    path = ensure_warn_path(guild)
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=4)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_warn_data(guild, data):
    path = ensure_warn_path(guild)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
        
def load_muted_data(guild: discord.Guild) -> dict:
    path = get_muted_file_path(guild)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                return {int(k): v for k, v in data.items()}
            except json.JSONDecodeError:
                return {}
    return {}

def full_format_time():
    return datetime.datetime.now().strftime("%H:%M:%S %d-%m-%Y")

def dmY_format_time():
    return datetime.datetime.now().strftime("%d-%m-%Y")

def get_user_log_path(message):
    user = message.author
    if message.guild:
        folder = f"loguser/{dmY_format_time()}/{safe_filename(message.guild.name)}_{message.guild.id}/"
    else:
        folder = f"loguser/{dmY_format_time()}/DM/message/"
    ensure_dir(folder)
    return os.path.join(folder, f"{safe_filename(user.name)}_{user.id}.txt")

def get_user_attachments_path(message):
    user = message.author
    if message.guild:
        folder = f"loguser/{dmY_format_time()}/{safe_filename(message.guild.name)}_{message.guild.id}/attachments_{safe_filename(user.name)}_{user.id}"
    else:
        folder = f"loguser/{dmY_format_time()}/DM/attachments_{safe_filename(user.name)}_{user.id}"
    ensure_dir(folder)
    return folder

def get_server_log_path(guild, channel):
    folder = f"logserver/{dmY_format_time()}/{safe_filename(guild.name)}_{guild.id}"
    ensure_dir(folder)
    return os.path.join(folder, f"{safe_filename(channel.name)}.txt")

def get_server_attachments_path(guild, channel):
    folder = f"logserver/{dmY_format_time()}/{safe_filename(guild.name)}_{guild.id}/attachments_{safe_filename(channel.name)}"
    ensure_dir(folder)
    return folder

async def save_attachments(message, folder):
    for attachment in message.attachments:
        ext = os.path.splitext(attachment.filename)[1]
        filename = f"{full_format_time().replace(':', '-')}_{message.id}{ext}"
        path = os.path.join(folder, filename)

        async with aiohttp.ClientSession() as session:
            async with session.get(attachment.url) as resp:
                if resp.status == 200:
                    with open(path, 'wb') as f:
                        f.write(await resp.read())

        # Lưu voice nếu là voice message, nhưng không gọi đệ quy
        if ext == ".mp3" or "voice-message" in attachment.filename:
            if message.guild:
                voice_path = get_server_attachments_path(message.guild, message.channel)
            else:
                voice_path = get_user_attachments_path(message)
            voice_filename = f"{full_format_time().replace(':', '-')}_{message.id}{ext}"
            voice_full_path = os.path.join(voice_path, voice_filename)

#### Processor for morderator ####
def parse_time(duration_str: str):
    if not duration_str or duration_str.lower() == "vĩnh viễn":
        return None  # Vĩnh viễn
    pattern = r"^(\d+)([smhd])$"
    match = re.match(pattern, duration_str.lower())
    if not match:
        return "invalid"
    number, unit = match.groups()
    number = int(number)
    if unit == 's':
        return number
    elif unit == 'm':
        return number * 60
    elif unit == 'h':
        return number * 3600
    elif unit == 'd':
        return number * 86400
    else:
        return "invalid"

#### Important Funtions ####
# Hàm autocomplete role cho member
async def role_autocomplete(interaction: discord.Interaction, current: str):
    roles = [role for role in interaction.guild.roles if current.lower() in role.name.lower()]
    return [
        discord.app_commands.Choice(name=role.name, value=str(role.id))
        for role in roles[:25]
    ]

# Duma đọc tên là biết
async def mute_for_warn(interaction, member, reason, duration):
    guild = interaction.guild
    muted_role = discord.utils.get(guild.roles, name="muted") or discord.utils.get(guild.roles, name="Muted")

    await member.add_roles(muted_role, reason=reason)

    try:
        end_dt = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
        end_time_str = end_dt.strftime("%H:%M:%S - %d/%m/%Y")
    except Exception:
        end_time_str = "❓Không rõ"

    # Cập nhật dữ liệu
    muted_users_info = load_muted_data(interaction.guild)
    muted_users_info[member.id] = {
        "reason": reason or "Không có lý do",
        "duration": duration,
        "time": full_format_time(),
        "end_time": end_time_str,
        "username": str(member),
        "display_name": member.display_name,
        "muted_by": f"{interaction.user}#{interaction.user.id}"
    }
    save_muted_data(interaction.guild, muted_users_info)
        
#### Add command for user ####
# AFK
afk_users = {}
@bot.tree.command(name="afk", description="Đặt trạng thái AFK")
@discord.app_commands.describe(
    reason="Lý do AFK"
)
async def afk(interaction: discord.Interaction, reason: str = "Không rõ"):
    # Kiểm tra lệnh có được triển khai trong máy chủ hay không
    if interaction.guild is None:
        await interaction.response.send_message(
            embed = discord.Embed(
                title="🚫 Chú ý",
                description="❌ Vui lòng dùng lệnh này trong máy chủ!",
                color=discord.Color.red()))
        return
    
    afk_users[interaction.user.id] = {
        "reason": reason,
        "time": full_format_time()
    }
    await interaction.response.send_message(
        embed = discord.Embed(
            title="✅ Thành công",
            description=f"✅ {interaction.user.mention} đã được đặt trạng thái AFK.\n✏️ Lý do: **{reason}**",
            color=discord.Color.green()))

# ADD ROLE
@bot.tree.command(name="addrole", description="Thêm một role cho người dùng")
@discord.app_commands.describe(
    member="Người cần được thêm role",
    role="Role cần thêm"
)
@commands.has_permissions(manage_roles=True)
async def addrole(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    # Kiểm tra lệnh có được triển khai trong máy chủ hay không
    if interaction.guild is None:
        await interaction.response.send_message(
            embed = discord.Embed(
                title="🚫 Chú ý",
                description="❌ Vui lòng dùng lệnh này trong máy chủ!",
                color=discord.Color.red()))
        return
    
    # Kiểm tra nếu bot không đủ quyền
    if role > interaction.guild.me.top_role:
        await interaction.response.send_message(
            embed = discord.Embed(
                title="🚫 Lỗi quyền",
                description="Bot không có quyền thêm role này.",
                color=discord.Color.red()
            ), ephemeral=True)
        return

    # Kiểm tra nếu người dùng đã có role
    if role in member.roles:
        await interaction.response.send_message(
            embed = discord.Embed(
                title="⚠️ Cảnh báo",
                description=f"{member.mention} đã có role `{role.name}` từ trước.",
                color=discord.Color.yellow()
            ), ephemeral=True)
        return

    try:
        await member.add_roles(role)
        await interaction.response.send_message(
            embed = discord.Embed(
                title="✅ Thành công",
                description=f"Đã thêm role `{role.name}` cho {member.mention}.\n\nNgười thực hiện:  {interaction.user.mention}",
                color=discord.Color.green()))
    except discord.Forbidden:
        await interaction.response.send_message(
            embed = discord.Embed(
                title="❌ Lỗi quyền",
                description="Bot không đủ quyền để thêm role.",
                color=discord.Color.red()
            ), ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(
            embed = discord.Embed(
                title="⚠️ Lỗi xảy ra",
                description=f"{e}",
                color=discord.Color.orange()
            ), ephemeral=True)
       
# REMOVE ROLE
@bot.tree.command(name="removerole", description="Gỡ một role khỏi một người dùng")
@discord.app_commands.describe(
    member="Người bị gỡ role",
    role="Role cần gỡ"
)
@commands.has_permissions(manage_roles=True)
async def removerole(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    if interaction.guild is None:
        return await interaction.response.send_message(
            embed=discord.Embed(
                title="🚫 Chú ý",
                description="❌ Vui lòng dùng lệnh này trong máy chủ!",
                color=discord.Color.red()
            ), ephemeral=True)

    if role not in member.roles:
        return await interaction.response.send_message(
            embed=discord.Embed(
                title="⚠️ Cảnh báo",
                description=f"{member.mention} không có role `{role.name}`.",
                color=discord.Color.yellow()
            ), ephemeral=True)

    if role >= interaction.guild.me.top_role:
        return await interaction.response.send_message(
            embed=discord.Embed(
                title="🚫 Lỗi quyền",
                description="Bot không có quyền gỡ role này.\nMã: M001",
                color=discord.Color.red()
            ), ephemeral=True)

    try:
        await member.remove_roles(role)
        await interaction.response.send_message(
            embed=discord.Embed(
                title="😭 Đã gỡ role",
                description=f"Đã gỡ role `{role.name}` khỏi {member.mention}.\n\nNgười thực hiện: {interaction.user.mention}",
                color=discord.Color.orange()
            ))
    except discord.Forbidden:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="❌ Lỗi quyền",
                description="Bot không đủ quyền để gỡ role.\nMã: M001",
                color=discord.Color.red()
            ), ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="⚠️ Lỗi xảy ra",
                description=str(e),
                color=discord.Color.orange()
            ), ephemeral=True)
        
# MUTE
muted_users_info = {}
@bot.tree.command(name="mute", description="Cấm người dùng gửi tin nhắn")
@discord.app_commands.describe(
    member="Người cần mute",
    reason="Lý do",
    duration="Thời gian (10s, 5m, 1h, 2d) hoặc bỏ trống để mute vĩnh viễn"
)
@commands.has_permissions(manage_roles=True)
async def mute(interaction: discord.Interaction, member: discord.Member, reason: str = "Không có", duration: str = "vĩnh viễn"):
    if interaction.guild is None:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="🚫 Chú ý",
                description="❌ Vui lòng dùng lệnh này trong máy chủ!",
                color=discord.Color.red()
            ))
        return

    muted_role = discord.utils.get(interaction.guild.roles, name="muted") or discord.utils.get(interaction.guild.roles, name="Muted")
    if not muted_role:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="🚫 Lỗi",
                description="Không tìm thấy role 'muted'. Vui lòng tạo role này trước.",
                color=discord.Color.red()
            ), ephemeral=True)
        return

    if interaction.user.top_role < member.top_role:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="🚫 Lỗi quyền",
                description="Bạn không thể mute người có role cao hơn hoặc bằng bạn.",
                color=discord.Color.red()
            ), ephemeral=True)
        return

    bot_member = interaction.guild.me
    if bot_member.top_role < member.top_role or bot_member.top_role < muted_role:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="🚫 Lỗi quyền",
                description="Bot không có đủ quyền để mute người dùng này.",
                color=discord.Color.red()
            ), ephemeral=True)
        return

    if muted_role in member.roles:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="⚠️ Cảnh báo",
                description=f"{member.mention} đã bị mute rồi.",
                color=discord.Color.orange()
            ), ephemeral=True)
        return

    seconds = parse_time(duration)
    if seconds == "invalid":
        await interaction.response.send_message(
            embed=discord.Embed(
                title="🚫 Lỗi định dạng thời gian",
                description="Định dạng thời gian không hợp lệ. Vui lòng nhập: 10s, 5m, 1h, 2d hoặc bỏ trống để mute vĩnh viễn.",
                color=discord.Color.red()
            ), ephemeral=True)
        return

    await member.add_roles(muted_role, reason=reason)

    # Tính thời gian kết thúc, nếu seconds có giá trị
    if seconds is None:
        end_time_str = "🔒 Vĩnh viễn"
    else:
        try:
            end_dt = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
            end_time_str = end_dt.strftime("%H:%M:%S - %d/%m/%Y")
        except Exception:
            end_time_str = "❓Không rõ"

    # Load và cập nhật dữ liệu mute
    muted_users_info = load_muted_data(interaction.guild)
    muted_users_info[member.id] = {
        "reason": reason or "Không có lý do",
        "duration": duration,
        "time": full_format_time(),
        "end_time": end_time_str,
        "username": str(member),
        "display_name": member.display_name,
        "muted_by": f"{interaction.user}#{interaction.user.id}"
    }
    save_muted_data(interaction.guild, muted_users_info)

    if seconds is None:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="🔇 Đã mute vĩnh viễn",
                description=f"{member.mention} đã bị mute vĩnh viễn.\n✏️ Lý do: `{reason}`\n\nNgười thực hiện: {interaction.user.mention}",
                color=discord.Color.orange()
            ))
    else:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="🔇 Đã mute thành công",
                description=f"{member.mention} đã bị mute trong `{duration}`.\n✏️ Lý do: `{reason}`\n\nNgười thực hiện: {interaction.user.mention}",
                color=discord.Color.orange()
            ))
            
# UNMUTE
@bot.tree.command(name="unmute", description="Cho phép người dùng gửi tin nhắn")
@discord.app_commands.describe(
    member="Người bị mute",
    reason="Lý do"
)
@commands.has_permissions(manage_roles=True)
async def unmute(interaction: discord.Interaction, member: discord.Member, reason: str = "Không có lý do"):
    if interaction.guild is None:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="🚫 Chú ý",
                description="❌ Vui lòng dùng lệnh này trong máy chủ!",
                color=discord.Color.red()
            ))
        return

    muted_role = discord.utils.get(interaction.guild.roles, name="muted") or discord.utils.get(interaction.guild.roles, name="Muted")
    if not muted_role:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="🚫 Lỗi",
                description="Không tìm thấy role 'muted'. Vui lòng tạo role này trước.",
                color=discord.Color.red()
            ), ephemeral=True)
        return

    if interaction.user.top_role < member.top_role:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="⚠️ Cảnh báo",
                description="Bạn không thể unmute người có role cao hơn hoặc bằng bạn.",
                color=discord.Color.orange()
            ), ephemeral=True)
        return

    bot_member = interaction.guild.me
    if bot_member.top_role < member.top_role or bot_member.top_role < muted_role:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="⚠️ Cảnh báo",
                description="Bot không có đủ quyền để unmute người dùng này.",
                color=discord.Color.yellow()
            ), ephemeral=True)
        return

    if muted_role not in member.roles:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="⚠️ Cảnh báo",
                description=f"{member.mention} không bị mute.",
                color=discord.Color.yellow()
            ), ephemeral=True)
        return

    try:
        await member.remove_roles(muted_role, reason=reason)
        muted_users_info = load_muted_data(interaction.guild)
        muted_users_info.pop(member.id, None)
        save_muted_data(interaction.guild, muted_users_info)
        await interaction.response.send_message(
            embed=discord.Embed(
                title="🔊 Đã unmute",
                description=f"{member.mention} đã được unmute.\n✏️ Lý do: `{reason}`\n\nNgười thực hiện: {interaction.user.mention}",
                color=discord.Color.green()
            ))
    except discord.Forbidden:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="🚫 Lỗi",
                description="Bot không đủ quyền để unmute người này.",
                color=discord.Color.red()
            ), ephemeral=True)
        
# LISTMUTE
@bot.tree.command(name="listmute", description="Hiển thị danh sách các thành viên đang bị mute")
@commands.has_permissions(manage_roles=True)
async def listmute(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="🚫 Chú ý",
                description="❌ Vui lòng dùng lệnh này trong máy chủ!",
                color=discord.Color.red()
            ))
        return

    muted_users_info = load_muted_data(interaction.guild)
    muted_role = discord.utils.get(interaction.guild.roles, name="muted") or discord.utils.get(interaction.guild.roles, name="Muted")

    if not muted_role:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="⚠️ Lỗi",
                description="Role 'muted' không tồn tại trong máy chủ.",
                color=discord.Color.red()
            ), ephemeral=True)
        return

    muted_members = [member for member in interaction.guild.members if muted_role in member.roles]

    if not muted_members:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="✅ Không có ai bị mute",
                description="Hiện tại không có thành viên nào đang bị mute.",
                color=discord.Color.green()
            ))
        return

    embed = discord.Embed(
        title="🔇 Danh sách thành viên đang bị mute",
        description=f"**Tổng cộng: {len(load_muted_data(interaction.guild))} người bị mute**",
        color=discord.Color.blue()
    )

    for member in muted_members:
        info = muted_users_info.get(member.id, {})
        reason = info.get("reason", "Không có lý do")
        start_time = info.get("time", "Không rõ")
        duration = info.get("duration", "Không rõ")
        end_time = info.get("end_time", "Không rõ")
        muted_by = info.get("muted_by", "")
        mention = f"<@{muted_by.split('#')[-1]}>" if "#" in muted_by else "không rõ (mute thủ công)"


        embed.add_field(
            name=f"Tên: {member}\nID: {member.id}",
            value=(
                f"✏️ Lý do: `{reason}`\n"
                f"⏳ Thời gian mute: `{duration}`\n"
                f"⏱ Thời diểm mute: `{start_time}`\n"
                f"🕒 Kết thúc mute: `{end_time}`\n"
                f"👮‍♂️ Người mute: {mention}"
            ),inline=False)
        embed.add_field(name="", value="", inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)
    
# SAY
@bot.tree.command(name="say", description="Nhờ bot nói hộ bạn gì đó")
@discord.app_commands.describe(
    message="Điều mà bạn muốn nói"
)
@commands.has_permissions(manage_messages=True)
async def say(interaction: discord.Interaction, message: str):
    # Kiểm tra lệnh có được triển khai trong máy chủ hay không
    if interaction.guild is None:
        await interaction.response.send_message(
            embed = discord.Embed(
                title="🚫 Chú ý",
                description="❌ Vui lòng dùng lệnh này trong máy chủ!.",
                color=discord.Color.red()))
        return

    await interaction.response.send_message("✅ Đã gửi!", ephemeral=True)
    await interaction.channel.send(f"```{message}```")
    
# WARN
@bot.tree.command(name="warn", description="Cảnh cáo thành viên")
@discord.app_commands.describe(member="Người cần cảnh cáo", reason="Lý do cảnh cáo")
@commands.has_permissions(manage_messages=True)
@commands.has_permissions(manage_roles=True)
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str = "Không có lý do"):
    # Kiểm tra vai trò
    if interaction.user.top_role <= member.top_role:
        await interaction.response.send_message(
            embed = discord.Embed(
                title="🚫 Chú ý",
                description="Bạn không thể cảnh cáo người có vai trò cao hơn hoặc bằng bạn.",
                color=discord.Color.yellow()
            ), ephemeral=True)
        return

    if member.bot:
        await interaction.response.send_message(
            embed = discord.Embed(
                title="🚫 Chú ý",
                description="Không thể cảnh cáo bot.",
                color=discord.Color.yellow()
            ), ephemeral=True)
        return

    guild = interaction.guild
    now = datetime.datetime.now()
    now_str = now.strftime("%H:%M:%S - %d/%m/%Y")

    data = load_warn_data(guild)
    user_id = str(member.id)
    user_warns = data.get(user_id, {"warns": [], "total": 0})

    # Xóa cảnh cáo quá 7 ngày
    user_warns["warns"] = [
        w for w in user_warns["warns"]
        if now - datetime.datetime.strptime(w["time"], "%H:%M:%S - %d/%m/%Y") < datetime.timedelta(days=7)
    ]

    # Thêm cảnh cáo mới
    user_warns["warns"].append({
        "reason": reason,
        "time": now_str,
        "by": str(interaction.user)
    })

    user_warns["total"] += 1
    data[user_id] = user_warns
    save_warn_data(guild, data)

    warn_count = len(user_warns["warns"])

    # Embed thông báo
    if warn_count is None or warn_count <= 3:
        await interaction.response.send_message(
            embed = discord.Embed(
                title="⚠️ Đã cảnh cáo. Mức 1",
                description=(
                    f"👤 {member.mention} đã bị cảnh cáo.\n"
                    f"✏️ Lý do: `{reason}`\n"
                    f"🕒 Thời gian: `{now_str}`\n"
                    f"📊 Số cảnh cáo trong 7 ngày qua: `{warn_count}/3`\n"
                    f"🕒 Tổng cảnh cáo từ trước đến nay: `{user_warns['total']}`"
                ), color=discord.Color.orange()))
    elif warn_count > 3 and warn_count <= 6:
        await interaction.response.send_message(
            embed = discord.Embed(
                title="⚠️ Đã cảnh cáo. Mức 2",
                description=(
                    f"👤 {member.mention} đã bị cảnh cáo.\n"
                    f"✏️ Lý do: `{reason}`\n"
                    f"🕒 Thời gian: `{now_str}`\n"
                    f"📊 Số cảnh cáo trong 7 ngày qua: `{warn_count}/6`\n"
                    f"🕒 Tổng cảnh cáo từ trước đến nay: `{user_warns['total']}`"
                ), color=discord.Color.orange()))
    else:
        await interaction.response.send_message(
            embed = discord.Embed(
                title="⚠️ Đã cảnh cáo. Mức 3",
                description=(
                    f"👤 {member.mention} đã bị cảnh cáo.\n"
                    f"✏️ Lý do: `{reason}`\n"
                    f"🕒 Thời gian: `{now_str}`\n"
                    f"📊 Số cảnh cáo trong 7 ngày qua: `{warn_count}/GÌ VẬY CU`\n"
                    f"🕒 Tổng cảnh cáo từ trước đến nay: `{user_warns['total']}`"
                ), color=discord.Color.orange()))

    # DM cho người bị cảnh cáo
    try:
        await member.send(
            embed=discord.Embed(
                title=f"⚠️ Bạn đã bị cảnh cáo tại server {guild.name}",
                description=(
                    f"✏️ Lý do: `{reason}`\n🕒 Thời gian: `{now_str}`"
                    "\nChú ý:\n1.Nếu bạn bị warn 3 lần, bạn sẽ bị mute 1 ngày\n2. Nếu bạn bị warn 6 lần, bạn sẽ bị mute 3 ngày\n3. Nếu bạn bị warn hơn 6 lần, bạn sẽ bị mute 7 ngày"),
                color=discord.Color.yellow()
            ))
    except discord.Forbidden:
        pass  # Người dùng tắt DM

    # Kiểm tra hình phạt nâng cao
    muted_role = discord.utils.get(interaction.guild.roles, name="muted") or discord.utils.get(interaction.guild.roles, name="Muted")
    if muted_role and muted_role not in member.roles:
        if warn_count == 3:
            await mute_for_warn(interaction, member, "Bị cảnh cáo 3 lần trong 1 tuần", "1d")
            try:
                await member.send(
                    embed=discord.Embed(
                        title="❌❌❌ Bạn đã bị mute ❌❌❌",
                        description=f"🚫 Bạn đã bị mute 1 ngày ở server **{guild.name}** vì bị cảnh cáo quá nhiều lần trong 1 tuần.",
                        color=discord.Color.yellow()))
                await interaction.followup.send(
                    embed = discord.Embed(
                        title="🔇 Đã mute thành công",
                        description=f"{member.mention} đã bị mute trong 1 ngày.\n✏️ Lý do: `Bị cảnh cáo 3 lần trong 1 tuần`\n\nNgười thực hiện: {interaction.user.mention}",
                        color=discord.Color.orange()))
            except discord.Forbidden:
                pass
        elif warn_count == 6:
            await mute_for_warn(interaction, member, "Bị cảnh cáo 6 lần trong 1 tuần", "3d")
            try:
                await member.send(
                    embed=discord.Embed(
                        title="❌❌❌ Bạn đã bị mute ❌❌❌",
                        description=f"🚫 Bạn đã bị mute 3 ngày ở server **{guild.name}** vì bị cảnh cáo quá nhiều lần trong 1 tuần.",
                        color=discord.Color.red()))
                await interaction.followup.send(
                    embed = discord.Embed(
                        title="🔇 Đã mute thành công",
                        description=f"{member.mention} đã bị mute trong 3 ngày.\n✏️ Lý do: `Bị cảnh cáo 6 lần trong 1 tuần`\n\nNgười thực hiện: {interaction.user.mention}",
                        color=discord.Color.orange()))
            except discord.Forbidden:
                pass
        elif warn_count > 6:
            await mute_for_warn(interaction, member, "Bị cảnh cáo hơn 6 lần trong 1 tuần", "7d")
            try:
                await member.send(
                    embed=discord.Embed(
                        title="❌❌❌ Bạn đã bị mute ❌❌❌",
                        description=f"🚫 Bạn đã bị mute 7 ngày ở server **{guild.name}** vì bị cảnh cáo quá nhiều lần trong 1 tuần.",
                        color=discord.Color.red()))
                await interaction.followup.send(
                    embed = discord.Embed(
                        title="🔇 Đã mute thành công",
                        description=f"{member.mention} đã bị mute trong 7 ngày.\n✏️ Lý do: `Bị cảnh cáo hơn 6 lần trong 1 tuần`\n\nNgười thực hiện: {interaction.user.mention}",
                        color=discord.Color.orange()))
            except discord.Forbidden:
                pass

#### LOGIC ####
@bot.event
async def on_message(message):

    log_text = f"[{full_format_time()}] <{message.author.name}#{message.author.id}>: "
    if message.stickers:
        log_text += f"Đã gửi sticker: {', '.join(s.name for s in message.stickers)}"
    elif message.attachments:
        log_text += "Đã gửi tệp đính kèm"
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
            await save_attachments(message, get_user_attachments_path(message))

    # Log server
    if message.guild and message.guild.id in log_server_ids:
        file_path = get_server_log_path(message.guild, message.channel)
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(log_text + "\n")
            if message.attachments or message.stickers:
                f.write("-" * 30 + "\n")
        if message.attachments:
            await save_attachments(message, get_server_attachments_path(message.guild, message.channel))

    #### Ngăn bot tự trả lời ####
    if message.author.bot:
        return

    #### Gửi tin nhắn thì xóa AFK ####
    if message.author.id in afk_users:
        del afk_users[message.author.id]
        await message.channel.send(f"💀 VCL {message.author.mention} kìa, trạng thái AFK của bạn đã được gỡ.")

    #### Nếu tag người đang AFK ####
    for user in message.mentions:
        if user.id in afk_users:
            reason = afk_users[user.id]["reason"]
            await message.channel.send(f"⚠️ {user.name} hiện đang AFK: **{reason}**")
    
    await bot.process_commands(message)  # Nếu bạn dùng both commands và slash
    
    #### Trả lời người dùng khi được tag ####
    if bot.user in message.mentions:
        with open(responsesJsonPath, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        message_lower = message.content.lower() 
        
        def match_keywords(section):
            for keyword in section.get("keywords", []):
                if keyword in message_lower:
                    return True
            return False

        def generate_response(section):
            contents = section["content"]
            if section.get("ResponseAllContent", "False") == "True":
                return "\n".join([f"{line}" for line in contents])
            else:
                return f"{random.choice(contents)}"

        responded = False
        for section_key in data:
            section = data[section_key]
            if isinstance(section, dict) and "keywords" in section:
                if match_keywords(section):
                    response = generate_response(section)
                    await message.reply(f"{message.author.mention}\n```{response}```")
                    responded = True
                    break
            elif isinstance(section, dict):
                # xử lý nested custom_info như "Dad", "Mom"
                for sub_key, sub_section in section.items():
                    if isinstance(sub_section, dict) and "keywords" in sub_section:
                        if match_keywords(sub_section):
                            response = generate_response(sub_section)
                            await message.reply(f"{message.author.mention}\n```{response}```")
                            responded = True
                            break
            if responded:
                break

        if not responded:
            # Nếu chỉ tag bot mà không có keyword khớp
            tag_resp = data.get("custom_info", {}).get("TagResponses", {})
            if tag_resp:
                contents = tag_resp.get("content", [])
                if tag_resp.get("ResponseAllContent", "False") == "True":
                    response = "\n".join([f"{line}" for line in contents])
                else:
                    response = f"{random.choice(contents)}"
                await message.reply(f"{message.author.mention} ```{response}```")

# CẬP NHẬT MUTE KHI THÊM ROLE THỦ CÔNG
@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    if before.guild is None:
        return

    muted_role = discord.utils.get(after.guild.roles, name="muted") or discord.utils.get(after.guild.roles, name="Muted")

    if not muted_role:
        return

    had_muted = muted_role in before.roles
    has_muted = muted_role in after.roles

    path = get_muted_file_path(after.guild)
    muted_data = load_muted_data(after.guild)

    # 🟢 Nếu vừa bị gán role muted
    if not had_muted and has_muted:
        if after.id in muted_data:
            return  # đã có, bỏ qua

        muted_data[after.id] = {
            "reason": "Không rõ (thêm thủ công)",
            "duration": "Vĩnh viễn",
            "time": datetime.datetime.now().strftime("%H:%M:%S - %d/%m/%Y"),
            "username": str(after),
            "display_name": after.display_name,
            "muted_by": f"Hệ thống#{after.guild.me.id}"  # hoặc bot/self là người phát hiện
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(muted_data, f, ensure_ascii=False, indent=4)

    # 🔴 Nếu vừa bị gỡ role muted
    elif had_muted and not has_muted:
        if after.id in muted_data:
            del muted_data[after.id]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(muted_data, f, ensure_ascii=False, indent=4)

# UNMUTE TỰ ĐỘNG 
async def check_mute_expiry():
    now = datetime.datetime.now()

    for guild in bot.guilds:
        path = f"json/{guild.name}_{guild.id}/muted_user"
        file_path = os.path.join(path, "muted_user.json")

        if not os.path.isfile(file_path):
            continue  # Bỏ qua nếu file không tồn tại

        # Xóa cờ read-only nếu có
        if os.path.exists(file_path) and not os.access(file_path, os.W_OK):
            os.chmod(file_path, stat.S_IWRITE)

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            print(f"Không thể đọc file hoặc lỗi JSON: {file_path}")
            continue

        changed = False

        for user_id, info in list(data.items()):
            end_time_str = info.get("end_time")

            if not end_time_str or "vĩnh viễn" in end_time_str.lower():
                continue

            try:
                end_time = datetime.datetime.strptime(end_time_str, "%H:%M:%S - %d/%m/%Y")
            except ValueError:
                print(f"Không parse được end_time: {end_time_str}")
                continue

            if now >= end_time:
                member = guild.get_member(int(user_id))
                if not member:
                    data.pop(user_id, None)
                    changed = True
                    continue

                muted_role = discord.utils.get(guild.roles, name="muted") or discord.utils.get(guild.roles, name="Muted")
                if not muted_role or muted_role not in member.roles:
                    data.pop(user_id, None)
                    changed = True
                    continue

                try:
                    await member.remove_roles(muted_role, reason="Tự động unmute khi hết hạn")
                    data.pop(user_id, None)
                    changed = True

                    # Gửi tin nhắn cho người dùng
                    try:
                        await member.send(
                            embed=discord.Embed(
                                title="🔊 Bạn đã được unmute",
                                description=f"⏰ Thời gian mute của bạn tại server **{guild.name}** đã kết thúc.\nBạn có thể trò chuyện lại bình thường!",
                                color=discord.Color.green()
                            )
                        )
                    except discord.Forbidden:
                        print(f"Không thể gửi DM cho {member.display_name}.")

                except discord.Forbidden:
                    print(f"Bot không đủ quyền unmute {member.display_name}.")
                    continue

        # Lưu lại dữ liệu nếu có thay đổi
        if changed:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
            except Exception as e:
                print(f"Lỗi khi ghi file: {file_path} → {e}")
                                
# HÀM GỌI KHỞI CHẠY UNMUTE MỖI KHOẢNG THỜI GIAN ĐÃ ĐỊNH
async def precise_loop():
    while True:
        start_time = time.monotonic()

        await check_mute_expiry()  # Gọi hàm xử lý mute/unmute

        ITSUNMUTETIMEMYGAY = 30
        elapsed = time.monotonic() - start_time
        sleep_time = max(0, ITSUNMUTETIMEMYGAY - elapsed)
        await asyncio.sleep(sleep_time)

# CÀI ĐẶT CẤU HÌNH MUTED
async def auto_setup_role(guild: discord.Guild):
    muted_role = discord.utils.get(guild.roles, name="muted") or discord.utils.get(guild.roles, name="Muted")
    default_role = guild.default_role

    # Tạo role nếu chưa có
    if not muted_role:
        try:
            muted_role = await guild.create_role(name="muted", reason="Tạo role để mute người dùng")
        except discord.Forbidden:
            return

    muted_role_channel_changed = 0
    default_role_channel_changed = 0

    for channel in guild.channels:
        try:
            overwrite = channel.overwrites_for(muted_role)
            overwrite.send_messages = False
            overwrite.send_messages_in_threads = False
            overwrite.create_public_threads = False
            overwrite.create_private_threads = False
            overwrite.embed_links = False
            overwrite.attach_files = False
            overwrite.add_reactions = False
            overwrite.use_external_emojis = False
            overwrite.use_external_stickers = False
            overwrite.send_tts_messages = False
            overwrite.send_voice_messages = False
            overwrite.use_application_commands = False

            await channel.set_permissions(muted_role, overwrite=overwrite)
            muted_role_channel_changed += 1
        except Exception as e:
            print(f"⚠️ Lỗi ở kênh '{channel.name}' ({guild.name}): {e}")

    print(f"🔧 Đã thiết lập quyền cho role 'muted' ở {muted_role_channel_changed} kênh trong server '{guild.name}'.")
    
    for channel in guild.channels:
        try: 
            overwrite = channel.overwrites_for(default_role)
            overwrite.create_instant_invite = False  
            overwrite.send_messages_in_threads = False  
            overwrite.create_public_threads = False 
            overwrite.create_private_threads = False  
            overwrite.mention_everyone = False
                
            await channel.set_permissions(default_role, overwrite=overwrite)
            default_role_channel_changed += 1
        except Exception as e:
            print(f"⚠️ Lỗi ở kênh '{channel.name}' ({guild.name}): {e}")
        
    print(f"🔧 Đã thiết lập quyền cho role mặc định ở {muted_role_channel_changed} kênh trong server '{guild.name}'.\n")


#### TERMINAL ####
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

    print(CommandsForTerminal)
    selected_channel = select_channel()

    while True:
        cmd = input("\nNhập lệnh: ").strip()

        if cmd.startswith("help"):
            print(CommandsForTerminal)

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
                                user = await bot.get_user(int(name_or_id))
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
                final_message += f"```{message_line}```\n"

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
                    user = await bot.get_user(user_id)
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
                user_name = bot.get_user(user_id)
                print(f"✅ Bắt đầu log người dùng: {user_id}_{user_name}")
            except:
                print("❌ Cú pháp sai.")

        elif cmd.startswith("unloguser "):
            try:
                user_id = int(cmd.split()[1])
                log_user_ids.discard(user_id)
                user_name =  bot.get_user(user_id)
                print(f"✅ Đã dừng log người dùng có ID: {user_id}_{user_name}")
            except:
                print("❌ Cú pháp sai.")

        elif cmd == "listloguser":
            if log_user_ids:
                print("👤 Đang log các user:")
                for uid in log_user_ids:
                    name = bot.get_user(uid)
                    print(f" - {uid}#{name}")
            else:
                print("⚠️ Không có user nào đang được log.")

        elif cmd.startswith("logserver "):
            try:    
                sid = int(cmd.split()[1])
                sun =  bot.get_guild(sid)
                log_server_ids.add(sid)
                print(f"✅ Bắt đầu log server: {sid}_{sun}")
            except:
                print("❌ Cú pháp sai.")

        elif cmd.startswith("unlogserver "):
            try:
                sid = int(cmd.split()[1])
                sun = bot.get_guild(sid)
                log_server_ids.discard(sid)
                print(f"✅ Đã dừng log server ID: {sid}_{sun}")
            except:
                print("❌ Cú pháp sai.")

        elif cmd == "listlogserver":
            if log_server_ids:
                print("🖥️ Đang log các server:")
                for sid in log_server_ids:
                    name = bot.get_guild(sid)
                    print(f" - {sid}#{name}")
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
        
        elif cmd == "":
            print("❌Vui lòng nhập lệnh.")
            
        else:
            print("❌ Lệnh không hợp lệ.")

#### ARE YOU REAĐYYYYYYYYYYYYY????? ####
@bot.event
async def on_ready():
    for guild in bot.guilds:
        await auto_setup_role(guild)
    bot.loop.create_task(precise_loop())
    await bot.wait_until_ready()
    synced = await bot.tree.sync(guild=None)
    print(f"✅Đã đồng bộ {len(synced)} lệnh slash command.\n✅ Bot đã đăng nhập với tài khoản: {bot.user} ({bot.user.id})") 
    threading.Thread(target=terminal_interface, daemon=True).start()
    
@bot.event
async def on_guild_join(guild: discord.Guild):
    print(f"➕ Bot đã được thêm vào server: {guild.name}")
    await auto_setup_muted_role(guild)
    
# -------------------------------------------
# Project: Con của Bắp#9505
# File: main.py
# Author: Phạm Lợi
# Discord: pap_corn
# Created: 16/4/2025
# Last Updated: 11/6/2025
#
# Version: 1.1
#
# Copyright (c) 2025 pap_corn
# All rights reserved.
#
# Bạn không được phép sử dụng, sao chép, sửa đổi hoặc phân phối file này
# nếu không có sự cho phép bằng văn bản từ tác giả.
# -------------------------------------------    

bot.run(TOKEN)
