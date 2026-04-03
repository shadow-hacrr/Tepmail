import asyncio
import json
import os
import re
import random
import secrets
import string
import hashlib
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from telegram.constants import ParseMode
from telegram.error import Forbidden, BadRequest
import aiohttp

# ============================================
# 🔧 CONFIG - YAHAN SIRF YEH CHANGE KARO
# ============================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
OWNER_IDS = [int(x.strip()) for x in os.getenv("OWNER_IDS", "8627624927").split(",") if x.strip()]

# 2 Channels + 1 WhatsApp + 1 YouTube
CHANNEL_1 = "@ssbugchannel"           # First Channel
CHANNEL_2 = "@syedhacks"     # Second Channel (CHANGE THIS)
YOUTUBE_LINK = "https://youtube.com/@shadowhere.460"
WHATSAPP_LINK = "https://whatsapp.com/channel/0029VbD54jxEgGfIqPaPSK24"

# Banner Image URL (Apni image ka URL daalo)
BANNER_URL = "https://i.postimg.cc/zX8C13Tg/header.jpg"

# ============================================
# ⚙️ MAIL.TM API CONFIG
# ============================================
MAIL_API = "https://api.mail.tm"

# ============================================
# 📁 FILE STORAGE SYSTEM
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
        "tokens.json": {},  # Connected bots
        "admin_logs.json": []
    }
    for fname, default in files.items():
        if not os.path.exists(get_path(fname)):
            save_json(fname, default)

# User management
def get_user(user_id):
    users = load_json("users.json", {})
    return users.get(str(user_id), {})

def save_user(user_id, data):
    users = load_json("users.json", {})
    users[str(user_id)] = data
    save_json("users.json", users)

def get_all_users():
    return load_json("users.json", {})

# Connected Tokens (Sub-bots)
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

# OTP History
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

# Admin Logs
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
# 🔍 VERIFICATION CHECK
# ============================================

async def check_user_joined(bot, user_id):
    """Check if user joined both channels"""
    try:
        # Check channel 1
        channel1_member = await bot.get_chat_member(CHANNEL_1, user_id)
        channel1_ok = channel1_member.status in ['member', 'administrator', 'creator']
        
        # Check channel 2
        channel2_member = await bot.get_chat_member(CHANNEL_2, user_id)
        channel2_ok = channel2_member.status in ['member', 'administrator', 'creator']
        
        return channel1_ok and channel2_ok
    except Exception as e:
        print(f"Check join error: {e}")
        return False

# ============================================
# 🎨 UI & STYLISH DESIGN - MOBILE FRIENDLY
# ============================================

def stylish_banner(text):
    """Stylish banner for mobile"""
    return f"""
┏━━━━━🔥 <b>{text}</b> 🔥━━━━━┓"""

def box_text(content):
    """Box style for mobile"""
    return f"""
┣━━━━━━━━━━━━━━━━━━━━━┫
{content}
┗━━━━━━━━━━━━━━━━━━━━━┛"""

# Keyboards - Mobile Optimized
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
        [InlineKeyboardButton("🔐 ᴠᴇʀɪꜰʏ ᴀᴄᴄᴇss", callback_data="verify")]
    ])

def main_menu_kb(is_owner=False):
    """Main menu - Image jaisa style"""
    buttons = [
        [InlineKeyboardButton("|| ᴜsᴇʀ ᴍᴇɴᴜ", callback_data="user_menu")],
    ]
    if is_owner:
        buttons.append([InlineKeyboardButton("|| ᴏᴡɴᴇʀ ᴍᴇɴᴜ", callback_data="owner_menu")])
    return InlineKeyboardMarkup(buttons)

def user_menu_kb():
    """User Menu - All free features"""
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
# 🤖 BOT COMMANDS
# ============================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    
    user_data = get_user(uid)
    
    if not user_data:
        # New user
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
        
        welcome = f"""
{stylish_banner("ᴄʏʙᴇʀ ʜᴀᴄᴋᴇʀ ʙᴏᴛ")}

┣ 👤 <b>ɴᴀᴍᴇ:</b> <code>@{user.username or 'N/A'}</code>
┣ 🆔 <b>ɪᴅ:</b> <code>{uid}</code>
┣ ⏰ <b>ᴊᴏɪɴᴇᴅ:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}

{box_text(""" <b>ᴄᴏᴍᴘʟᴇᴛᴇ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ:</b>

