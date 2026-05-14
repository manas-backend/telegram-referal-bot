

from flask import Flask
from threading import Thread
import logging
import os
import sqlite3
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ChatJoinRequestHandler
)

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS").split(",")))
PORT = int(os.getenv("PORT", 8080))
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot ishlayapti!"
    
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

GROUP_LINK = "https://t.me/englishhshsa"

# Database yo'li - Render da /data papkasi doimiy
DB_PATH = "referral_bot.db"

# ─────────────────────────── DATABASE ───────────────────────────

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Foydalanuvchilar jadvali
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        referred_by INTEGER,
        referral_count INTEGER DEFAULT 0,
        join_date TEXT,
        is_active INTEGER DEFAULT 1,
        is_subscribed INTEGER DEFAULT 0
    )''')
    
    # Agar is_subscribed ustuni bo'lmasa, qo'shish
    try:
        c.execute("ALTER TABLE users ADD COLUMN is_subscribed INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    # Referallar bog'lanish jadvali (TO'G'RILANGAN)
    c.execute('''CREATE TABLE IF NOT EXISTS referrals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        referrer_id INTEGER,
        referred_id INTEGER,
        date TEXT
    )''')
    
    conn.commit()
    conn.close()

def add_user(user_id, username, first_name, referred_by=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
    if c.fetchone():
        conn.close()
        return False
    c.execute('''INSERT INTO users (user_id, username, first_name, referred_by, join_date)
                 VALUES (?, ?, ?, ?, ?)''',
              (user_id, username, first_name, referred_by, datetime.now().isoformat()))
    if referred_by:
        c.execute('UPDATE users SET referral_count = referral_count + 1 WHERE user_id = ?',
                  (referred_by,))
        c.execute('INSERT INTO referrals (referrer_id, referred_id, date) VALUES (?, ?, ?)',
                  (referred_by, user_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return True

def get_user_stats(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT referral_count, join_date FROM users WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    if result:
        referral_count, join_date = result
        c.execute('''SELECT u.first_name, u.username, r.date
                     FROM referrals r
                     JOIN users u ON r.referred_id = u.user_id
                     WHERE r.referrer_id = ?
                     ORDER BY r.date DESC''', (user_id,))
        referrals = c.fetchall()
        conn.close()
        return referral_count, join_date, referrals
    conn.close()
    return None, None, []

def get_top_users(limit=10):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT user_id, first_name, username, referral_count
                 FROM users WHERE is_active = 1
                 ORDER BY referral_count DESC LIMIT ?''', (limit,))
    top_users = c.fetchall()
    conn.close()
    return top_users

def get_total_stats():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM users')
    total_users = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM users WHERE referred_by IS NOT NULL')
    referred_users = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM users WHERE referral_count > 0')
    active_referrers = c.fetchone()[0]
    conn.close()
    return total_users, referred_users, active_referrers

# ─────────────────────────── HANDLERS ───────────────────────────
async def check_subscription(user_id, context):
    chat_id = "https://t.me/englishhshsa"  # kanal username
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        if member.status in ["member", "administrator", "creator"]:
            return True
    except:
        return False
    return False
    
async def join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.chat_join_request.from_user
    chat_id = update.chat_join_request.chat.id

    # kanalga avtomatik qo‘shish (approve)
    await context.bot.approve_chat_join_request(
        chat_id=chat_id,
        user_id=user.id
    )

    # userni bazaga qo‘shish
    add_user(
        user.id,
        user.username or "",
        user.first_name or "User"
    )

    # referral bonus (ixtiyoriy)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "UPDATE users SET referral_count = referral_count + 1 WHERE user_id = ?",
        (user.id,)
    )
    conn.commit()
    conn.close()


def make_main_keyboard(user_id):
    keyboard = [
        [InlineKeyboardButton("📊 Mening statistikam", callback_data='my_stats')],
        [InlineKeyboardButton("🏆 TOP reyting", callback_data='top_rating')],
        [InlineKeyboardButton("ℹ️ Yordam", callback_data='help')]
    ]
    if user_id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("👨‍💼 Admin panel", callback_data='admin_panel')])
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id

