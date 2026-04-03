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

# Environment variables se lo (secure way)
# export BOT_TOKEN="your_token_here"
# export OWNER_IDS="8627624927,1234567890" (comma separated multiple owners)

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
OWNER_IDS = [int(x.strip()) for x in os.getenv("OWNER_IDS", "8627624927").split(",") if x.strip()]
CHANNEL_USERNAME = "@ssbugchannel"
GROUP_USERNAME = "@syedhacks"
YOUTUBE_LINK = "https://youtube.com/@shadowhere.460"
WHATSAPP_LINK = "https://whatsapp.com/channel/0029VbD54jxEgGfIqPaPSK24"

# Premium Prices
PRICES = {
    "weekly": {"price": 500, "days": 7, "name": "⚡ WEEKLY"},
    "monthly": {"price": 1500, "days": 30, "name": "💎 MONTHLY"},
    "yearly": {"price": 2000, "days": 365, "name": "👑 YEARLY"},
    "lifetime": {"price": 3000, "days": 99999, "name": "🔥 LIFETIME"}
}

# Referral Config
REFERRAL_POINTS_PER_INVITE = 1
POINTS_PER_EMAIL = 3

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

def init_files():
    os.makedirs(DATA_DIR, exist_ok=True)
    files = {
        "users.json": {},
        "premium.json": {},
        "otp_history.json": [],
        "tokens.json": {},  # Connected bots
        "referrals.json": {},  # Referral data
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

# Premium management
def is_premium(user_id):
    premium = load_json("premium.json", {})
    data = premium.get(str(user_id), {})
    if not data:
        return False
    expires = datetime.fromisoformat(data.get('expires', '2000-01-01'))
    return datetime.now() < expires

def get_premium_info(user_id):
    premium = load_json("premium.json", {})
    return premium.get(str(user_id), {})

def add_premium(user_id, days=30, plan_type="monthly"):
    premium = load_json("premium.json", {})
    current = premium.get(str(user_id), {})
    
    # If already premium, extend from current expiry
    if current and datetime.fromisoformat(current.get('expires', '2000-01-01')) > datetime.now():
        expires = datetime.fromisoformat(current['expires']) + timedelta(days=days)
    else:
        expires = datetime.now() + timedelta(days=days)
    
    premium[str(user_id)] = {
        "added": datetime.now().isoformat(),
        "expires": expires.isoformat(),
        "days": days,
        "plan": plan_type,
        "price": PRICES.get(plan_type, {}).get('price', 0)
    }
    save_json("premium.json", premium)

def remove_premium(user_id):
    premium = load_json("premium.json", {})
    if str(user_id) in premium:
        del premium[str(user_id)]
        save_json("premium.json", premium)

def get_all_premium():
    premium = load_json("premium.json", {})
    active = []
    for uid, data in premium.items():
        if datetime.fromisoformat(data.get('expires', '2000-01-01')) > datetime.now():
            active.append({
                "user_id": uid,
                **data
            })
    return active

# Referral System
def get_referral_code(user_id):
    # Generate unique referral code
    code = hashlib.md5(f"{user_id}_shadow".encode()).hexdigest()[:8].upper()
    return code

def get_referral_data(user_id):
    refs = load_json("referrals.json", {})
    return refs.get(str(user_id), {
        "code": get_referral_code(user_id),
        "invited_by": None,
        "invites": [],
        "points": 0,
        "total_earned": 0
    })

def save_referral_data(user_id, data):
    refs = load_json("referrals.json", {})
    refs[str(user_id)] = data
    save_json("referrals.json", refs)

def process_referral(new_user_id, ref_code):
    if not ref_code:
        return False
    
    # Find who owns this code
    all_refs = load_json("referrals.json", {})
    inviter_id = None
    
    for uid, data in all_refs.items():
        if data.get("code") == ref_code:
            inviter_id = uid
            break
    
    if not inviter_id or int(inviter_id) == new_user_id:
        return False
    
    # Update inviter
    inviter_data = get_referral_data(inviter_id)
    if new_user_id not in inviter_data["invites"]:
        inviter_data["invites"].append(new_user_id)
        inviter_data["points"] += REFERRAL_POINTS_PER_INVITE
        inviter_data["total_earned"] += REFERRAL_POINTS_PER_INVITE
        save_referral_data(inviter_id, inviter_data)
        
        # Update new user
        new_data = get_referral_data(new_user_id)
        new_data["invited_by"] = inviter_id
        save_referral_data(new_user_id, new_data)
        
        return True
    return False

def can_use_email(user_id):
    """Check if user can generate email (premium or has points)"""
    if is_premium(user_id):
        return True, "premium"
    
    ref_data = get_referral_data(user_id)
    if ref_data["points"] >= POINTS_PER_EMAIL:
        return True, "points"
    
    return False, "no_credits"

def deduct_email_credit(user_id):
    """Deduct credit after email generation"""
    if is_premium(user_id):
        return True
    
    ref_data = get_referral_data(user_id)
    if ref_data["points"] >= POINTS_PER_EMAIL:
        ref_data["points"] -= POINTS_PER_EMAIL
        save_referral_data(user_id, ref_data)
        return True
    return False

# Connected Tokens (Sub-bots)
def add_connected_token(token, added_by):
    tokens = load_json("tokens.json", {})
    tokens[token] = {
        "added_by": added_by,
        "added_at": datetime.now().isoformat(),
        "status": "active"
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
    """Check if user joined channel and group"""
    try:
        # Check channel
        channel_member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        channel_ok = channel_member.status in ['member', 'administrator', 'creator']
        
        # Check group
        group_member = await bot.get_chat_member(GROUP_USERNAME, user_id)
        group_ok = group_member.status in ['member', 'administrator', 'creator']
        
        return channel_ok and group_ok
    except Exception as e:
        print(f"Check join error: {e}")
        return False

# ============================================
# 🎨 UI & ANIMATIONS - PREMIUM DESIGN
# ============================================

def banner_text(text):
    return f"""
╔══════════════════════════════════════════╗
║  {text:^38}  ║
╚══════════════════════════════════════════╝"""

def premium_box(title, content):
    return f"""
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  ✦ {title:^26} ✦  ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
{content}"""

def glitch_effect(text):
    chars = "▓▒░█▄▀▌▐■□▪▫▬►◄▲▼◆◇○●◐◑★☆"
    return "".join(random.choice(chars) if random.random() > 0.85 else c for c in text)

def neon_text(text):
    neon = ["", "", "", ""]
    return random.choice(neon) + text

# Keyboards
def start_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📢 CHANNEL", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"),
            InlineKeyboardButton("👥 GROUP", url=f"https://t.me/{GROUP_USERNAME.replace('@', '')}")
        ],
        [
            InlineKeyboardButton("▶️ YOUTUBE", url=YOUTUBE_LINK),
            InlineKeyboardButton("💬 WHATSAPP", url=WHATSAPP_LINK)
        ],
        [InlineKeyboardButton("🔐 VERIFY ACCESS", callback_data="verify")]
    ])