┣ 🔗 ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ 1
┣ 🔗 ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ 2  
┣ 🔗 ꜱᴜʙsᴄʀɪʙᴇ ʏᴏᴜᴛᴜʙᴇ
┣ 🔗 ᴊᴏɪɴ ᴡʜᴀᴛsᴀᴘᴘ

<code>🔻 ᴛʜᴇɴ ᴄʟɪᴄᴋ ᴠᴇʀɪꜰʏ 🔻</code>""")}
"""
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
            await update.message.reply_photo(
                photo=BANNER_URL,
                caption=f"{stylish_banner('⚠️ ɴᴏᴛ ᴠᴇʀɪꜰɪᴇᴅ')}\n\n<code>ᴘʟᴇᴀsᴇ ᴄᴏᴍᴘʟᴇᴛᴇ ᴠᴇʀɪꜰɪᴄᴀᴛɪᴏɴ ꜰɪʀsᴛ!</code>",
                parse_mode=ParseMode.HTML,
                reply_markup=start_kb()
            )

async def verify_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("ᴄʜᴇᴄᴋɪɴɢ...")
    uid = query.from_user.id
    
    # ACTUAL CHECK
    joined = await check_user_joined(context.bot, uid)
    
    if not joined:
        await query.edit_message_caption(
            caption=f"""
{stylish_banner("❌ ɴᴏᴛ ᴊᴏɪɴᴇᴅ")}

┣ ⚠️ <b>ᴘʟᴇᴀsᴇ ᴊᴏɪɴ ᴀʟʟ:</b>

┣ 📢 {CHANNEL_1}
┣ 📢 {CHANNEL_2}

<code>ᴛʜᴇɴ ᴄʟɪᴄᴋ ᴠᴇʀɪꜰʏ ᴀɢᴀɪɴ</code>""",
            parse_mode=ParseMode.HTML,
            reply_markup=start_kb()
        )
        return
    
    # Save verified status
    user_data = get_user(uid)
    user_data['verified'] = True
    save_user(uid, user_data)
    
    # Success animation messages
    await query.edit_message_caption(
        caption=f"{stylish_banner('⚡ ᴠᴇʀɪꜰʏɪɴɢ...')}",
        parse_mode=ParseMode.HTML
    )
    await asyncio.sleep(0.5)
    
    await query.edit_message_caption(
        caption=f"{stylish_banner('🔓 ᴀᴄᴄᴇss ɢʀᴀɴᴛᴇᴅ!')}",
        parse_mode=ParseMode.HTML
    )
    await asyncio.sleep(0.5)
    
    # Auto start bot - Show main menu directly
    await show_main_menu(update, context, from_verify=True)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, from_verify=False):
    """Show main menu like the image style"""
    user = update.effective_user
    uid = user.id
    is_owner = uid in OWNER_IDS
    
    text = f"""
{stylish_banner("ᴄʏʙᴇʀ ʜᴀᴄᴋᴇʀ ʙᴏᴛ")}

┣━┫ sʜᴀᴅᴏᴡ ┣━┫

┣ 👤 <b>ɴᴀᴍᴇ:</b> @{user.username or 'N/A'}
┣ 🆔 <b>ɪᴅ:</b> <code>{uid}</code>
┣ ⏰ <b>ᴏɴʟɪɴᴇ:</b> {datetime.now().strftime('%H:%M:%S')}

{box_text("<code>⚡ sᴇʟᴇᴄᴛ ᴍᴇɴᴜ ⚡</code>")}"""
    
    if from_verify:
        # Edit the verification message
        await update.callback_query.edit_message_caption(
            caption=text,
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
# 📧 MAIL.TM INTEGRATION - 100% FREE
# ============================================

async def getmail_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("ɢᴇɴᴇʀᴀᴛɪɴɢ...")
    uid = query.from_user.id
    
    try:
        async with aiohttp.ClientSession() as session:
            # Get domain
            async with session.get(f"{MAIL_API}/domains") as resp:
                domains_resp = await resp.json()
                members = domains_resp.get('hydra:member', [])
                if not members:
                    raise Exception("No domains available!")
                domain = random.choice(members)['domain']

            # Create account
            username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))
            email = f"{username}@{domain}"
            password = ''.join(random.choices(string.ascii_letters + string.digits, k=15))

            async with session.post(f"{MAIL_API}/accounts", json={"address": email, "password": password}) as resp:
                if resp.status != 201:
                    raise Exception("Failed to create account")

            # Get token
            async with session.post(f"{MAIL_API}/token", json={"address": email, "password": password}) as resp:
                token_data = await resp.json()
                token = token_data.get('token')
                if not token:
                    raise Exception("Token failed")

            # Save user data
            user_data = get_user(uid)
            user_data.update({
                'email': email,
                'email_pass': password,
                'email_token': token,
                'email_created': datetime.now().isoformat()
            })
            save_user(uid, user_data)

            # Start polling
            asyncio.create_task(poll_otp_task(uid, email, token, context.bot))

            mail_text = f"""
{stylish_banner("📧 ᴛᴇᴍᴘ ᴍᴀɪʟ ʀᴇᴀᴅʏ")}

┣ 📬 <b>ᴇᴍᴀɪʟ:</b> <code>{email}</code>
┣ 🔑 <b>ᴘᴀssᴡᴏʀᴅ:</b> <code>{password}</code>
┣ ⏱ <b>ᴇxᴘɪʀᴇs:</b> 15 ᴍɪɴᴜᴛᴇs

{box_text("""⚡ <b>ᴏᴛᴘ ᴡɪʟʟ ᴀᴘᴘᴇᴀʀ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ!

