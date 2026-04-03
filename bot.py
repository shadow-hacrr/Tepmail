import asyncio
import json
import os
import re
import random
import secrets
import string
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from telegram.constants import ParseMode
from telegram.error import Forbidden, BadRequest
import aiohttp

# ============================================
# CONFIG
# ============================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
OWNER_IDS = [int(x.strip()) for x in os.getenv("OWNER_IDS", "8627624927").split(",") if x.strip()]

# 2 Channels + 1 WhatsApp + 1 YouTube
CHANNEL_1 = "@ssbugchannel"
CHANNEL_2 = "@syedhacks"  # CHANGE THIS
YOUTUBE_LINK = "https://youtube.com/@shadowhere.460"
WHATSAPP_LINK = "https://whatsapp.com/channel/0029VbD54jxEgGfIqPaPSK24"

# Banner Image URL
BANNER_URL = "https://i.postimg.cc/zX8C13Tg/header.jpg"

# ============================================
# MAIL.TM API CONFIG
# ============================================
MAIL_API = "https://api.mail.tm"

# ============================================
# FILE STORAGE SYSTEM
# ============================================
DATA_DIR = "bot_data"
os.makedirs(DATA_DIR, exist_ok=True)

def get_path(filename):
    return os.path.join(DATA_DIR, filename)

def load_json(filename, default=None):
    path = get_path(filename)
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return default if default is not None else {}
    return default if default is not None else {}

def save_json(filename, data):
    path = get_path(filename)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def init_files():
    os.makedirs(DATA_DIR, exist_ok=True)
    files = {
        "users.json": {},
        "otp_history.json": [],
        "tokens.json": {},
        "admin_logs.json": []
    }
    for fname, default in files.items():
        if not os.path.exists(get_path(fname)):
            save_json(fname, default)

def get_user(user_id):
    users = load_json("users.json", {})
    return users.get(str(user_id), {})

def save_user(user_id, data):
    users = load_json("users.json", {})
    users[str(user_id)] = data
    save_json("users.json", users)

def get_all_users():
    return load_json("users.json", {})

def add_connected_token(token, added_by, bot_username):
    tokens = load_json("tokens.json", {})
    tokens[token] = {
        "added_by": added_by,
        "added_at": datetime.now().isoformat(),
        "status": "active",
        "bot_username": bot_username
    }
    save_json("tokens.json", tokens)

def remove_connected_token(token):
    tokens = load_json("tokens.json", {})
    if token in tokens:
        del tokens[token]
        save_json("tokens.json", tokens)

def get_connected_tokens():
    return load_json("tokens.json", {})

def add_otp_record(user_id, data):
    history = load_json("otp_history.json", [])
    data['user_id'] = user_id
    data['id'] = secrets.token_hex(6)
    data['time'] = datetime.now().isoformat()
    history.append(data)
    if len(history) > 5000:
        history = history[-5000:]
    save_json("otp_history.json", history)

def get_user_otps(user_id, limit=10):
    history = load_json("otp_history.json", [])
    user_otps = [h for h in history if h.get('user_id') == user_id]
    return sorted(user_otps, key=lambda x: x.get('time', ''), reverse=True)[:limit]

def log_admin(action, admin_id, details=""):
    logs = load_json("admin_logs.json", [])
    logs.append({
        "action": action,
        "admin_id": admin_id,
        "details": details,
        "time": datetime.now().isoformat()
    })
    if len(logs) > 1000:
        logs = logs[-1000:]
    save_json("admin_logs.json", logs)

# ============================================
# VERIFICATION CHECK
# ============================================

async def check_user_joined(bot, user_id):
    try:
        channel1_member = await bot.get_chat_member(CHANNEL_1, user_id)
        channel1_ok = channel1_member.status in ['member', 'administrator', 'creator']

        channel2_member = await bot.get_chat_member(CHANNEL_2, user_id)
        channel2_ok = channel2_member.status in ['member', 'administrator', 'creator']

        return channel1_ok and channel2_ok
    except Exception as e:
        print(f"Check join error: {e}")
        return False