def main_menu_kb(is_owner=False):
    buttons = [
        [InlineKeyboardButton("📧 GET TEMP MAIL", callback_data="getmail")],
        [InlineKeyboardButton("📨 CHECK INBOX", callback_data="inbox")],
        [InlineKeyboardButton("👤 MY PROFILE", callback_data="profile")],
        [InlineKeyboardButton("💰 MY BALANCE", callback_data="balance")],
        [InlineKeyboardButton("🔗 REFERRAL LINK", callback_data="referral")],
        [InlineKeyboardButton("💎 UPGRADE", callback_data="premium")]
    ]
    if is_owner:
        buttons.append([InlineKeyboardButton("👑 OWNER MENU", callback_data="owner_menu")])
    return InlineKeyboardMarkup(buttons)

def owner_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 BROADCAST", callback_data="broadcast")],
        [InlineKeyboardButton("➕ ADD TOKEN", callback_data="addtoken")],
        [InlineKeyboardButton("📋 TOKEN LIST", callback_data="tokenlist")],
        [InlineKeyboardButton("👥 PREMIUM LIST", callback_data="premlist")],
        [InlineKeyboardButton("📊 STATISTICS", callback_data="stats")],
        [InlineKeyboardButton("🔙 MAIN MENU", callback_data="menu")]
    ])