💯 100% ꜰʀᴇᴇ - ᴜɴʟɪᴍɪᴛᴇᴅ ᴇᴍᴀɪʟs""")}
"""
            await query.edit_message_text(
                mail_text, 
                parse_mode=ParseMode.HTML, 
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 ɴᴇᴡ ᴍᴀɪʟ", callback_data="getmail")],
                    [InlineKeyboardButton("📨 ᴄʜᴇᴄᴋ ɪɴʙᴏx", callback_data="inbox")],
                    [InlineKeyboardButton("🔙 ᴜsᴇʀ ᴍᴇɴᴜ", callback_data="user_menu")]
                ])
            )
    except Exception as e:
        await query.edit_message_text(
            f"❌ <b>ᴇʀʀᴏʀ:</b> <code>{str(e)}</code>\n\nᴛʀʏ ᴀɢᴀɪɴ!", 
            parse_mode=ParseMode.HTML
        )

async def poll_otp_task(uid, email, token, bot):
    headers = {"Authorization": f"Bearer {token}"}
    seen = set()
    try:
        for _ in range(180):  # 15 min
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
                                
                                alert = f"""
{stylish_banner("🚨 ᴏᴛᴘ ʀᴇᴄᴇɪᴠᴇᴅ 🚨")}

┣ 📧 <b>ꜰʀᴏᴍ:</b> <code>{sender}</code>
┣ 📝 <b>sᴜʙᴊᴇᴄᴛ:</b> <code>{subject}</code>

{box_text(f"""🔐 <b>ᴏᴛᴘ ᴄᴏᴅᴇ:</b>
<code>{otp or 'Not found'}</code>

⏰ {datetime.now().strftime('%H:%M:%S')}""")}
"""
                                await bot.send_message(uid, alert, parse_mode=ParseMode.HTML)
            await asyncio.sleep(5)
    except Exception as e:
        print(f"Polling error: {e}")
    finally:
        # Cleanup
        user_data = get_user(uid)
        if user_data.get('email') == email:
            user_data['email'] = None
            user_data['email_token'] = None
            save_user(uid, user_data)
        await bot.send_message(
            uid, 
            "⏱️ <b>ᴇᴍᴀɪʟ ᴇxᴘɪʀᴇᴅ!</b>\nᴜsᴇ /sᴛᴀʀᴛ ᴛᴏ ɢᴇᴛ ɴᴇᴡ ᴏɴᴇ.", 
            parse_mode=ParseMode.HTML
        )

