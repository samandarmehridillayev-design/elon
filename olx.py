import sqlite3
import telebot
from telebot import types

TOKEN = '8934681392:AAE-yJP_Qrn7CF2MYtqzWagSDOLyVQp95Oo'  # BotFather'dan olingan token
CHANNEL_ID = '@elon_savdosi'  # Kanalingiz username'i
ADMIN_ID = 8004582786  # Telegram ID raqamingiz

bot = telebot.TeleBot(TOKEN)


# --- 1. MA'LUMOTLAR BAZASI ---
def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            category TEXT,
            title TEXT,
            region TEXT,
            price INTEGER,
            phone TEXT,
            photo_id TEXT
        )
    ''')
    conn.commit()
    conn.close()


init_db()

user_data = {}
search_filters = {}
pending_ads = {}


# --- 2. ASOSIY MENYU ---
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("➕ E'lon berish", "🔍 Qidirish")
    bot.send_message(
        message.chat.id,
        "Salom! Avto, Uy-joy va Telefon savdosi botiga xush kelibsiz.\nBo'limni tanlang:",
        reply_markup=markup
    )


# Kategoriya tanlash menyusi
def get_categories_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("🏠 Uy-joy", "🚗 Avtomobil", "📱 Telefonlar")
    return markup


# --- 3. E'LON BERISH BOSQICHLARI ---
@bot.message_handler(func=lambda msg: msg.text == "➕ E'lon berish")
def add_ad_start(message):
    msg = bot.send_message(message.chat.id, "Kategoriyani tanlang:", reply_markup=get_categories_keyboard())
    bot.register_next_step_handler(msg, process_category)


def process_category(message):
    chat_id = message.chat.id
    category = message.text
    user_data[chat_id] = {'category': category}

    markup = types.ReplyKeyboardRemove()

    # Kategoriya bo'yicha maxsus ko'rsatib o'tish
    if category == "📱 Telefonlar":
        prompt_text = "Model va xotirasini kiriting (Masalan: iPhone 13 Pro 128GB, karobka-dok bor):"
    elif category == "🚗 Avtomobil":
        prompt_text = "Model va yilini kiriting (Masalan: Cobalt 2022 2-pozitsiya, kraska toza):"
    else:
        prompt_text = "Sarlavha/Tavsifni kiriting (Masalan: 2 xonali uy yevroremont):"

    msg = bot.send_message(chat_id, prompt_text, reply_markup=markup)
    bot.register_next_step_handler(msg, process_title)


def process_title(message):
    chat_id = message.chat.id
    user_data[chat_id]['title'] = message.text

    msg = bot.send_message(chat_id, "Qaysi shahar/viloyatda? (Masalan: Toshkent):")
    bot.register_next_step_handler(msg, process_region)


def process_region(message):
    chat_id = message.chat.id
    user_data[chat_id]['region'] = message.text

    msg = bot.send_message(chat_id, "Narxini kiriting (faqat raqamda, USD):")
    bot.register_next_step_handler(msg, process_price)


def process_price(message):
    chat_id = message.chat.id
    if not message.text.isdigit():
        msg = bot.send_message(chat_id, "Iltimos, narxni faqat raqamlarda kiriting:")
        bot.register_next_step_handler(msg, process_price)
        return

    user_data[chat_id]['price'] = int(message.text)

    msg = bot.send_message(chat_id, "Bog'lanish uchun telefon raqamingizni kiriting:")
    bot.register_next_step_handler(msg, process_phone)


def process_phone(message):
    chat_id = message.chat.id
    user_data[chat_id]['phone'] = message.text

    msg = bot.send_message(chat_id, "Rasm yuboring:")
    bot.register_next_step_handler(msg, process_photo)


def process_photo(message):
    chat_id = message.chat.id
    if message.content_type != 'photo':
        msg = bot.send_message(chat_id, "Iltimos, rasm yuboring!")
        bot.register_next_step_handler(msg, process_photo)
        return

    user_data[chat_id]['photo_id'] = message.photo[-1].file_id
    data = user_data[chat_id]

    ad_key = f"{chat_id}_{message.message_id}"
    pending_ads[ad_key] = data

    caption_text = (
        f"🆕 **YANGI MODERATSIYA E'LONI**\n\n"
        f"👤 **Foydalanuvchi ID:** `{chat_id}`\n"
        f"📁 **Kategoriya:** {data['category']}\n"
        f"📝 **Tavsif:** {data['title']}\n"
        f"📍 **Hudud:** {data['region']}\n"
        f"💰 **Narxi:** ${data['price']}\n"
        f"📞 **Aloqa:** {data['phone']}"
    )

    markup = types.InlineKeyboardMarkup()
    btn_approve = types.InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"approve_{ad_key}")
    btn_reject = types.InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_{ad_key}")
    markup.add(btn_approve, btn_reject)

    try:
        bot.send_photo(ADMIN_ID, data['photo_id'], caption=caption_text, reply_markup=markup, parse_mode="Markdown")
        bot.send_message(chat_id, "⏳ E'longiz adminga moderatsiyaga yuborildi. Tasdiqlangach kanalga joylanadi!")
    except Exception as e:
        bot.send_message(chat_id, "❌ E'lonni adminga yuborishda xatolik yuz berdi.")
        print(f"Admin yuborish xatosi: {e}")

    start(message)


# --- 4. ADMIN MODERATSIYASI ---
@bot.callback_query_handler(func=lambda call: call.data.startswith(('approve_', 'reject_')))
def handle_moderation(call):
    action, ad_key = call.data.split('_', 1)

    if ad_key not in pending_ads:
        bot.answer_callback_query(call.id, "Bu e'lon allaqachon ko'rib chiqilgan!", show_alert=True)
        return

    data = pending_ads.pop(ad_key)
    owner_id = int(ad_key.split('_')[0])

    if action == "approve":
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO ads (user_id, category, title, region, price, phone, photo_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (owner_id, data['category'], data['title'], data['region'], data['price'], data['phone'],
              data['photo_id']))
        conn.commit()
        conn.close()

        channel_text = (
            f"📢 **YANGI E'LON ({data['category'].upper()})**\n\n"
            f"📝 **Tavsif:** {data['title']}\n"
            f"📍 **Hudud:** {data['region']}\n"
            f"💰 **Narxi:** ${data['price']}\n"
            f"📞 **Aloqa:** {data['phone']}\n\n"
            f"🤖 *Bot orqali joylandi*"
        )
        try:
            bot.send_photo(CHANNEL_ID, data['photo_id'], caption=channel_text, parse_mode="Markdown")
        except Exception as e:
            print(f"Kanalga joylashda xato: {e}")

        bot.edit_message_caption("✅ E'lon tasdiqlandi va kanalga joylandi!", chat_id=call.message.chat.id,
                                 message_id=call.message.message_id)
        bot.send_message(owner_id, "🎉 Xushxabar! E'longiz admin tomonidan tasdiqlandi va kanalga joylandi.")

    elif action == "reject":
        bot.edit_message_caption("❌ E'lon rad etildi.", chat_id=call.message.chat.id,
                                 message_id=call.message.message_id)
        bot.send_message(owner_id, "😔 Afsuski, e'longiz admin tomonidan rad etildi.")

    bot.answer_callback_query(call.id)


# --- 5. QIDIRUV TIZIMI ---
@bot.message_handler(func=lambda msg: msg.text == "🔍 Qidirish")
def search_start(message):
    msg = bot.send_message(message.chat.id, "Qaysi kategoriyada qidirmoqchisiz?",
                           reply_markup=get_categories_keyboard())
    bot.register_next_step_handler(msg, process_search_category)


def process_search_category(message):
    chat_id = message.chat.id
    search_filters[chat_id] = {'category': message.text}

    markup = types.ReplyKeyboardRemove()
    msg = bot.send_message(chat_id, "Qaysi hududdan qidiryapsiz? (Masalan: Toshkent yoki 'Hammasi'):",
                           reply_markup=markup)
    bot.register_next_step_handler(msg, process_search_region)


def process_search_region(message):
    chat_id = message.chat.id
    search_filters[chat_id]['region'] = message.text

    msg = bot.send_message(chat_id, "Maksimal narxni kiriting (USD, masalan: 500 yoki cheklovsiz bo'lsa '0'):")
    bot.register_next_step_handler(msg, process_search_max_price)


def process_search_max_price(message):
    chat_id = message.chat.id
    if not message.text.isdigit():
        msg = bot.send_message(chat_id, "Iltimos, narxni faqat raqamda kiriting:")
        bot.register_next_step_handler(msg, process_search_max_price)
        return

    max_price = int(message.text)
    search_filters[chat_id]['max_price'] = max_price
    filters = search_filters[chat_id]

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    query = "SELECT title, region, price, phone, photo_id FROM ads WHERE category = ?"
    params = [filters['category']]

    if filters['region'].lower() != 'hammasi':
        query += " AND LOWER(region) LIKE ?"
        params.append(f"%{filters['region'].lower()}%")

    if filters['max_price'] > 0:
        query += " AND price <= ?"
        params.append(filters['max_price'])

    query += " ORDER BY id DESC LIMIT 10"

    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()

    if not results:
        bot.send_message(chat_id, "🔍 Afsuski, kiritilgan filtrlar bo'yicha e'lon topilmadi.")
        start(message)
        return

    bot.send_message(chat_id, f"🎯 **Natijalar (Topildi: {len(results)} ta):**", parse_mode="Markdown")
    for item in results:
        caption = f"📌 **{item[0]}**\n📍 Hudud: {item[1]}\n💰 Narxi: ${item[2]}\n📞 Tel: {item[3]}"
        bot.send_photo(chat_id, item[4], caption=caption, parse_mode="Markdown")

    start(message)


print("Bot 3 ta kategoriya bilan ishlamoqda...")
bot.infinity_polling()