def premium_plans_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"⚡ WEEKLY - ₹{PRICES['weekly']['price']}", callback_data="buy_weekly")],
        [InlineKeyboardButton(f"💎 MONTHLY - ₹{PRICES['monthly']['price']}", callback_data="buy_monthly")],
        [InlineKeyboardButton(f"👑 YEARLY - ₹{PRICES['yearly']['price']}", callback_data="buy_yearly")],
        [InlineKeyboardButton(f"🔥 LIFETIME - ₹{PRICES['lifetime']['price']}", callback_data="buy_lifetime")],
        [InlineKeyboardButton("🔙 BACK", callback_data="menu")]
    ])

# ============================================
# 🤖 BOT COMMANDS
# ============================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    args = context.args
    
    # Check if referral code present
    if args and args[0].startswith("ref"):
        ref_code = args[0].replace("ref", "")
        process_referral(uid, ref_code)
    
    user_data = get_user(uid)
    
    if not user_data:
        # New user
        ref_data = get_referral_data(uid)
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
{banner_text("🔥 TEMP MAIL BY SHADOW 🔥")}

👤 <b>User:</b> <code>{uid}</code>
📅 <b>Date:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}

⚠️ <b>COMPLETE VERIFICATION:</b>
• Join Channel 📢
• Join Group 👥  
• Subscribe YouTube ▶️
• Join WhatsApp 💬

<code>🔻 Then click VERIFY 🔻</code>
"""
        await update.message.reply_photo(
            photo="https://i.postimg.cc/zX8C13Tg/header.jpg",  # Banner image URL
            caption=welcome,
            parse_mode=ParseMode.HTML,
            reply_markup=start_kb()
        )
    else:
        if user_data.get('verified'):
            await show_menu(update, context)
        else:
            await update.message.reply_text(
                "⚠️ <b>Complete verification first!</b>", 
                parse_mode=ParseMode.HTML, 
                reply_markup=start_kb()
            )

async def verify_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Checking...")
    uid = query.from_user.id
    
    # ACTUAL CHECK
    joined = await check_user_joined(context.bot, uid)
    
    if not joined:
        await query.edit_message_text(
            f"""{banner_text("❌ NOT JOINED")}

⚠️ <b>Please join all channels first:</b>
• {CHANNEL_USERNAME}
• {GROUP_USERNAME}

Then click VERIFY again.""",
            parse_mode=ParseMode.HTML,
            reply_markup=start_kb()
        )
        return
    
    # Save verified status
    user_data = get_user(uid)
    user_data['verified'] = True
    save_user(uid, user_data)
    
    # Animation
    for text in ["⚡ SYSTEM BOOT...", "🔥 CONNECTING...", "✅ ACCESS GRANTED!"]:
        await query.edit_message_text(
            f"<code>{glitch_effect('TEMP MAIL BY SHADOW')}</code>\n\n<b>{neon_text(text)}</b>", 
            parse_mode=ParseMode.HTML
        )
        await asyncio.sleep(0.5)
    
    # Success message with banner
    success = f"""
{banner_text("✅ VERIFIED SUCCESSFULLY")}

🔓 <b>Status:</b> <code>ACTIVE</code>
🆔 <b>ID:</b> <code>{uid}</code>
⭐ <b>Plan:</b> {'💎 PREMIUM' if is_premium(uid) else '🆓 FREE'}

