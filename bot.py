import asyncio
import json
import os
import re
import random
import secrets
import string
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.constants import ParseMode
import aiohttp

# ============================================
# 🔧 CONFIG - YAHAN SIRF YEH 5 CHEEZEIN CHANGE KARO
# ============================================

BOT_TOKEN = "8642015132:AAEcouvdOL48gLCs1CMHvGViPGmV9BB9M0E"
OWNER_ID = 8627624927
CHANNEL_USERNAME = "@ssbugchannel"
GROUP_USERNAME = "@ssbuggroup"
YOUTUBE_LINK = "https://youtube.com/@shadowhere.460"
WHATSAPP_LINK = "https://whatsapp.com/channel/0029VbD54jxEgGfIqPaPSK24"

# ============================================
# ⚙️ MAIL.TM API CONFIG
# ============================================
MAIL_API = "https://api.mail.tm"

# ============================================
# 📁 FILE STORAGE SYSTEM (NO DATABASE!)
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

# Premium management
def is_premium(user_id):
    premium = load_json("premium.json", {})
    data = premium.get(str(user_id), {})
    if not data:
        return False
    expires = datetime.fromisoformat(data.get('expires', '2000-01-01'))
    return datetime.now() < expires

def add_premium(user_id, days=30):
    premium = load_json("premium.json", {})
    expires = datetime.now() + timedelta(days=days)
    premium[str(user_id)] = {
        "added": datetime.now().isoformat(),
        "expires": expires.isoformat(),
        "days": days
    }
    save_json("premium.json", premium)

def remove_premium(user_id):
    premium = load_json("premium.json", {})
    if str(user_id) in premium:
        del premium[str(user_id)]
        save_json("premium.json", premium)

# OTP History
def add_otp_record(user_id, data):
    history = load_json("otp_history.json", [])
    data['user_id'] = user_id
    data['id'] = secrets.token_hex(6)
    data['time'] = datetime.now().isoformat()
    history.append(data)
    if len(history) > 1000:
        history = history[-1000:]
    save_json("otp_history.json", history)

def get_user_otps(user_id, limit=5):
    history = load_json("otp_history.json", [])
    user_otps = [h for h in history if h.get('user_id') == user_id]
    return sorted(user_otps, key=lambda x: x.get('time', ''), reverse=True)[:limit]

# ============================================
# 🎨 UI & ANIMATIONS
# ============================================
GLITCH = "▓▒░█▄▀▌▐■□▪▫▬►◄▲▼◆◇○●◐◑"

def glitch_text(text):
    return "".join(random.choice(GLITCH) if random.random() > 0.9 else c for c in text)

def start_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 JOIN CHANNEL", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")],
        [InlineKeyboardButton("👥 JOIN GROUP", url=f"https://t.me/{GROUP_USERNAME.replace('@', '')}")],
        [InlineKeyboardButton("▶️ YOUTUBE", url=YOUTUBE_LINK)],
        [InlineKeyboardButton("💬 WHATSAPP", url=WHATSAPP_LINK)],
        [InlineKeyboardButton("🔐 VERIFY ACCESS", callback_data="verify")]
    ])

def menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📧 GET TEMP MAIL", callback_data="getmail")],
        [InlineKeyboardButton("📨 CHECK INBOX", callback_data="inbox")],
        [InlineKeyboardButton("👤 MY PROFILE", callback_data="profile")],
        [InlineKeyboardButton("💎 UPGRADE", callback_data="premium")]
    ])

# ============================================
# 🤖 BOT COMMANDS
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
            "daily_count": 0,
            "last_reset": datetime.now().strftime("%Y-%m-%d"),
            "email": None,
            "email_pass": None,
            "email_token": None
        })
        welcome = f"""
╔════════════════════════════════════╗
║     🔥 <b>WELCOME TO DARK MAIL</b> 🔥     ║
╚════════════════════════════════════╝

👤 <b>ID:</b> <code>{uid}</code>
📅 <b>Date:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}

⚠️ <b>COMPLETE VERIFICATION:</b>
• Join Channel
• Join Group  
• Subscribe YouTube
• Join WhatsApp

<code>🔻 Then click VERIFY 🔻</code>
"""
        await update.message.reply_text(welcome, parse_mode=ParseMode.HTML, reply_markup=start_kb())
    else:
        if user_data.get('verified'):
            await show_menu(update, context)
        else:
            await update.message.reply_text("⚠️ <b>Verify first!</b>", parse_mode=ParseMode.HTML, reply_markup=start_kb())