# ============================================
# PREMIUM STYLISH UI WITH EMOJIS
# ============================================

def banner(text):
    return f"✨🔥 {text} 🔥✨"

def divider():
    return "━" * 23

def premium_box(title, content):
    return f"""
╔═══════════════════════╗
║  ✨ {title:^17} ✨  ║
╚═══════════════════════╝
{content}
━━━━━━━━━━━━━━━━━━━━━━━"""

# Keyboards - Premium Style
def start_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📢 ᴄʜᴀɴɴᴇʟ 1", url=f"https://t.me/{CHANNEL_1.replace('@', '')}"),
            InlineKeyboardButton("📢 ᴄʜᴀɴɴᴇʟ 2", url=f"https://t.me/{CHANNEL_2.replace('@', '')}")
        ],
        [
            InlineKeyboardButton("▶️ ʏᴏᴜᴛᴜʙᴇ", url=YOUTUBE_LINK),
            InlineKeyboardButton("💬 ᴡʜᴀᴛsᴀᴘᴘ", url=WHATSAPP_LINK)
        ],
        [InlineKeyboardButton("✅ ᴠᴇʀɪꜰʏ ᴀᴄᴄᴇss", callback_data="verify")]
    ])

def main_menu_kb(is_owner=False):
    buttons = [
        [InlineKeyboardButton("📋 ᴜsᴇʀ ᴍᴇɴᴜ", callback_data="user_menu")],
    ]
    if is_owner:
        buttons.append([InlineKeyboardButton("👑 ᴏᴡɴᴇʀ ᴍᴇɴᴜ", callback_data="owner_menu")])
    return InlineKeyboardMarkup(buttons)

def user_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📧 ɢᴇᴛ ᴛᴇᴍᴘ ᴍᴀɪʟ", callback_data="getmail")],
        [InlineKeyboardButton("📨 ᴄʜᴇᴄᴋ ɪɴʙᴏx", callback_data="inbox")],
        [InlineKeyboardButton("👤 ᴍʏ ᴘʀᴏꜰɪʟᴇ", callback_data="profile")],
        [InlineKeyboardButton("🔙 ʙᴀᴄᴋ ᴛᴏ ᴍᴀɪɴ", callback_data="main_menu")]
    ])

def owner_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 ʙʀᴏᴀᴅᴄᴀsᴛ", callback_data="broadcast")],
        [InlineKeyboardButton("➕ ᴀᴅᴅ ᴛᴏᴋᴇɴ", callback_data="addtoken")],
        [InlineKeyboardButton("📋 ᴛᴏᴋᴇɴ ʟɪsᴛ", callback_data="tokenlist")],
        [InlineKeyboardButton("🗑 ᴄʟᴇᴀʀ ᴛᴏᴋᴇɴs", callback_data="clear_tokens")],
        [InlineKeyboardButton("📊 sᴛᴀᴛɪsᴛɪᴄs", callback_data="stats")],
        [InlineKeyboardButton("🔙 ʙᴀᴄᴋ", callback_data="main_menu")]
    ])

# ============================================
# BOT COMMANDS
# ============================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id

    user_data = get_user(uid)

    if not user_data:
        save_user(uid, {
            "uid": uid,
            "username": user.username,
            "name": user.first_name,
            "joined": datetime.now().isoformat(),
            "verified": False,
            "email": None,
            "email_pass": None,
            "email_token": None
        })

        welcome = premium_box("TempMail by SHADOW", f"""
👤 <b>Name:</b> @{user.username or 'N/A'}
🆔 <b>ID:</b> <code>{uid}</code>
📅 <b>Joined:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}

⚠️ <b>COMPLETE VERIFICATION:</b>

🔗 Join Channel 1
🔗 Join Channel 2  
🔗 Subscribe YouTube
🔗 Join WhatsApp

<i>Then click VERIFY ACCESS</i>""")

        await update.message.reply_photo(
            photo=BANNER_URL,
            caption=welcome,
            parse_mode=ParseMode.HTML,
            reply_markup=start_kb()
        )
    else:
        if user_data.get('verified'):
            await show_main_menu(update, context)
        else:
            text = premium_box("⚠️ NOT VERIFIED", "Please complete verification first!")
            await update.message.reply_photo(
                photo=BANNER_URL,
                caption=text,
                parse_mode=ParseMode.HTML,
                reply_markup=start_kb()
            )