<code>⚡ Ready to use! ⚡</code>
"""
    await query.edit_message_text(success, parse_mode=ParseMode.HTML, reply_markup=main_menu_kb(uid in OWNER_IDS))

# ============================================
# 📧 MAIL.TM INTEGRATION
# ============================================

async def getmail_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Generating...")
    uid = query.from_user.id
    
    # Check credits
    can_use, credit_type = can_use_email(uid)
    if not can_use:
        await query.edit_message_text(
            f"""{banner_text("⚠️ NO CREDITS")}

❌ <b>You have no credits!</b>

💡 <b>Earn credits:</b>
• Share referral link
• 3 invites = 1 Email

Or upgrade to Premium 💎""",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 GET REFERRAL LINK", callback_data="referral")],
                [InlineKeyboardButton("💎 UPGRADE", callback_data="premium")]
            ])
        )
        return
    
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

            # Deduct credit if not premium
            if not is_premium(uid):
                deduct_email_credit(uid)
            
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

            ref_data = get_referral_data(uid)
            
            mail_text = f"""
{banner_text("📧 TEMP MAIL READY")}

📬 <b>Email:</b> <code>{email}</code>
🔑 <b>Password:</b> <code>{password}</code>
⏱ <b>Expires:</b> 15 minutes

💰 <b>Balance:</b> {ref_data['points']} points
⭐ <b>Status:</b> {'💎 PREMIUM' if is_premium(uid) else 'FREE'}

<code>━━━━━━━━━━━━━━━━━━━━━</code>
⚡ <b>OTP will appear automatically!</b>
<code>━━━━━━━━━━━━━━━━━━━━━</code>
"""
            await query.edit_message_text(
                mail_text, 
                parse_mode=ParseMode.HTML, 
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 NEW MAIL", callback_data="getmail")],
                    [InlineKeyboardButton("📨 CHECK INBOX", callback_data="inbox")],
                    [InlineKeyboardButton("🔙 MENU", callback_data="menu")]
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
                                
                                # IMPROVED OTP EXTRACTION
                                otp = extract_otp(subject + " " + body)
                                
                                add_otp_record(uid, {
                                    "from": sender, 
                                    "subject": subject, 
                                    "otp": otp, 
                                    "body": body[:200]
                                })
                                
                                alert = f"""
🚨 {banner_text("OTP RECEIVED")} 🚨

📧 <b>From:</b> <code>{sender}</code>
📝 <b>Subject:</b> <code>{subject}</code>

<code>━━━━━━━━━━━━━━━━━━━━━</code>
🔐 <b>OTP CODE:</b>
<code>{otp or 'Not found in email'}</code>
<code>━━━━━━━━━━━━━━━━━━━━━</code>

⏰ <b>Time:</b> {datetime.now().strftime('%H:%M:%S')}
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
            "⏱️ <b>Email expired!</b>\nUse /start to get new one.", 
            parse_mode=ParseMode.HTML
        )

def extract_otp(text):
    """Extract OTP from text - FIXED VERSION"""
    if not text:
        return None
    
    # Clean text
    text = text.replace('\n', ' ').replace('\r', ' ')
    
    # Patterns to try (in order of priority)
    patterns = [
        # Format: XXX-XXX or XXX XXX
        r'(\d{3}[-\s]\d{3})',
        # Format: XXXXXX (6 digits)
        r'\b(\d{6})\b',
        # Format: XXXX (4 digits)  
        r'\b(\d{4})\b',
        # Format: XXXXXXXX (8 digits)
        r'\b(\d{8})\b',
        # Format: "OTP is 123456"
        r'(?i)otp[:\s]+(\d{3}[-\s]?\d{3})',
        r'(?i)otp[:\s]+(\d+)',
        # Format: "code is 123-456"
        r'(?i)code[:\s]+(\d{3}[-\s]\d{3})',
        r'(?i)code[:\s]+(\d+)',
        # Format: "verification code: 123456"
        r'(?i)verification[:\s]+(\d+)',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            if match:
                # Clean and return
                otp = match.strip()
                # If it's format like "678-644", keep it as is
                # If it's just digits, return as is
                return otp
    
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
            "❌ No active email!\nGet one first.", 
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📧 GET MAIL", callback_data="getmail")]
            ])
        )
        return
    
    otps = get_user_otps(uid, 5)
    text = f"""
{banner_text("📨 INBOX")}

📬 <b>Email:</b> <code>{email}</code>

<code>━━━━━━━━━━━━━━━━━━━━━</code>
"""
    if otps:
        for i, o in enumerate(otps, 1):
            otp_disp = o.get('otp', 'N/A') or 'N/A'
            time_disp = o.get('time', '')
            if time_disp:
                time_disp = time_disp[11:16]
            text += f"\n{i}. <b>OTP:</b> <code>{otp_disp}</code> | ⏰ {time_disp}"
    else:
        text += "\n<i>Waiting for OTP...</i>"
    
    text += "\n<code>━━━━━━━━━━━━━━━━━━━━━</code>"
    
    await query.edit_message_text(
        text, 
        parse_mode=ParseMode.HTML, 
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 REFRESH", callback_data="inbox")],
            [InlineKeyboardButton("🔙 BACK", callback_data="menu")]
        ])
    )