async def verify_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Verifying...")
    uid = query.from_user.id
    user_data = get_user(uid)
    user_data['verified'] = True
    save_user(uid, user_data)
    for text in ["⚡ BOOTING...", "🔥 CONNECTING...", "✅ ACCESS GRANTED!"]:
        await query.edit_message_text(f"<code>{glitch_text('SYSTEM')}</code>\n\n<b>{text}</b>", parse_mode=ParseMode.HTML)
        await asyncio.sleep(0.4)
    success = f"""
╔════════════════════════════════════╗
║    ✅ <b>VERIFIED - WELCOME!</b>         ║
╚════════════════════════════════════╝

🔓 <b>Status:</b> ACTIVE
🆔 <b>ID:</b> <code>{uid}</code>
📊 <b>Plan:</b> {'💎 PREMIUM' if is_premium(uid) else '🆓 FREE (3/day)'}

<code>⚡ Ready to use! ⚡</code>
"""
    await query.edit_message_text(success, parse_mode=ParseMode.HTML, reply_markup=menu_kb())

# ============================================
# 📧 MAIL.TM INTEGRATION FIXED
# ============================================

async def getmail_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Generating mail...")
    uid = query.from_user.id
    user_data = get_user(uid)
    today = datetime.now().strftime("%Y-%m-%d")
    if user_data.get('last_reset') != today:
        user_data['daily_count'] = 0
        user_data['last_reset'] = today

    if not is_premium(uid) and user_data.get('daily_count', 0) >= 3:
        await query.edit_message_text(
            "⚠️ <b>DAILY LIMIT!</b>\n\n🔒 Free: 3/day\n💎 Premium: Unlimited",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💎 UPGRADE", callback_data="premium")]])
        )
        return

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{MAIL_API}/domains") as resp:
                domains_resp = await resp.json()
                members = domains_resp.get('hydra:member', [])
                if not members:
                    raise Exception("No available domains!")
                domain = members[0]['domain']

            username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
            email = f"{username}@{domain}"
            password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))

            async with session.post(f"{MAIL_API}/accounts", json={"address": email, "password": password}) as resp:
                if resp.status != 201:
                    raise Exception("Failed to create account")

            async with session.post(f"{MAIL_API}/token", json={"address": email, "password": password}) as resp:
                token_data = await resp.json()
                token = token_data.get('token')
                if not token:
                    raise Exception("Token not received")

            user_data.update({
                'email': email,
                'email_pass': password,
                'email_token': token,
                'daily_count': user_data.get('daily_count', 0) + 1
            })
            save_user(uid, user_data)

            asyncio.create_task(poll_otp_task(uid, email, token, context.bot))

            mail_text = f"""
╔════════════════════════════════════╗
║     📧 <b>TEMP MAIL READY!</b> 📧        ║
╚════════════════════════════════════╝

📬 <b>Email:</b> <code>{email}</code>
🔑 <b>Password:</b> <code>{password}</code>
⏱ <b>Expires:</b> 15 minutes
📊 <b>Used Today:</b> {user_data['daily_count']}/{'∞' if is_premium(uid) else '3'}

<code>━━━━━━━━━━━━━━━━━━━━━</code>
⚡ OTP will appear automatically!
<code>━━━━━━━━━━━━━━━━━━━━━</code>
"""
            await query.edit_message_text(mail_text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 NEW MAIL", callback_data="getmail")],
                [InlineKeyboardButton("📨 CHECK INBOX", callback_data="inbox")],
                [InlineKeyboardButton("🔙 MENU", callback_data="menu")]
            ]))
    except Exception as e:
        await query.edit_message_text(f"❌ <b>Error:</b> <code>{str(e)}</code>\n\nTry again!", parse_mode=ParseMode.HTML)

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
                                body = detail.get('text', '')
                                otp = extract_otp(subject + " " + body)
                                add_otp_record(uid, {"from": sender, "subject": subject, "otp": otp, "body": body[:100]})
                                alert = f"""
🚨 <b>OTP RECEIVED!</b> 🚨
📧 <b>From:</b> <code>{sender}</code>
📝 <b>Subject:</b> <code>{subject}</code>
<code>━━━━━━━━━━━━━━━</code>
🔐 <b>OTP: {otp or 'Not found'}</b>
<code>━━━━━━━━━━━━━━━</code>
⏰ {datetime.now().strftime('%H:%M:%S')}
"""
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
        await bot.send_message(uid, "⏱️ <b>Email expired!</b> Use /getmail for new one.", parse_mode=ParseMode.HTML)

def extract_otp(text):
    patterns = [r'\b\d{6}\b', r'\b\d{4}\b', r'\b\d{8}\b', r'(?i)otp[:\s]+(\d+)', r'(?i)code[:\s]+(\d+)']
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(0)
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
        await query.edit_message_text("❌ No active email!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📧 GET MAIL", callback_data="getmail")]]))
        return
    otps = get_user_otps(uid, 5)
    text = f"""
╔════════════════════════════════════╗
║        📨 <b>INBOX</b> 📨               ║
╚════════════════════════════════════╝

📬 <b>Email:</b> <code>{email}</code>

<code>━━━━━━━━━━━━━━━━━━━━━</code>
"""
    if otps:
        for i, o in enumerate(otps, 1):
            text += f"\n{i}. <b>OTP:</b> <code>{o.get('otp', 'N/A')}</code> | {o.get('time', '')[11:16]}"
    else:
        text += "\n<i>Waiting for OTP...</i>"
    text += "\n<code>━━━━━━━━━━━━━━━━━━━━━</code>"
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 REFRESH", callback_data="inbox")],
        [InlineKeyboardButton("🔙 BACK", callback_data="menu")]
    ]))