def extract_otp(text):
    """Extract OTP from text"""
    if not text:
        return None
    
    text = text.replace('\n', ' ').replace('\r', ' ')
    
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
# 📨 OTHER HANDLERS
# ============================================

async def inbox_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    user_data = get_user(uid)
    email = user_data.get('email')
    
    if not email:
        await query.edit_message_text(
            f"{stylish_banner('❌ ɴᴏ ᴀᴄᴛɪᴠᴇ ᴇᴍᴀɪʟ')}\n\nɢᴇᴛ ᴏɴᴇ ꜰɪʀsᴛ!", 
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📧 ɢᴇᴛ ᴍᴀɪʟ", callback_data="getmail")]
            ])
        )
        return
    
    otps = get_user_otps(uid, 5)
    text = f"""
{stylish_banner("📨 ɪɴʙᴏx")}

┣ 📬 <b>ᴇᴍᴀɪʟ:</b> <code>{email}</code>

┣━━━━━━━━━━━━━━━━━━━━━┫"""
    
    if otps:
        for i, o in enumerate(otps, 1):
            otp_disp = o.get('otp', 'N/A') or 'N/A'
            time_disp = o.get('time', '')
            if time_disp:
                time_disp = time_disp[11:16]
            text += f"\n┣ {i}. <b>ᴏᴛᴘ:</b> <code>{otp_disp}</code> | ⏰ {time_disp}"
    else:
        text += "\n┣ <i>ᴡᴀɪᴛɪɴɢ ꜰᴏʀ ᴏᴛᴘ...</i>"
    
    text += "\n┗━━━━━━━━━━━━━━━━━━━━━┛"
    
    await query.edit_message_text(
        text, 
        parse_mode=ParseMode.HTML, 
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 ʀᴇꜰʀᴇsʜ", callback_data="inbox")],
            [InlineKeyboardButton("🔙 ᴜsᴇʀ ᴍᴇɴᴜ", callback_data="user_menu")]
        ])
    )

async def profile_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    user_data = get_user(uid)
    
    text = f"""
{stylish_banner("👤 ᴘʀᴏꜰɪʟᴇ")}

┣ 🆔 <b>ɪᴅ:</b> <code>{uid}</code>
┣ 👤 <b>ɴᴀᴍᴇ:</b> {user_data.get('name', 'N/A')}
┣ 📧 <b>ᴀᴄᴛɪᴠᴇ ᴇᴍᴀɪʟ:</b> <code>{user_data.get('email') or 'None'}</code>

{box_text("💯 <b>ꜰʀᴇᴇ ᴜsᴇʀ</b> - ᴜɴʟɪᴍɪᴛᴇᴅ ᴀᴄᴄᴇss")}
"""
    await query.edit_message_text(
        text, 
        parse_mode=ParseMode.HTML, 
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 ᴜsᴇʀ ᴍᴇɴᴜ", callback_data="user_menu")]
        ])
    )

# ============================================
# 👑 OWNER MENU & COMMANDS
# ============================================

async def owner_menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    
    if uid not in OWNER_IDS:
        await query.answer("❌ ᴏᴡɴᴇʀ ᴏɴʟʏ!", show_alert=True)
        return
    
    text = f"""
{stylish_banner("👑 ᴏᴡɴᴇʀ ᴍᴇɴᴜ")}

┣ 🆔 <b>ᴀᴅᴍɪɴ ɪᴅ:</b> <code>{uid}</code>
┣ ⏰ <b>ᴛɪᴍᴇ:</b> {datetime.now().strftime('%H:%M:%S')}

{box_text("<code>⚡ sᴇʟᴇᴄᴛ ᴀᴅᴍɪɴ ᴀᴄᴛɪᴏɴ ⚡</code>")}
"""
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=owner_menu_kb()
    )