async def profile_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    user_data = get_user(uid)
    prem = is_premium(uid)
    ref_data = get_referral_data(uid)
    
    prem_info = get_premium_info(uid)
    plan_text = ""
    if prem and prem_info:
        expires = datetime.fromisoformat(prem_info['expires'])
        days_left = (expires - datetime.now()).days
        plan_text = f"\n📅 <b>Expires:</b> {expires.strftime('%Y-%m-%d')} ({days_left} days)"
    
    text = f"""
{banner_text("👤 PROFILE")}

🆔 <b>ID:</b> <code>{uid}</code>
👤 <b>Name:</b> {user_data.get('name', 'N/A')}
⭐ <b>Status:</b> {'💎 PREMIUM' if prem else '🆓 FREE'}{plan_text}

💰 <b>Points:</b> {ref_data['points']}
👥 <b>Invited:</b> {len(ref_data['invites'])} users
📧 <b>Active Email:</b> <code>{user_data.get('email') or 'None'}</code>
"""
    buttons = [[InlineKeyboardButton("🔙 BACK", callback_data="menu")]]
    if not prem:
        buttons.insert(0, [InlineKeyboardButton("💎 UPGRADE", callback_data="premium")])
    
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

async def balance_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    ref_data = get_referral_data(uid)
    
    can_generate = ref_data['points'] // POINTS_PER_EMAIL
    
    text = f"""
{banner_text("💰 MY BALANCE")}

💎 <b>Current Points:</b> {ref_data['points']}
📧 <b>Emails Available:</b> {can_generate}

📊 <b>Earning Rate:</b>
• 1 Invite = {REFERRAL_POINTS_PER_INVITE} point
• {POINTS_PER_EMAIL} Points = 1 Email

👥 <b>Total Invited:</b> {len(ref_data['invites'])} users
💵 <b>Total Earned:</b> {ref_data['total_earned']} points

<code>━━━━━━━━━━━━━━━━━━━━━</code>
💡 <b>Tip:</b> Share your referral link to earn more!
"""
    await query.edit_message_text(
        text, 
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 GET REFERRAL LINK", callback_data="referral")],
            [InlineKeyboardButton("🔙 BACK", callback_data="menu")]
        ])
    )

async def referral_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    ref_data = get_referral_data(uid)
    bot_username = context.bot.username
    
    ref_link = f"https://t.me/{bot_username}?start=ref{ref_data['code']}"
    
    text = f"""
{banner_text("🔗 REFERRAL PROGRAM")}

📢 <b>Your Referral Code:</b> <code>{ref_data['code']}</code>

🔗 <b>Your Link:</b>
<code>{ref_link}</code>

📊 <b>Stats:</b>
• Invited: {len(ref_data['invites'])} users
• Points: {ref_data['points']}
• Emails Available: {ref_data['points'] // POINTS_PER_EMAIL}

🎁 <b>Rewards:</b>
• {REFERRAL_POINTS_PER_INVITE} point per invite
• {POINTS_PER_EMAIL} points = 1 Temp Mail

<code>━━━━━━━━━━━━━━━━━━━━━</code>
📱 <b>Share this link with friends!</b>
"""
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 SHARE LINK", url=f"https://t.me/share/url?url={ref_link}&text=Join%20this%20awesome%20Temp%20Mail%20Bot!")],
            [InlineKeyboardButton("🔙 BACK", callback_data="menu")]
        ])
    )