async def verify_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("🔍 Checking...")
    uid = query.from_user.id

    joined = await check_user_joined(context.bot, uid)

    if not joined:
        text = premium_box("❌ NOT JOINED", f"""
⚠️ <b>Please join all channels:</b>

📢 {CHANNEL_1}
📢 {CHANNEL_2}

<i>Then click VERIFY again</i>""")
        await query.edit_message_caption(
            caption=text,
            parse_mode=ParseMode.HTML,
            reply_markup=start_kb()
        )
        return

    user_data = get_user(uid)
    user_data['verified'] = True
    save_user(uid, user_data)

    # Animation
    await query.edit_message_caption(
        caption=premium_box("⚡ VERIFYING...", "Please wait..."),
        parse_mode=ParseMode.HTML
    )
    await asyncio.sleep(0.5)

    await query.edit_message_caption(
        caption=premium_box("✅ ACCESS GRANTED!", "Welcome to TempMail by SHADOW!"),
        parse_mode=ParseMode.HTML
    )
    await asyncio.sleep(0.5)

    await show_main_menu(update, context, from_verify=True)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, from_verify=False):
    user = update.effective_user
    uid = user.id
    is_owner = uid in OWNER_IDS

    text = premium_box("TempMail by SHADOW", f"""
👤 <b>Name:</b> @{user.username or 'N/A'}
🆔 <b>ID:</b> <code>{uid}</code>
⏰ <b>Online:</b> {datetime.now().strftime('%H:%M:%S')}

⚡ <i>Select an option below:</i>""")

    if from_verify:
        await update.callback_query.edit_message_caption(
            caption=text,
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu_kb(is_owner)
        )
    else:
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text,
                parse_mode=ParseMode.HTML,
                reply_markup=main_menu_kb(is_owner)
            )
        else:
            await update.effective_message.reply_photo(
                photo=BANNER_URL,
                caption=text,
                parse_mode=ParseMode.HTML,
                reply_markup=main_menu_kb(is_owner)
            )

# ============================================
# USER MENU HANDLER
# ============================================

async def user_menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("📋 Opening User Menu...")

    text = premium_box("📋 USER MENU", """
📧 <b>Get Temp Mail</b> - Free unlimited emails
📨 <b>Check Inbox</b> - View received OTPs
👤 <b>My Profile</b> - Your account info

💯 <b>100% FREE</b> - No limits!""")

    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=user_menu_kb()
    )

# ============================================
# MAIL.TM INTEGRATION
# ============================================