# 1. Avval DB dan tekshiramiz
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT is_subscribed FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()

    # Agar oldin tasdiqlangan bo'lsa, o'tkazib yuboramiz
    if row and row[0] == 1:
        pass
    else:
        is_joined = await check_subscription(user_id, context)

        if not is_joined:
            keyboard = [
                [InlineKeyboardButton("📢 Kanalga obuna bo'lish", url=GROUP_LINK)],
                [InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub")]
            ]
            await update.message.reply_text(
                "❌ Botdan foydalanish uchun kanalga obuna bo'ling!",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

        # Obuna bo'lgan bo'lsa, DB ga yozamiz (fayl mavjud bo'lsa)
        if row:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("UPDATE users SET is_subscribed = 1 WHERE user_id = ?", (user_id,))
            conn.commit()
            conn.close()
    
    username = user.username or ""
    first_name = user.first_name or "Foydalanuvchi"

    referred_by = None
    if context.args:
        try:
            referred_by = int(context.args[0])
            if referred_by == user_id:
                referred_by = None
        except:
            pass

    is_new = add_user(user_id, username, first_name, referred_by)

    bot_username = context.bot.username
    referral_link = f"https://t.me/{bot_username}?start={user_id}"

    if is_new and referred_by:
        salom = "✅ Siz muvaffaqiyatli ro'yxatdan o'tdingiz!\n\n"
    elif is_new:
        salom = "✅ Botga xush kelibsiz!\n\n"
    else:
        salom = "👋 Qaytganingizdan xursandmiz!\n\n"

    message = (
        f"🎉 Assalomu alaykum, <b>{first_name}</b>!\n\n"
        f"{salom}"
        f"🔗 Sizning referal linkingiz:\n"
        f"<a href=\"{referral_link}\">👉 Do'stlarga yuborish uchun bosing</a>\n\n"
        f"👥 Guruhga kirish: <a href=\"{GROUP_LINK}\">Super Olimpiada</a>\n\n"
        f"Do'stlaringizni taklif qiling va TOP reytingga chiqing! 🏆"
    )

    await update.message.reply_text(
        message,
        reply_markup=make_main_keyboard(user_id),
        parse_mode='HTML',
        disable_web_page_preview=True
    )

async def my_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    referral_count, join_date, referrals = get_user_stats(user_id)

    bot_username = context.bot.username
    referral_link = f"https://t.me/{bot_username}?start={user_id}"

    message = (
        f"📊 <b>Sizning statistikangiz</b>\n\n"
        f"👥 Taklif qilganlar: <b>{referral_count}</b> kishi\n"
        f"📅 Qo'shilgan sana: {join_date[:10]}\n\n"
        f"🔗 Referal linkingiz:\n"
        f"<a href=\"{referral_link}\">👉 Do'stlarga yuborish uchun bosing</a>\n\n"
    )

    if referrals:
        message += "<b>Taklif qilgan foydalanuvchilaringiz:</b>\n"
        for i, (name, uname, date) in enumerate(referrals[:10], 1):
            utext = f"@{uname}" if uname else ""
            message += f"{i}. {name} {utext} - {date[:10]}\n"
        if len(referrals) > 10:
            message += f"\n<i>... va yana {len(referrals) - 10} kishi</i>\n"
    else:
        message += "<i>Hali hech kimni taklif qilmadingiz</i>\n"

    keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data='back_to_menu')]]
    await query.edit_message_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML',
        disable_web_page_preview=True
    )