async def premium_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    text = f"""
{banner_text("💎 PREMIUM PLANS")}

🆓 <b>FREE:</b> Earn via referrals only
💎 <b>PREMIUM:</b> Unlimited emails!

💰 <b>Choose Your Plan:</b>

⚡ <b>WEEKLY</b> - ₹{PRICES['weekly']['price']}
   └ 7 Days Access

💎 <b>MONTHLY</b> - ₹{PRICES['monthly']['price']}
   └ 30 Days Access

👑 <b>YEARLY</b> - ₹{PRICES['yearly']['price']}
   └ 365 Days Access

🔥 <b>LIFETIME</b> - ₹{PRICES['lifetime']['price']}
   └ Forever Access!

<code>━━━━━━━━━━━━━━━━━━━━━</code>
📞 <b>Contact to buy:</b> @yourusername
"""
    await query.edit_message_text(
        text, 
        parse_mode=ParseMode.HTML, 
        reply_markup=premium_plans_kb()
    )

async def menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_menu(update, context, edit=True)

async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, edit=False):
    uid = update.effective_user.id
    is_owner = uid in OWNER_IDS
    
    text = f"""
{banner_text("🔥 TEMP MAIL BY SHADOW 🔥")}

👤 <b>User:</b> <code>{uid}</code>
⏰ <b>Time:</b> {datetime.now().strftime('%H:%M:%S')}

<code>⚡ Select an option below ⚡</code>
"""
    if edit:
        await update.callback_query.edit_message_text(
            text, 
            parse_mode=ParseMode.HTML, 
            reply_markup=main_menu_kb(is_owner)
        )
    else:
        await update.message.reply_text(
            text, 
            parse_mode=ParseMode.HTML, 
            reply_markup=main_menu_kb(is_owner)
        )

# ============================================
# 👑 OWNER MENU & COMMANDS
# ============================================

async def owner_menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    
    if uid not in OWNER_IDS:
        await query.answer("❌ Owner only!", show_alert=True)
        return
    
    text = f"""
{banner_text("👑 OWNER MENU")}

🆔 <b>Admin ID:</b> <code>{uid}</code>
⏰ <b>Time:</b> {datetime.now().strftime('%H:%M:%S')}

<code>⚡ Select admin action ⚡</code>
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
        await query.answer("❌ Owner only!", show_alert=True)
        return
    
    await query.edit_message_text(
        f"""{banner_text("📢 BROADCAST")}

📝 <b>Send your message now</b>
(Type /cancel to abort)

📊 <b>Target:</b> All users
⏰ <b>Time:</b> {datetime.now().strftime('%H:%M:%S')}""",
        parse_mode=ParseMode.HTML
    )
    context.user_data['awaiting_broadcast'] = True

async def addtoken_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    
    if uid not in OWNER_IDS:
        await query.answer("❌ Owner only!", show_alert=True)
        return
    
    await query.edit_message_text(
        f"""{banner_text("➕ ADD TOKEN")}

📝 <b>Send bot token to connect</b>
(Type /cancel to abort)

<code>Format: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz</code>

⚠️ <b>Warning:</b> Token will be validated!""",
        parse_mode=ParseMode.HTML
    )
    context.user_data['awaiting_token'] = True

async def tokenlist_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    
    if uid not in OWNER_IDS:
        await query.answer("❌ Owner only!", show_alert=True)
        return
    
    tokens = get_connected_tokens()
    
    if not tokens:
        text = f"""{banner_text("📋 TOKEN LIST")}
        