async def getmail_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("📧 Generating...")
    uid = query.from_user.id

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{MAIL_API}/domains") as resp:
                domains_resp = await resp.json()
                members = domains_resp.get('hydra:member', [])
                if not members:
                    raise Exception("No domains available!")
                domain = random.choice(members)['domain']

            username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))
            email = f"{username}@{domain}"
            password = ''.join(random.choices(string.ascii_letters + string.digits, k=15))

            async with session.post(f"{MAIL_API}/accounts", json={"address": email, "password": password}) as resp:
                if resp.status != 201:
                    raise Exception("Failed to create account")

            async with session.post(f"{MAIL_API}/token", json={"address": email, "password": password}) as resp:
                token_data = await resp.json()
                token = token_data.get('token')
                if not token:
                    raise Exception("Token failed")

            user_data = get_user(uid)
            user_data.update({
                'email': email,
                'email_pass': password,
                'email_token': token,
                'email_created': datetime.now().isoformat()
            })
            save_user(uid, user_data)

            asyncio.create_task(poll_otp_task(uid, email, token, context.bot))

            mail_text = premium_box("📧 TEMP MAIL READY", f"""
📬 <b>Email:</b> <code>{email}</code>
🔑 <b>Password:</b> <code>{password}</code>
⏱ <b>Expires:</b> 15 minutes

⚡ <b>OTP will appear automatically!</b>
💯 <b>100% FREE</b> - Unlimited emails""")

            await query.edit_message_text(
                mail_text, 
                parse_mode=ParseMode.HTML, 
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 ɴᴇᴡ ᴍᴀɪʟ", callback_data="getmail")],
                    [InlineKeyboardButton("📨 ᴄʜᴇᴄᴋ ɪɴʙᴏx", callback_data="inbox")],
                    [InlineKeyboardButton("📋 ᴜsᴇʀ ᴍᴇɴᴜ", callback_data="user_menu")]
                ])
            )
    except Exception as e:
        await query.edit_message_text(
            f"❌ <b>Error:</b> <code>{str(e)}</code>\n\nTry again!", 
            parse_mode=ParseMode.HTML
        )

async def poll_otp_task(uid, email, token, bot):
    headers = {"Authorization": f"Bearer {token}"}
    seen = set()
    try:
        for _ in range(180):
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{MAIL_API}/messages", headers=headers) as resp:
                    data = await resp.json()
                    messages = data.get('hydra:member', [])

                    for msg in messages:
                        mid = msg.get('id')
                        if mid and mid not in seen:
                            seen.add(mid)

                            async with session.get(f"{MAIL_API}/messages/{mid}", headers=headers) as r:
                                detail = await r.json()
                                subject = detail.get('subject', 'No Subject')
                                sender = detail.get('from', {}).get('address', 'Unknown')
                                body = detail.get('text', '') or detail.get('html', '')

                                otp = extract_otp(subject + " " + body)

                                add_otp_record(uid, {
                                    "from": sender, 
                                    "subject": subject, 
                                    "otp": otp, 
                                    "body": body[:200]
                                })

                                alert = f"""🚨 {banner("OTP RECEIVED")} 🚨

{divider()}
📧 <b>From:</b> <code>{sender}</code>
📝 <b>Subject:</b> <code>{subject}</code>
{divider()}

🔐 <b>OTP CODE:</b>
<code>{otp or 'Not found in email'}</code>

⏰ <b>Time:</b> {datetime.now().strftime('%H:%M:%S')}"""
                                await bot.send_message(uid, alert, parse_mode=ParseMode.HTML)
            await asyncio.sleep(5)
    except Exception as e:
        print(f"Polling error: {e}")
    finally:
        user_data = get_user(uid)
        if user_data.get('email') == email:
            user_data['email'] = None
            user_data['email_token'] = None
            save_user(uid, user_data)
        await bot.send_message(
            uid, 
            "⏱️ <b>Email expired!</b>\nUse /start to get new one.", 
            parse_mode=ParseMode.HTML
        )

