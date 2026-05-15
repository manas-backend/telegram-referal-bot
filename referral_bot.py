import asyncio
import logging
import os
from datetime import datetime
import aiosqlite
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiohttp import web  # Render uchun veb-server

# ============================================================
#  SOZLAMALAR — Render Environment Variables orqali ishlaydi
# ============================================================
BOT_TOKEN    = os.getenv("BOT_TOKEN")
CHANNEL_ID   = os.getenv("CHANNEL_ID", "@super_olimpiada")
CHANNEL_LINK = os.getenv("CHANNEL_LINK", "https://t.me/super_olimpiada")

# Admin IDs ni matndan raqamlar ro'yxatiga o'tkazish
admin_env    = os.getenv("ADMIN_IDS")
ADMIN_IDS    = [int(x.strip()) for x in admin_env.split(",") if x.strip().isdigit()]

# Render diski ulangan bo'lsa /data/bot.db, aks holda shunchaki bot.db
if os.path.exists("/data"):
    DB_NAME = "/data/bot.db"
else:
    DB_NAME = "bot.db"

PORT = int(os.getenv("PORT", 8080))
# ============================================================

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

router = Router()

# ─────────────────────────────────────────────
#  DATABASE FUNKSIYALARI (O'ZGARISHSIZ QOLDI)
# ─────────────────────────────────────────────

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id        INTEGER PRIMARY KEY,
                username       TEXT,
                full_name      TEXT,
                referred_by    INTEGER,
                referral_count INTEGER DEFAULT 0,
                joined_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER,
                referred_id INTEGER,
                joined_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

async def get_user(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)) as c:
            return await c.fetchone()

async def add_user(user_id, username, full_name, referred_by=None):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username, full_name, referred_by) VALUES (?,?,?,?)",
            (user_id, username or "", full_name, referred_by)
        )
        await db.commit()

async def add_referral(referrer_id, referred_id):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT id FROM referrals WHERE referred_id=?", (referred_id,)) as c:
            if await c.fetchone():
                return False
        await db.execute("INSERT INTO referrals (referrer_id, referred_id) VALUES (?,?)", (referrer_id, referred_id))
        await db.execute("UPDATE users SET referral_count = referral_count+1 WHERE user_id=?", (referrer_id,))
        await db.commit()
        return True

async def get_top_users(limit=10):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT user_id, full_name, username, referral_count FROM users ORDER BY referral_count DESC LIMIT ?",
            (limit,)
        ) as c:
            return await c.fetchall()