<i>No connected bots found.</i>"""
    else:
        text = f"""{banner_text("📋 CONNECTED BOTS")}

<b>Total:</b> {len(tokens)} bots

"""
        for i, (token, data) in enumerate(tokens.items(), 1):
            short_token = token[:15] + "..." if len(token) > 15 else token
            added = data.get('added_at', 'Unknown')[:10]
            text += f"{i}. <code>{short_token}</code>\n   📅 {added}\n\n"
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🗑 CLEAR ALL", callback_data="clear_tokens")],
            [InlineKeyboardButton("🔙 BACK", callback_data="owner_menu")]
        ])
    )

async def premlist_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    
    if uid not in OWNER_IDS:
        await query.answer("❌ Owner only!", show_alert=True)
        return
    
    premium_users = get_all_premium()
    
    if not premium_users:
        text = f"""{banner_text("👥 PREMIUM LIST")}
        
<i>No premium users found.</i>"""
    else:
        text = f"""{banner_text("👥 PREMIUM USERS")}

<b>Total Active:</b> {len(premium_users)}

"""
        for i, user in enumerate(premium_users[:20], 1):  # Show top 20
            expires = datetime.fromisoformat(user['expires'])
            days_left = (expires - datetime.now()).days
            text += f"{i}. <code>{user['user_id']}</code> | {user.get('plan', 'N/A')} | {days_left}d\n"
        
        if len(premium_users) > 20:
            text += f"\n<i>...and {len(premium_users) - 20} more</i>"
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 BACK", callback_data="owner_menu")]
        ])
    )

async def stats_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    
    if uid not in OWNER_IDS:
        await query.answer("❌ Owner only!", show_alert=True)
        return
    
    users = get_all_users()
    premium = get_all_premium()
    tokens = get_connected_tokens()
    
    verified = sum(1 for u in users.values() if u.get('verified'))
    
    text = f"""
{banner_text("📊 STATISTICS")}

👥 <b>Total Users:</b> <code>{len(users)}</code>
✅ <b>Verified:</b> <code>{verified}</code>
💎 <b>Premium:</b> <code>{len(premium)}</code>
🤖 <b>Connected Bots:</b> <code>{len(tokens)}</code>

📅 <b>Date:</b> {datetime.now().strftime('%Y-%m-%d')}
"""
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 BACK", callback_data="owner_menu")]
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
                await asyncio.sleep(0.1)  # Rate limit
            except (Forbidden, BadRequest):
                failed += 1
        
        log_admin("broadcast", uid, f"Sent: {sent}, Failed: {failed}")
        await message.reply_text(
            f"""{banner_text("✅ BROADCAST COMPLETE")}

📤 <b>Sent:</b> <code>{sent}</code>
❌ <b>Failed:</b> <code>{failed}</code>""",
            parse_mode=ParseMode.HTML
        )
        return
    
    # Handle token add
    if context.user_data.get('awaiting_token'):
        context.user_data['awaiting_token'] = False
        token = update.message.text.strip()
        
        # Validate token format
        if not re.match(r'^\d+:[A-Za-z0-9_-]+$', token):
            await update.message.reply_text("❌ <b>Invalid token format!</b>")
            return
        
        # Check if already exists
        tokens = get_connected_tokens()
        if token in tokens:
            await update.message.reply_text("❌ <b>Token already connected!</b>")
            return
        
        # Try to validate by getting bot info
        try:
            from telegram import Bot
            test_bot = Bot(token)
            bot_info = await test_bot.get_me()
            bot_name = bot_info.username
            
            add_connected_token(token, uid)
            log_admin("add_token", uid, f"Bot: @{bot_name}")
            
            await update.message.reply_text(
                f"""{banner_text("✅ TOKEN ADDED")}

🤖 <b>Bot:</b> @{bot_name}
🔑 <b>Token:</b> <code>{token[:20]}...</code>