async def broadcast_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    
    if uid not in OWNER_IDS:
        await query.answer("❌ ᴏᴡɴᴇʀ ᴏɴʟʏ!", show_alert=True)
        return
    
    await query.edit_message_text(
        f"""{stylish_banner("📢 ʙʀᴏᴀᴅᴄᴀsᴛ")}

┣ 📝 <b>sᴇɴᴅ ʏᴏᴜʀ ᴍᴇssᴀɢᴇ ɴᴏᴡ</b>
┣ <code>(ᴛʏᴘᴇ /ᴄᴀɴᴄᴇʟ ᴛᴏ ᴀʙᴏʀᴛ)</code>

┣ 📊 <b>ᴛᴀʀɢᴇᴛ:</b> ᴀʟʟ ᴜsᴇʀs
┣ ⏰ <b>ᴛɪᴍᴇ:</b> {datetime.now().strftime('%H:%M:%S')}""",
        parse_mode=ParseMode.HTML
    )
    context.user_data['awaiting_broadcast'] = True

async def addtoken_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    
    if uid not in OWNER_IDS:
        await query.answer("❌ ᴏᴡɴᴇʀ ᴏɴʟʏ!", show_alert=True)
        return
    
    await query.edit_message_text(
        f"""{stylish_banner("➕ ᴀᴅᴅ ᴛᴏᴋᴇɴ")}

┣ 📝 <b>sᴇɴᴅ ʙᴏᴛ ᴛᴏᴋᴇɴ ᴛᴏ ᴄᴏɴɴᴇᴄᴛ</b>
┣ <code>(ᴛʏᴘᴇ /ᴄᴀɴᴄᴇʟ ᴛᴏ ᴀʙᴏʀᴛ)</code>

┣ <code>ꜰᴏʀᴍᴀᴛ: 123456789:ᴀʙᴄᴅᴇꜰ...</code>

⚠️ <b>ʙᴏᴛ ᴡɪʟʟ ʙᴇ ᴏɴʟɪɴᴇ ɪɴsᴛᴀɴᴛʟʏ!</b>""",
        parse_mode=ParseMode.HTML
    )
    context.user_data['awaiting_token'] = True

async def tokenlist_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    
    if uid not in OWNER_IDS:
        await query.answer("❌ ᴏᴡɴᴇʀ ᴏɴʟʏ!", show_alert=True)
        return
    
    tokens = get_connected_tokens()
    
    if not tokens:
        text = f"""{stylish_banner("📋 ᴛᴏᴋᴇɴ ʟɪsᴛ")}
        
┣ <i>ɴᴏ ᴄᴏɴɴᴇᴄᴛᴇᴅ ʙᴏᴛs ꜰᴏᴜɴᴅ.</i>"""
    else:
        text = f"""{stylish_banner("📋 ᴄᴏɴɴᴇᴄᴛᴇᴅ ʙᴏᴛs")}

┣ <b>ᴛᴏᴛᴀʟ:</b> {len(tokens)} ʙᴏᴛs

"""
        for i, (token, data) in enumerate(tokens.items(), 1):
            bot_name = data.get('bot_username', 'Unknown')
            added = data.get('added_at', 'Unknown')[:10]
            text += f"┣ {i}. @{bot_name}\n┣    📅 {added}\n\n"
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 ʙᴀᴄᴋ", callback_data="owner_menu")]
        ])
    )

async def stats_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    
    if uid not in OWNER_IDS:
        await query.answer("❌ ᴏᴡɴᴇʀ ᴏɴʟʏ!", show_alert=True)
        return
    
    users = get_all_users()
    tokens = get_connected_tokens()
    
    verified = sum(1 for u in users.values() if u.get('verified'))
    
    text = f"""
{stylish_banner("📊 sᴛᴀᴛɪsᴛɪᴄs")}

┣ 👥 <b>ᴛᴏᴛᴀʟ ᴜsᴇʀs:</b> <code>{len(users)}</code>
┣ ✅ <b>ᴠᴇʀɪꜰɪᴇᴅ:</b> <code>{verified}</code>
┣ 🤖 <b>ᴄᴏɴɴᴇᴄᴛᴇᴅ ʙᴏᴛs:</b> <code>{len(tokens)}</code>

┣ 📅 <b>ᴅᴀᴛᴇ:</b> {datetime.now().strftime('%Y-%m-%d')}
┗━━━━━━━━━━━━━━━━━━━━━┛
"""
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 ʙᴀᴄᴋ", callback_data="owner_menu")]
        ])
    )