def extract_otp(text):
    if not text:
        return None

    text = text.replace(chr(10), ' ').replace(chr(13), ' ')

    patterns = [
        r'(\d{3}[-\s]\d{3})',
        r'\b(\d{6})\b',
        r'\b(\d{4})\b',
        r'\b(\d{8})\b',
        r'(?i)otp[:\s]+(\d{3}[-\s]?\d{3})',
        r'(?i)otp[:\s]+(\d+)',
        r'(?i)code[:\s]+(\d{3}[-\s]\d{3})',
        r'(?i)code[:\s]+(\d+)',
        r'(?i)verification[:\s]+(\d+)',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            if match:
                return match.strip()

    return None

# ============================================
# OTHER HANDLERS
# ============================================

async def inbox_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("📨 Checking inbox...")
    uid = query.from_user.id
    user_data = get_user(uid)
    email = user_data.get('email')

    if not email:
        text = premium_box("❌ NO ACTIVE EMAIL", "Get one first!")
        await query.edit_message_text(
            text, 
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📧 ɢᴇᴛ ᴍᴀɪʟ", callback_data="getmail")]
            ])
        )
        return

    otps = get_user_otps(uid, 5)
    lines = [premium_box("📨 INBOX", f"""
📬 <b>Email:</b> <code>{email}</code>""")]

    if otps:
        for i, o in enumerate(otps, 1):
            otp_disp = o.get('otp', 'N/A') or 'N/A'
            time_disp = o.get('time', '')
            if time_disp:
                time_disp = time_disp[11:16]
            lines.append(f"{i}. 🔐 <code>{otp_disp}</code> | ⏰ {time_disp}")
    else:
        lines.append("<i>Waiting for OTP...</i>")

    text = "\n".join(lines) + "\n" + divider()

    await query.edit_message_text(
        text, 
        parse_mode=ParseMode.HTML, 
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 ʀᴇꜰʀᴇsʜ", callback_data="inbox")],
            [InlineKeyboardButton("📋 ᴜsᴇʀ ᴍᴇɴᴜ", callback_data="user_menu")]
        ])
    )

async def profile_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("👤 Loading profile...")
    uid = query.from_user.id
    user_data = get_user(uid)

    text = premium_box("👤 MY PROFILE", f"""
🆔 <b>ID:</b> <code>{uid}</code>
👤 <b>Name:</b> {user_data.get('name', 'N/A')}
📧 <b>Active Email:</b> <code>{user_data.get('email') or 'None'}</code>

✅ <b>FREE USER</b> - Unlimited access!""")

    await query.edit_message_text(
        text, 
        parse_mode=ParseMode.HTML, 
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 ᴜsᴇʀ ᴍᴇɴᴜ", callback_data="user_menu")]
        ])
    )

# ============================================
# OWNER MENU
# ============================================

async def owner_menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("👑 Opening Owner Menu...")
    uid = query.from_user.id

    if uid not in OWNER_IDS:
        await query.answer("❌ Owner only!", show_alert=True)
        return

    text = premium_box("👑 OWNER MENU", f"""
🆔 <b>Admin ID:</b> <code>{uid}</code>
⏰ <b>Time:</b> {datetime.now().strftime('%H:%M:%S')}

⚡ <i>Select admin action:</i>""")

    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=owner_menu_kb()
    )

async def broadcast_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id

    if uid not in OWNER_IDS:
        await query.answer("❌ Owner only!", show_alert=True)
        return

    await query.answer("📢 Send broadcast message...")

    await query.edit_message_text(
        premium_box("📢 BROADCAST", """
📝 <b>Send your message now</b>
<i>(Type /cancel to abort)</i>

📊 <b>Target:</b> All users"""),
        parse_mode=ParseMode.HTML
    )
    context.user_data['awaiting_broadcast'] = True

async def addtoken_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id

    if uid not in OWNER_IDS:
        await query.answer("❌ Owner only!", show_alert=True)
        return

    await query.answer("➕ Send bot token...")

    await query.edit_message_text(
        premium_box("➕ ADD TOKEN", """
📝 <b>Send bot token to connect</b>
<i>(Type /cancel to abort)</i>

<code>Format: 123456789:ABCdef...</code>

⚠️ <b>Bot will be online instantly!</b>"""),
        parse_mode=ParseMode.HTML
    )
    context.user_data['awaiting_token'] = True