async def profile_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    user_data = get_user(uid)
    prem = is_premium(uid)
    text = f"""
╔════════════════════════════════════╗
║        👤 <b>PROFILE</b> 👤              ║
╚════════════════════════════════════╝

🆔 <b>ID:</b> <code>{uid}</code>
⭐ <b>Status:</b> {'💎 PREMIUM' if prem else '🆓 FREE'}
📊 <b>Today:</b> {user_data.get('daily_count', 0)}/{'∞' if prem else '3'}

📧 <b>Email:</b> <code>{user_data.get('email') or 'None'}</code>
"""
    buttons = [[InlineKeyboardButton("🔙 BACK", callback_data="menu")]]
    if not prem:
        buttons.insert(0, [InlineKeyboardButton("💎 UPGRADE", callback_data="premium")])
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

async def premium_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    text = """
╔════════════════════════════════════╗
║      💎 <b>PREMIUM UPGRADE</b> 💎        ║
╚════════════════════════════════════╝

🆓 <b>FREE:</b> 3 OTP/day
💎 <b>PREMIUM:</b> Unlimited OTP

💰 <b>Price:</b> ₹199/month

<i>Contact @yourusername</i>
"""
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 CONTACT", url="https://t.me/yourusername")],
        [InlineKeyboardButton("🔙 BACK", callback_data="menu")]
    ]))

async def menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_menu(update, context, edit=True)

async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, edit=False):
    uid = update.effective_user.id
    text = f"""
╔════════════════════════════════════╗
║     🔥 <b>DARK MAIL - MENU</b> 🔥        ║
╚════════════════════════════════════╝

👤 <b>User:</b> <code>{uid}</code>
⏰ {datetime.now().strftime('%H:%M')}

<code>⚡ Select option ⚡</code>
"""
    if edit:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=menu_kb())
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=menu_kb())

# ============================================
# 👑 ADMIN COMMANDS
# ============================================

async def addprem_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Owner only!")
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /addprem user_id [days]")
        return
    try:
        target = int(context.args[0])
        days = int(context.args[1]) if len(context.args) > 1 else 30
        
        add_premium(target, days)
        
        await update.message.reply_text(f"✅ Premium added!\n\n👤 User: <code>{target}</code>\n⏱ Days: <code>{days}</code>", parse_mode=ParseMode.HTML)
        
        try:
            await context.bot.send_message(target, "🎉 <b>You're now PREMIUM!</b>\nEnjoy unlimited OTP!", parse_mode=ParseMode.HTML)
        except:
            pass
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def remprem_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /remprem user_id")
        return
    
    try:
        target = int(context.args[0])
        remove_premium(target)
        await update.message.reply_text(f"✅ Removed premium from <code>{target}</code>", parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"❌ {str(e)}")

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    
    users = get_all_users()
    prem = load_json("premium.json", {})
    
    active_prem = sum(1 for p in prem.values() if datetime.fromisoformat(p.get('expires', '2000-01-01')) > datetime.now())
    
    text = f"""
📊 <b>STATS</b>

👥 Users: <code>{len(users)}</code>
✅ Verified: <code>{sum(1 for u in users.values() if u.get('verified'))}</code>
💎 Premium: <code>{active_prem}</code>
"""
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

# ============================================
# 🚀 MAIN
# ============================================

def main():
    print("🤖 Dark Mail Bot Starting...")
    print("📁 File-based storage")
    print("📧 Mail.tm API integrated")
    
    # Init files
    os.makedirs(DATA_DIR, exist_ok=True)
    for f in ["users.json", "premium.json", "otp_history.json"]:
        if not os.path.exists(get_path(f)):
            save_json(f, {} if f != "otp_history.json" else [])
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addprem", addprem_cmd))
    app.add_handler(CommandHandler("remprem", remprem_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    
    # Callbacks
    app.add_handler(CallbackQueryHandler(verify_cb, pattern="^verify$"))
    app.add_handler(CallbackQueryHandler(getmail_cb, pattern="^getmail$"))
    app.add_handler(CallbackQueryHandler(inbox_cb, pattern="^inbox$"))
    app.add_handler(CallbackQueryHandler(profile_cb, pattern="^profile$"))
    app.add_handler(CallbackQueryHandler(premium_cb, pattern="^premium$"))
    app.add_handler(CallbackQueryHandler(menu_cb, pattern="^menu$"))
    
    print("✅ Bot ready!")
    app.run_polling()

if __name__ == "__main__":
    main()