async def clear_tokens_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    
    if uid not in OWNER_IDS:
        await query.answer("❌ ᴏᴡɴᴇʀ ᴏɴʟʏ!", show_alert=True)
        return
    
    save_json("tokens.json", {})
    log_admin("clear_tokens", uid, "All tokens cleared")
    
    await query.edit_message_text(
        f"{stylish_banner('✅ ᴛᴏᴋᴇɴs ᴄʟᴇᴀʀᴇᴅ')}\n\nᴀʟʟ ᴄᴏɴɴᴇᴄᴛᴇᴅ ʙᴏᴛs ʀᴇᴍᴏᴠᴇᴅ.",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 ʙᴀᴄᴋ", callback_data="owner_menu")]
        ])
    )

# ============================================
# 📩 MESSAGE HANDLERS (FOR OWNER COMMANDS)
# ============================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    
    if uid not in OWNER_IDS:
        return
    
    # Handle broadcast
    if context.user_data.get('awaiting_broadcast'):
        context.user_data['awaiting_broadcast'] = False
        message = update.message
        
        await message.reply_text("📤 <b>ʙʀᴏᴀᴅᴄᴀsᴛɪɴɢ...</b>", parse_mode=ParseMode.HTML)
        
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
            f"""{stylish_banner("✅ ʙʀᴏᴀᴅᴄᴀsᴛ ᴄᴏᴍᴘʟᴇᴛᴇ")}

┣ 📤 <b>sᴇɴᴛ:</b> <code>{sent}</code>
┣ ❌ <b>ꜰᴀɪʟᴇᴅ:</b> <code>{failed}</code>
┗━━━━━━━━━━━━━━━━━━━━━┛""",
            parse_mode=ParseMode.HTML
        )
        return
    
    # Handle token add - BOT KO ONLINE KARO
    if context.user_data.get('awaiting_token'):
        context.user_data['awaiting_token'] = False
        token = update.message.text.strip()
        
        # Validate token format
        if not re.match(r'^\d+:[A-Za-z0-9_-]+$', token):
            await update.message.reply_text("❌ <b>ɪɴᴠᴀʟɪᴅ ᴛᴏᴋᴇɴ ꜰᴏʀᴍᴀᴛ!</b>")
            return
        
        # Check if already exists
        tokens = get_connected_tokens()
        if token in tokens:
            await update.message.reply_text("❌ <b>ᴛᴏᴋᴇɴ ᴀʟʀᴇᴀᴅʏ ᴄᴏɴɴᴇᴄᴛᴇᴅ!</b>")
            return
        
        # Validate and get bot info, then START THE BOT
        try:
            from telegram import Bot
            test_bot = Bot(token)
            bot_info = await test_bot.get_me()
            bot_name = bot_info.username
            
            # Save token
            add_connected_token(token, uid, bot_name)
            log_admin("add_token", uid, f"Bot: @{bot_name}")
            
            # 🔥 START THE CONNECTED BOT
            await start_connected_bot(token, bot_name)
            
            await update.message.reply_text(
                f"""{stylish_banner("✅ ʙᴏᴛ ᴏɴʟɪɴᴇ")}

┣ 🤖 <b>ʙᴏᴛ:</b> @{bot_name}
┣ 🔑 <b>sᴛᴀᴛᴜs:</b> <code>ᴏɴʟɪɴᴇ</code>
┣ ⏰ <b>ᴄᴏɴɴᴇᴄᴛᴇᴅ:</b> {datetime.now().strftime('%H:%M:%S')}

{box_text("✅ ʙᴏᴛ ɪs ɴᴏᴡ ʟɪᴠᴇ ᴀɴᴅ ᴡᴏʀᴋɪɴɢ!")}""",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            await update.message.reply_text(f"❌ <b>ɪɴᴠᴀʟɪᴅ ᴛᴏᴋᴇɴ!</b>\nᴇʀʀᴏʀ: {str(e)}")
        return

async def start_connected_bot(token, bot_username):
    """Start a connected bot with same functionality"""
    try:
        app = Application.builder().token(token).build()
        
        # Same handlers as main bot
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("cancel", cancel_cmd))
        
        # Message handler
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        # Callbacks
        app.add_handler(CallbackQueryHandler(verify_cb, pattern="^verify$"))
        app.add_handler(CallbackQueryHandler(getmail_cb, pattern="^getmail$"))
        app.add_handler(CallbackQueryHandler(inbox_cb, pattern="^inbox$"))
        app.add_handler(CallbackQueryHandler(profile_cb, pattern="^profile$"))
        app.add_handler(CallbackQueryHandler(lambda u, c: show_user_menu(u, c), pattern="^user_menu$"))
        app.add_handler(CallbackQueryHandler(lambda u, c: show_main_menu(u, c, edit=True), pattern="^main_menu$"))
        
        # Owner callbacks
        app.add_handler(CallbackQueryHandler(owner_menu_cb, pattern="^owner_menu$"))
        app.add_handler(CallbackQueryHandler(broadcast_cb, pattern="^broadcast$"))
        app.add_handler(CallbackQueryHandler(addtoken_cb, pattern="^addtoken$"))
        app.add_handler(CallbackQueryHandler(tokenlist_cb, pattern="^tokenlist$"))
        app.add_handler(CallbackQueryHandler(stats_cb, pattern="^stats$"))
        app.add_handler(CallbackQueryHandler(clear_tokens_cb, pattern="^clear_tokens$"))
        
        # Start in background
        asyncio.create_task(app.run_polling())
        print(f"🤖 Connected bot @{bot_username} is now ONLINE!")
        
    except Exception as e:
        print(f"❌ Failed to start connected bot: {e}")

