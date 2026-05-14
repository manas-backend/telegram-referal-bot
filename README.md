# 🤖 Telegram Referal Bot

Telegram uchun to'liq referal tizimi bilan bot.

## ✨ Imkoniyatlar

- ✅ Foydalanuvchilarni ro'yxatdan o'tkazish
- 🔗 Har biriga maxsus referal link berish
- 📊 Taklif qilinganlarni hisoblash
- 🏆 TOP 10 reyting ko'rsatish
- 👨‍💼 Admin panel
- 📈 To'liq statistika
- 💾 SQLite database

## 🚀 O'rnatish

### 1. Bot yaratish

1. Telegram'da [@BotFather](https://t.me/BotFather) ga o'ting
2. `/newbot` buyrug'ini yuboring
3. Bot uchun nom kiriting (masalan: "Mening Referal Botim")
4. Bot uchun username kiriting (masalan: "my_referral_bot")
5. BotFather sizga **TOKEN** beradi (masalan: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)

### 2. Admin ID ni topish

1. [@userinfobot](https://t.me/userinfobot) ga o'ting
2. `/start` ni bosing
3. Sizning **User ID** raqamingizni ko'rsatadi (masalan: `123456789`)

### 3. Kodni sozlash

`referral_bot.py` faylini oching va quyidagilarni o'zgartiring:

```python
# 13-qatorda:
ADMIN_ID = 123456789  # Bu yerga o'z User ID raqamingizni kiriting

# 269-qatorda:
TOKEN = "YOUR_BOT_TOKEN_HERE"  # Bu yerga BotFather dan olingan tokenni kiriting
```

### 4. Kerakli kutubxonalarni o'rnatish

```bash
pip install -r requirements.txt
```

yoki:

```bash
pip install python-telegram-bot==21.0
```

### 5. Botni ishga tushirish

```bash
python referral_bot.py
```

Agar hammasi to'g'ri bo'lsa, konsolda ko'rasiz:
```
✅ Bot ishga tushdi!
```

## 📱 Foydalanish

### Oddiy foydalanuvchilar uchun:

1. **Boshlash**: Botga `/start` yuboring
2. **Referal link olish**: Sizga maxsus link beriladi
3. **Do'stlarni taklif qilish**: Linkni ulashing
4. **Statistika**: "📊 Mening statistikam" tugmasini bosing
5. **Reyting**: "🏆 TOP reyting" tugmasini bosing

### Admin uchun:

1. Botga `/start` yuboring
2. "👨‍💼 Admin panel" tugmasi paydo bo'ladi
3. Jami statistikani ko'ring
4. Barcha foydalanuvchilarni boshqaring

## 🗂️ Database struktura

Bot `referral_bot.db` SQLite databasedan foydalanadi:

### `users` jadvali:
- `user_id` - Foydalanuvchi ID
- `username` - Telegram username
- `first_name` - Ism
- `referred_by` - Kim taklif qilgan
- `referral_count` - Necha kishi taklif qilgan
- `join_date` - Qo'shilgan sana
- `is_active` - Faolmi

### `referrals` jadvali:
- `id` - Referal ID
- `referrer_id` - Taklif qilgan ID
- `referred_id` - Taklif qilingan ID
- `date` - Sana

## 🎯 Asosiy funksiyalar

### Referal tizimi
```
https://t.me/your_bot?start=123456789
                              ↑
                    Taklif qiluvchining ID
```

Yangi foydalanuvchi bu link orqali botga qo'shilsa:
- U avtomatik ro'yxatdan o'tadi
- Taklif qiluvchining hisobi +1 ga oshadi
- Statistika yangilanadi

### TOP reyting
```
🥇 1. Ali @ali123 - 15 kishi
🥈 2. Vali @vali456 - 12 kishi
🥉 3. Guli @guli789 - 8 kishi
4. Hasan @hasan - 5 kishi
...
```

## 🛠️ Sozlamalar

### Bot tokenini almashtirish:
```python
TOKEN = "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"
```

### Admin ID ni o'zgartirish:
```python
ADMIN_ID = 123456789  # O'z ID raqamingiz
```

### TOP reytingdagi foydalanuvchilar sonini o'zgartirish:
```python
top_users = get_top_users(10)  # 10 o'rniga istalgan son
```

## 📊 Misol

**Foydalanuvchi A** botga qo'shiladi:
- Unga link beriladi: `https://t.me/bot?start=111`

**Foydalanuvchi B** bu link orqali qo'shiladi:
- B ro'yxatdan o'tadi
- A ning hisobi: 1 kishi

**Foydalanuvchi C** A ning linki orqali qo'shiladi:
- C ro'yxatdan o'tadi
- A ning hisobi: 2 kishi

**TOP reyting**:
```
1. A - 2 kishi
2. B - 0 kishi
3. C - 0 kishi
```

## 🔧 Muammolarni hal qilish

### Bot ishlamayapti?
- TOKEN to'g'ri kiritilganini tekshiring
- Internetga ulanganingizni tekshiring
- Python 3.7+ versiyasi o'rnatilganini tekshiring

### Admin panel ko'rinmayapti?
- ADMIN_ID raqami to'g'ri kiritilganini tekshiring
- Botni qayta ishga tushiring

### Database xatosi?
- `referral_bot.db` faylini o'chiring
- Botni qayta ishga tushiring (yangi database yaratiladi)

## 📝 Keyingi versiyalar uchun

- [ ] Xabar yuborish (broadcast)
- [ ] Excel export
- [ ] Grafik statistika
- [ ] Mukofotlar tizimi
- [ ] Telegram Premium integratsiya
- [ ] Multi-til qo'llab-quvvatlash

## 💡 Maslahatlar

1. **Botni serverda ishlatish**: VPS yoki Heroku da ishga tushiring
2. **Backup**: Database faylini muntazam saqlang
3. **Monitoring**: Botning statistikasini kuzatib boring
4. **Marketing**: Referal tizimini rag'batlantirish uchun mukofotlar bering

## 📞 Yordam

Savollaringiz bo'lsa, botni ishga tushirishda yordam kerak bo'lsa, menga murojaat qiling!

## 📄 Litsenziya

Bu kod bepul va ochiq. Istalganingizcha o'zgartiring va ishlating!

---

**✨ Omad tilayman! Botingiz TOP bo'lsin! 🚀**