async def get_user_referrals(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT u.full_name, u.username, r.joined_at
            FROM referrals r JOIN users u ON u.user_id=r.referred_id
            WHERE r.referrer_id=? ORDER BY r.joined_at DESC
        """, (user_id,)) as c:
            return await c.fetchall()

async def get_total_users():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as c:
            return (await c.fetchone())[0]

async def search_user(query):
    query = query.strip().lstrip("@")
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        if query.isdigit():
            async with db.execute("SELECT * FROM users WHERE user_id=?", (int(query),)) as c:
                return await c.fetchall()
        async with db.execute("SELECT * FROM users WHERE username LIKE ?", (f"%{query}%",)) as c:
            return await c.fetchall()

async def get_all_user_ids():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id FROM users") as c:
            return [r[0] for r in await c.fetchall()]

# ─────────────────────────────────────────────
#  KLAVIATURALAR VA HANDLERLAR (O'ZGARISHSIZ)
# ─────────────────────────────────────────────

def main_kb(user_id):
    rows = [
        [KeyboardButton(text="🔗 Referal havolam"), KeyboardButton(text="📊 Statistikam")],
        [KeyboardButton(text="🏆 Top reyting"),     KeyboardButton(text="❓ Yordam")],
    ]
    if user_id in ADMIN_IDS:
        rows.append([KeyboardButton(text="⚙️ Admin panel")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)

def sub_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Kanalga obuna bo'lish", url=CHANNEL_LINK)],
        [InlineKeyboardButton(text="✅ Obuna bo'ldim", callback_data="check_sub")],
    ])

def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📨 Hammaga xabar", callback_data="broadcast")],
        [InlineKeyboardButton(text="🔍 Foydalanuvchi qidirish", callback_data="search")],
        [InlineKeyboardButton(text="📈 Statistika", callback_data="stats")],
    ])

def cancel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel")]
    ])

async def is_subscribed(bot: Bot, user_id):
    try:
        m = await bot.get_chat_member(CHANNEL_ID, user_id)
        return m.status not in ("left", "kicked", "restricted")
    except Exception:
        return False

class St(StatesGroup):
    broadcast = State()
    search    = State()

@router.message(CommandStart())
async def cmd_start(msg: Message, bot: Bot):
    user = msg.from_user
    args = msg.text.split()
    referred_by = None

    if len(args) > 1:
        try:
            ref = int(args[1])
            if ref != user.id:
                referred_by = ref
        except ValueError:
            pass

    existing = await get_user(user.id)
    if not existing:
        await add_user(user.id, user.username, user.full_name, referred_by)

    if not await is_subscribed(bot, user.id):
        await msg.answer(
            f"👋 Salom, <b>{user.full_name}</b>!\n\n"
            "📢 Botdan foydalanish uchun avval kanalga obuna bo'ling:",
            parse_mode="HTML", reply_markup=sub_kb()
        )
        return

    if referred_by and not existing:
        added = await add_referral(referred_by, user.id)
        if added:
            try:
                await bot.send_message(
                    referred_by,
                    f"🎉 <b>{user.full_name}</b> (@{user.username or '—'}) siz orqali qo'shildi!",
                    parse_mode="HTML"
                )
            except Exception:
                pass

    await msg.answer(
        f"✅ Xush kelibsiz, <b>{user.full_name}</b>!",
        parse_mode="HTML", reply_markup=main_kb(user.id)
    )

@router.callback_query(F.data == "check_sub")
async def check_sub(call: CallbackQuery, bot: Bot):
    user = call.from_user
    if not await is_subscribed(bot, user.id):
        await call.answer("❌ Hali obuna bo'lmagansiz!", show_alert=True)
        return

    user_data = await get_user(user.id)
    if user_data and user_data["referred_by"]:
        added = await add_referral(user_data["referred_by"], user.id)
        if added:
            try:
                await bot.send_message(
                    user_data["referred_by"],
                    f"🎉 <b>{user.full_name}</b> (@{user.username or '—'}) siz orqali qo'shildi!",
                    parse_mode="HTML"
                )
            except Exception:
                pass

    await call.message.edit_text(f"✅ Obuna tasdiqlandi! Xush kelibsiz, <b>{user.full_name}</b>!", parse_mode="HTML")
    await bot.send_message(user.id, "Menyudan birini tanlang:", reply_markup=main_kb(user.id))

@router.message(F.text == "🔗 Referal havolam")
async def my_ref(msg: Message, bot: Bot):
    if not await is_subscribed(bot, msg.from_user.id):
        await msg.answer("❌ Avval kanalga obuna bo'ling!", reply_markup=sub_kb())
        return
    
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start={msg.from_user.id}"
    user_data = await get_user(msg.from_user.id)
    count = user_data["referral_count"] if user_data else 0
    
    text = (
        f"🔗 <b>Sizning referal havolangiz:</b>\n\n"
        f"{link}\n"
        f"☝️ <i>Nusxa olish uchun ustiga bosing:</i>\n\n"
        f"👥 Siz orqali qo'shilganlar: <b>{count} kishi</b>\n\n"
        f"💡 Havolani do'stlaringizga yuboring va reytingda yuqoriga chiqing!\n\n"
        f"📢 <b>Guruhga kirish:</b> https://t.me/super_olimpiada"
    )

    await msg.answer(text=text, parse_mode="HTML", disable_web_page_preview=True)

@router.message(F.text == "📊 Statistikam")
async def my_stats(msg: Message, bot: Bot):
    if not await is_subscribed(bot, msg.from_user.id):
        await msg.answer("❌ Avval kanalga obuna bo'ling!", reply_markup=sub_kb())
        return
    user_data = await get_user(msg.from_user.id)
    referrals = await get_user_referrals(msg.from_user.id)
    count = user_data["referral_count"] if user_data else 0
    joined = str(user_data["joined_at"])[:10] if user_data else "—"

    text = (
        f"📊 <b>Sizning statistikangiz</b>\n\n"
        f"👤 Ism: <b>{msg.from_user.full_name}</b>\n"
        f"🆔 ID: <code>{msg.from_user.id}</code>\n"
        f"📅 Qo'shilgan: <b>{joined}</b>\n"
        f"👥 Taklif qilganlar: <b>{count} kishi</b>\n"
    )
    if referrals:
        text += "\n<b>So'nggi taklif qilinganlar:</b>\n"
        for i, r in enumerate(referrals[:5], 1):
            text += f"  {i}. {r['full_name'] or 'Nomalum'} — {str(r['joined_at'])[:10]}\n"

    await msg.answer(text, parse_mode="HTML")

@router.message(F.text == "🏆 Top reyting")
async def top(msg: Message, bot: Bot):
    if not await is_subscribed(bot, msg.from_user.id):
        await msg.answer("❌ Avval kanalga obuna bo'ling!", reply_markup=sub_kb())
        return
    users = await get_top_users(10)
    if not users:
        await msg.answer("Hozircha ma'lumot yo'q.")
        return
    medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    text = "🏆 <b>TOP 10 — Ko'proq odam taklif qilganlar</b>\n\n"
    for i, u in enumerate(users):
        uname = f"@{u['username']}" if u["username"] else ""
        text += f"{medals[i]} <b>{u['full_name'] or 'Nomalum'}</b> {uname} — <b>{u['referral_count']}</b> kishi\n"
    await msg.answer(text, parse_mode="HTML")

@router.message(F.text == "❓ Yordam")
async def help_cmd(msg: Message):
    await msg.answer(
        "❓ <b>Yordam</b>\n\n"
        "🔗 <b>Referal havolam</b> — Shaxsiy havolangizni olib do'stlarga yuboring.\n\n"
        "📊 <b>Statistikam</b> — Siz taklif qilganlar ro'yxati va soni.\n\n"
        "🏆 <b>Top reyting</b> — Eng ko'p taklif qilganlar ro'yxati.\n\n"
        "📞 Muammo bo'lsa admingа murojaat qiling.",
        parse_mode="HTML"
    )

@router.message(F.text == "⚙️ Admin panel")
async def admin_panel(msg: Message):
    if msg.from_user.id not in ADMIN_IDS:
        return
    total = await get_total_users()
    await msg.answer(
        f"⚙️ <b>Admin panel</b>\n\n👥 Jami foydalanuvchilar: <b>{total}</b>",
        parse_mode="HTML", reply_markup=admin_kb()
    )

@router.callback_query(F.data == "stats")
async def admin_stats(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
    total = await get_total_users()
    top = await get_top_users(5)
    text = f"📈 <b>Statistika</b>\n\n👥 Jami: <b>{total}</b>\n\n🏆 Top 5:\n"
    for i, u in enumerate(top, 1):
        text += f"  {i}. {u['full_name'] or 'Nomalum'} — {u['referral_count']} kishi\n"
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=admin_kb())

@router.callback_query(F.data == "broadcast")
async def broadcast_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return
    await state.set_state(St.broadcast)
    await call.message.edit_text(
        "📨 Barcha foydalanuvchilarga yuboriladigan xabarni yozing\n(matn, rasm, video — istalgan):",
        reply_markup=cancel_kb()
    )

@router.message(St.broadcast)
async def do_broadcast(msg: Message, bot: Bot, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS:
        return
    await state.clear()
    ids = await get_all_user_ids()
    ok = fail = 0
    status = await msg.answer(f"📤 Yuborilmoqda... 0/{len(ids)}")
    for i, uid in enumerate(ids):
        try:
            await msg.copy_to(uid)
            ok += 1
        except Exception:
            fail += 1
        if (i + 1) % 20 == 0:
            try:
                await status.edit_text(f"📤 Yuborilmoqda... {i+1}/{len(ids)}")
            except Exception:
                pass
        await asyncio.sleep(0.05)
    await status.edit_text(
        f"✅ <b>Yuborish yakunlandi!</b>\n\n✔️ Muvaffaqiyatli: <b>{ok}</b>\n❌ Xatolik: <b>{fail}</b>",
        parse_mode="HTML"
    )

@router.callback_query(F.data == "search")
async def search_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return
    await state.set_state(St.search)
    await call.message.edit_text(
        "🔍 Foydalanuvchi <b>username</b> yoki <b>ID</b> sini kiriting:",
        parse_mode="HTML", reply_markup=cancel_kb()
    )

@router.message(St.search)
async def do_search(msg: Message, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS:
        return
    await state.clear()
    results = await search_user(msg.text)
    if not results:
        await msg.answer("❌ Foydalanuvchi topilmadi.")
        return
    for u in results[:5]:
        full_name = u['full_name'] or "Noma'lum"
        username = u['username'] or "-"
        referred_by = u['referred_by'] or "mustaqil"
        joined_at = str(u['joined_at'])[:10]

        text = (
            f"👤 <b>{full_name}</b>\n"
            f"🆔 ID: <code>{u['user_id']}</code>\n"
            f"📛 Username: @{username}\n"
            f"👥 Taklif qilgani: <b>{u['referral_count']}</b> kishi\n"
            f"🔗 Kim orqali: <code>{referred_by}</code>\n"
            f"📅 Qo'shilgan: {joined_at}"
        )
        await msg.answer(text, parse_mode="HTML")

@router.callback_query(F.data == "cancel")
async def cancel(call: CallbackQuery, state: FSMContext):
    await state.clear()
    total = await get_total_users()
    await call.message.edit_text(
        f"⚙️ <b>Admin panel</b>\n\n👥 Jami: <b>{total}</b>",
        parse_mode="HTML", reply_markup=admin_kb()
    )

# ─────────────────────────────────────────────
#  RENDER UCHUN SOXTA VEB-SERVER (WEB SITE)
# ─────────────────────────────────────────────

async def handle_web(request):
    return web.Response(text="Bot muvaffaqiyatli ishlayapti ✅")

async def start_web_server():
    webapp = web.Application()
    webapp.router.add_get('/', handle_web)
    runner = web.AppRunner(webapp)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    log.info(f"Veb-server {PORT}-portda ishga tushdi.")

# ─────────────────────────────────────────────
#  ISHGA TUSHIRISH (MAIN)
# ─────────────────────────────────────────────

async def main():
    if not BOT_TOKEN:
        log.error("XATO: BOT_TOKEN o'zgaruvchisi topilmadi!")
        return

    await init_db()
    
    bot = Bot(token=BOT_TOKEN)
    dp  = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    
    # Veb-serverni bot bilan parallel ishga tushiramiz
    await start_web_server()
    
    log.info("Bot polling rejimida ishga tushdi ✅")
    
    # Eski so'rovlarni o'chirib yuborish (Render qayta yonganda tiqilinch bo'lmasligi uchun)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Bot to'xtatildi.")