async def show_user_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user menu"""
    query = update.callback_query
    await query.edit_message_text(
        f"""
{stylish_banner("ᴜsᴇʀ ᴍᴇɴᴜ")}

┣ 📧 <b>ɢᴇᴛ ᴛᴇᴍᴘ ᴍᴀɪʟ</b> - ꜰʀᴇᴇ ᴜɴʟɪᴍɪᴛᴇᴅ
┣ 📨 <b>ᴄʜᴇᴄᴋ ɪɴʙᴏx</b> - ᴠɪᴇᴡ ᴏᴛᴘs
┣ 👤 <b>ᴍʏ ᴘʀᴏꜰɪʟᴇ</b> - ʏᴏᴜʀ ɪɴꜰᴏ

{box_text("💯 100% ꜰʀᴇᴇ - ɴᴏ ʟɪᴍɪᴛs!")}""",
        parse_mode=ParseMode.HTML,
        reply_markup=user_menu_kb()
    )

async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    is_owner = update.effective_user.id in OWNER_IDS
    await update.message.reply_text(
        "❌ ᴄᴀɴᴄᴇʟʟᴇᴅ.",
        reply_markup=main_menu_kb(is_owner)
    )

# ============================================
# 🚀 MAIN
# ============================================

def main():
    init_files()
    
    print("🤖 Cyber Hacker Bot - Starting...")
    print(f"👑 Owners: {OWNER_IDS}")
    print("📁 File-based storage initialized")
    print("📧 Mail.tm API integrated")
    print("💯 100% FREE system active")
    print("🤖 Connected bots system active")
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel_cmd))
    
    # Message handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Callbacks - Main
    app.add_handler(CallbackQueryHandler(verify_cb, pattern="^verify$"))
    app.add_handler(CallbackQueryHandler(getmail_cb, pattern="^getmail$"))
    app.add_handler(CallbackQueryHandler(inbox_cb, pattern="^inbox$"))
    app.add_handler(CallbackQueryHandler(profile_cb, pattern="^profile$"))
    app.add_handler(CallbackQueryHandler(show_user_menu, pattern="^user_menu$"))
    app.add_handler(CallbackQueryHandler(lambda u, c: show_main_menu(u, c, edit=True), pattern="^main_menu$|^menu$"))
    
    # Callbacks - Owner
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