async def tokenlist_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("📋 Loading tokens...")
    uid = query.from_user.id

    if uid not in OWNER_IDS:
        await query.answer("❌ Owner only!", show_alert=True)
        return

    tokens = get_connected_tokens()

    if not tokens:
        text = premium_box("📋 TOKEN LIST", "<i>No connected bots found.</i>")
    else:
        lines = [premium_box("📋 CONNECTED BOTS", f"<b>Total:</b> {len(tokens)} bots"), ""]
        for i, (token, data) in enumerate(tokens.items(), 1):
            bot_name = data.get('bot_username', 'Unknown')
            added = data.get('added_at', 'Unknown')[:10]
            lines.append(f"{i}. 🤖 @{bot_name}")
            lines.append(f"   📅 {added}\n")
        text = "\n".join(lines)

    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 ʙᴀᴄᴋ", callback_data="owner_menu")]
        ])
    )

async def stats_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("📊 Loading stats...")
    uid = query.from_user.id

    if uid not in OWNER_IDS:
        await query.answer("❌ Owner only!", show_alert=True)
        return

    users = get_all_users()
    tokens = get_connected_tokens()

    verified = sum(1 for u in users.values() if u.get('verified'))

    text = premium_box("📊 STATISTICS", f"""
👥 <b>Total Users:</b> <code>{len(users)}</code>
✅ <b>Verified:</b> <code>{verified}</code>
🤖 <b>Connected Bots:</b> <code>{len(tokens)}</code>

📅 <b>Date:</b> {datetime.now().strftime('%Y-%m-%d')}""")

    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 ʙᴀᴄᴋ", callback_data="owner_menu")]
        ])
    )

async def clear_tokens_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("🗑 Clearing tokens...")
    uid = query.from_user.id

    if uid not in OWNER_IDS:
        await query.answer("❌ Owner only!", show_alert=True)
        return

    save_json("tokens.json", {})
    log_admin("clear_tokens", uid, "All tokens cleared")

    await query.edit_message_text(
        premium_box("✅ TOKENS CLEARED", "All connected bots removed."),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 ʙᴀᴄᴋ", callback_data="owner_menu")]
        ])
    )