✅ Connected successfully!""",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            await update.message.reply_text(f"❌ <b>Invalid token!</b>\nError: {str(e)}")
        return

# ============================================
# 🛠️ ADMIN COMMANDS
# ============================================

async def addprem_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in OWNER_IDS:
        await update.message.reply_text("❌ Owner only!")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /addprem user_id plan_type\n\n"
            "Plans: weekly, monthly, yearly, lifetime"
        )
        return
    
    try:
        target = int(context.args[0])
        plan = context.args[1].lower()
        
        if plan not in PRICES:
            await update.message.reply_text(f"❌ Invalid plan! Use: weekly, monthly, yearly, lifetime")
            return
        
        days = PRICES[plan]['days']
        add_premium(target, days, plan)
        
        await update.message.reply_text(
            f"""{banner_text("✅ PREMIUM ADDED")}

👤 <b>User:</b> <code>{target}</code>
📦 <b>Plan:</b> {PRICES[plan]['name']}
⏱ <b>Days:</b> <code>{days}</code>
💰 <b>Price:</b> ₹{PRICES[plan]['price']}""",
            parse_mode=ParseMode.HTML
        )
        
        try:
            await context.bot.send_message(
                target, 
                f"""🎉 {banner_text("PREMIUM ACTIVATED")}

⭐ <b>Plan:</b> {PRICES[plan]['name']}
⏱ <b>Duration:</b> {days} days

Enjoy unlimited emails! 💎""",
                parse_mode=ParseMode.HTML
            )
        except:
            pass
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def remprem_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in OWNER_IDS:
        await update.message.reply_text("❌ Owner only!")
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

async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Cancelled.", reply_markup=main_menu_kb(update.effective_user.id in OWNER_IDS))

# ============================================
# 🚀 MAIN
# ============================================

def main():
    init_files()
    
    print("🤖 Temp Mail by Shadow - Starting...")
    print(f"👑 Owners: {OWNER_IDS}")
    print("📁 File-based storage initialized")
    print("📧 Mail.tm API integrated")
    print("💎 Premium system active")
    print("🔗 Referral system active")
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addprem", addprem_cmd))
    app.add_handler(CommandHandler("remprem", remprem_cmd))
    app.add_handler(CommandHandler("cancel", cancel_cmd))
    
    # Message handler (for broadcast/token)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Callbacks - Main
    app.add_handler(CallbackQueryHandler(verify_cb, pattern="^verify$"))
    app.add_handler(CallbackQueryHandler(getmail_cb, pattern="^getmail$"))
    app.add_handler(CallbackQueryHandler(inbox_cb, pattern="^inbox$"))
    app.add_handler(CallbackQueryHandler(profile_cb, pattern="^profile$"))
    app.add_handler(CallbackQueryHandler(balance_cb, pattern="^balance$"))
    app.add_handler(CallbackQueryHandler(referral_cb, pattern="^referral$"))
    app.add_handler(CallbackQueryHandler(premium_cb, pattern="^premium$"))
    app.add_handler(CallbackQueryHandler(menu_cb, pattern="^menu$"))
    
    # Callbacks - Owner
    app.add_handler(CallbackQueryHandler(owner_menu_cb, pattern="^owner_menu$"))
    app.add_handler(CallbackQueryHandler(broadcast_cb, pattern="^broadcast$"))
    app.add_handler(CallbackQueryHandler(addtoken_cb, pattern="^addtoken$"))
    app.add_handler(CallbackQueryHandler(tokenlist_cb, pattern="^tokenlist$"))
    app.add_handler(CallbackQueryHandler(premlist_cb, pattern="^premlist$"))
    app.add_handler(CallbackQueryHandler(stats_cb, pattern="^stats$"))
    
    # Premium plans
    app.add_handler(CallbackQueryHandler(lambda u,c: premium_cb(u,c), pattern="^buy_"))
    
    print("✅ Bot ready!")
    app.run_polling()

if __name__ == "__main__":
    main()