async def top_rating_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    top_users = get_top_users(10)
    medals = ["🥇", "🥈", "🥉"]
    message = "<b>🏆 TOP 10 REYTING</b>\n\nEng ko'p odam taklif qilganlar:\n\n"

    for i, (uid, name, uname, count) in enumerate(top_users, 1):
        medal = medals[i-1] if i <= 3 else f"{i}."
        utext = f"@{uname}" if uname else ""
        message += f"{medal} {name} {utext} — <b>{count}</b> kishi\n"

    if not top_users:
        message += "<i>Hali statistika yo'q</i>\n"

    keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data='back_to_menu')]]
    await query.edit_message_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    message = (
        "<b>ℹ️ YORDAM</b>\n\n"
        "Botdan foydalanish juda oson!\n\n"
        "1️⃣ Referal linkingizni do'stlaringizga yuboring\n"
        "2️⃣ Ular link orqali botga qo'shilishadi\n"
        "3️⃣ Har bir yangi foydalanuvchi sizning hisobingizga qo'shiladi\n"
        "4️⃣ TOP reytingda o'rningizni kuzatib boring\n\n"
        "<b>💡 Maslahat:</b> Linkni ijtimoiy tarmoqlarda ulashing!"
    )

    keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data='back_to_menu')]]
    await query.edit_message_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def admin_panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    if user_id not in ADMIN_IDS:
        await query.answer("❌ Sizda admin huquqi yo'q!", show_alert=True)
        return

    await query.answer()
    total_users, referred_users, active_referrers = get_total_stats()
    conv = (referred_users / total_users * 100) if total_users > 0 else 0

    message = (
        "<b>👨‍💼 ADMIN PANEL</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{total_users}</b>\n"
        f"🔗 Referal orqali kelganlar: <b>{referred_users}</b>\n"
        f"⭐ Faol taklif qiluvchilar: <b>{active_referrers}</b>\n\n"
        f"📊 Konversiya: <b>{conv:.1f}%</b>"
    )

    keyboard = [
        [InlineKeyboardButton("📢 Xabar yuborish", callback_data='admin_broadcast')],
        [InlineKeyboardButton("📊 Batafsil statistika", callback_data='admin_detailed_stats')],
        [InlineKeyboardButton("🔙 Orqaga", callback_data='back_to_menu')]
    ]
    await query.edit_message_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def back_to_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    bot_username = context.bot.username
    referral_link = f"https://t.me/{bot_username}?start={user.id}"

    message = (
        f"🎉 Xush kelibsiz, <b>{user.first_name}</b>!\n\n"
        f"🔗 Sizning referal linkingiz:\n"
        f"<a href=\"{referral_link}\">👉 Do'stlarga yuborish uchun bosing</a>\n\n"
        f"Do'stlaringizni taklif qiling va TOP reytingga chiqing! 🏆"
    )

    await query.edit_message_text(
        message,
        reply_markup=make_main_keyboard(user.id),
        parse_mode='HTML',
        disable_web_page_preview=True
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id # user_id ni teparoqda olib qo'yamiz

    
    if data == 'my_stats':
        await my_stats_callback(update, context)
    elif data == 'top_rating':
        await top_rating_callback(update, context)
    elif data == 'help':
        await help_callback(update, context)
    elif data == 'admin_panel':
        await admin_panel_callback(update, context)
    elif data == 'back_to_menu':
        await back_to_menu_callback(update, context)
    elif data == "check_sub":
        is_joined = await check_subscription(user_id, context)

        if not is_joined:
            await query.answer("❌ Hali obuna bo‘lmagansiz!", show_alert=True)
            return

        # Foydalanuvchi bazada bo'lmasa, qo'shib qo'yamiz
        add_user(
            user_id,
            query.from_user.username or "",
            query.from_user.first_name or "User"
        )

        # Endi bemalol statusni yangilasa bo'ladi
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "UPDATE users SET is_subscribed = 1 WHERE user_id = ?",
            (user_id,)
        )
        conn.commit()
        conn.close()

        await query.answer("✅ Obuna tasdiqlandi!")
        await back_to_menu_callback(update, context)

    elif data == 'admin_broadcast':
        await query.answer("Bu funksiya keyingi versiyada qo'shiladi", show_alert=True)
    elif data == 'admin_detailed_stats':
        await query.answer("Bu funksiya keyingi versiyada qo'shiladi", show_alert=True)

# ─────────────────────────── MAIN ───────────────────────────

def main():
    if not TOKEN:
        print("XATO: .env faylda BOT_TOKEN yo'q!")
        return

    init_db()

    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))

def main():
    if not TOKEN:
        raise Exception("BOT_TOKEN yo'q!")

    init_db()

    application = Application.builder().token(TOKEN).build()
    

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    application.add_handler(ChatJoinRequestHandler(join_request))

    print("✅ Bot polling rejimida ishga tushdi!")
    def run_flask():
        app.run(host="0.0.0.0", port=PORT)

    Thread(target=run_flask).start()

    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )

if __name__ == '__main__':
    main()