# ============================================
# MESSAGE HANDLERS
# ============================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if uid not in OWNER_IDS:
        return

    if context.user_data.get('awaiting_broadcast'):
        context.user_data['awaiting_broadcast'] = False
        message = update.message

        await message.reply_text("📤 <b>Broadcasting...</b>", parse_mode=ParseMode.HTML)

        users = get_all_users()
        sent = 0
        failed = 0

        for user_id in users.keys():
            try:
                if message.photo:
                    await context.bot.send_photo(
                        chat_id=user_id,
                        photo=message.photo[-1].file_id,
                        caption=message.caption,
                        parse_mode=ParseMode.HTML
                    )
                elif message.video:
                    await context.bot.send_video(
                        chat_id=user_id,
                        video=message.video.file_id,
                        caption=message.caption,
                        parse_mode=ParseMode.HTML
                    )
                else:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=message.text,
                        parse_mode=ParseMode.HTML
                    )
                sent += 1
                await asyncio.sleep(0.1)
            except (Forbidden, BadRequest):
                failed += 1

        log_admin("broadcast", uid, f"Sent: {sent}, Failed: {failed}")
        await message.reply_text(
            premium_box("✅ BROADCAST COMPLETE", f"""
📤 <b>Sent:</b> <code>{sent}</code>
❌ <b>Failed:</b> <code>{failed}</code>"""),
            parse_mode=ParseMode.HTML
        )
        return

    if context.user_data.get('awaiting_token'):
        context.user_data['awaiting_token'] = False
        token = update.message.text.strip()

        if not re.match(r'^\d+:[A-Za-z0-9_-]+$', token):
            await update.message.reply_text("❌ <b>Invalid token format!</b>")
            return

        tokens = get_connected_tokens()
        if token in tokens:
            await update.message.reply_text("❌ <b>Token already connected!</b>")
            return

        try:
            from telegram import Bot
            test_bot = Bot(token)
            bot_info = await test_bot.get_me()
            bot_name = bot_info.username

            add_connected_token(token, uid, bot_name)
            log_admin("add_token", uid, f"Bot: @{bot_name}")

            await start_connected_bot(token, bot_name)

            await update.message.reply_text(
                premium_box("✅ BOT ONLINE", f"""
🤖 <b>Bot:</b> @{bot_name}
🔑 <b>Status:</b> <code>ONLINE</code>
⏰ <b>Connected:</b> {datetime.now().strftime('%H:%M:%S')}

✅ <b>Bot is now live and working!</b>"""),
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            await update.message.reply_text(f"❌ <b>Invalid token!</b>\nError: {str(e)}")
        return

async def start_connected_bot(token, bot_username):
    try:
        app = Application.builder().token(token).build()

        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("cancel", cancel_cmd))

        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        app.add_handler(CallbackQueryHandler(verify_cb, pattern="^verify$"))
        app.add_handler(CallbackQueryHandler(getmail_cb, pattern="^getmail$"))
        app.add_handler(CallbackQueryHandler(inbox_cb, pattern="^inbox$"))
        app.add_handler(CallbackQueryHandler(profile_cb, pattern="^profile$"))
        app.add_handler(CallbackQueryHandler(user_menu_cb, pattern="^user_menu$"))
        app.add_handler(CallbackQueryHandler(show_main_menu, pattern="^main_menu$"))

        app.add_handler(CallbackQueryHandler(owner_menu_cb, pattern="^owner_menu$"))
        app.add_handler(CallbackQueryHandler(broadcast_cb, pattern="^broadcast$"))
        app.add_handler(CallbackQueryHandler(addtoken_cb, pattern="^addtoken$"))
        app.add_handler(CallbackQueryHandler(tokenlist_cb, pattern="^tokenlist$"))
        app.add_handler(CallbackQueryHandler(stats_cb, pattern="^stats$"))
        app.add_handler(CallbackQueryHandler(clear_tokens_cb, pattern="^clear_tokens$"))

        asyncio.create_task(app.run_polling())
        print(f"Connected bot @{bot_username} is now ONLINE!")

    except Exception as e:
        print(f"Failed to start connected bot: {e}")

async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    is_owner = update.effective_user.id in OWNER_IDS
    await update.message.reply_text(
        "❌ <b>Cancelled.</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_kb(is_owner)
    )

# ============================================
# MAIN
# ============================================

def main():
    init_files()

    print("🔥 TempMail by SHADOW - Starting...")
    print(f"👑 Owners: {OWNER_IDS}")
    print("💯 100% FREE system active")

    app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel_cmd))

    # Message handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Callback handlers
    app.add_handler(CallbackQueryHandler(verify_cb, pattern="^verify$"))
    app.add_handler(CallbackQueryHandler(getmail_cb, pattern="^getmail$"))
    app.add_handler(CallbackQueryHandler(inbox_cb, pattern="^inbox$"))
    app.add_handler(CallbackQueryHandler(profile_cb, pattern="^profile$"))
    app.add_handler(CallbackQueryHandler(user_menu_cb, pattern="^user_menu$"))
    app.add_handler(CallbackQueryHandler(show_main_menu, pattern="^main_menu$"))

    # Owner callbacks
    app.add_handler(CallbackQueryHandler(owner_menu_cb, pattern="^owner_menu$"))
    app.add_handler(CallbackQueryHandler(broadcast_cb, pattern="^broadcast$"))
    app.add_handler(CallbackQueryHandler(addtoken_cb, pattern="^addtoken$"))
    app.add_handler(CallbackQueryHandler(tokenlist_cb, pattern="^tokenlist$"))
    app.add_handler(CallbackQueryHandler(stats_cb, pattern="^stats$"))
    app.add_handler(CallbackQueryHandler(clear_tokens_cb, pattern="^clear_tokens$"))

    print("✅ Bot ready!")
    app.run_polling()

if __name__ == "__main__":
    main()
