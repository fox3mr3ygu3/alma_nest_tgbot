import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from db import validate_password, conn, decrement_visit, clear_session_keys, get_session_value, get_client, count_bookings_for_period, set_session_value
from config import ADMIN_ID, NOTIFIER_BOT_TOKEN
from datetime import datetime, timedelta
from back_utils import append_back_button

MAX_CAPACITY = {8: 15, 10: 10, 12: 5}
LOGIN_ID, LOGIN_PASSWORD = range(2)


async def client_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Prevent admin from entering user flow
    if str(user_id) == str(ADMIN_ID):
        return ConversationHandler.END

    # Check if session already exists
    cur = conn.cursor()
    cur.execute("SELECT client_id FROM sessions WHERE telegram_id = %s", (user_id,))
    row = cur.fetchone()
    cur.close()

    if row:
        client_id = row[0]

        client_id = row[0]
        # Validate client exists AND session must be marked as validated
        if row:
            client_id = row[0]
            if get_session_value(user_id, "validated"):
                set_session_value(user_id, "id", client_id)
                return await return_visit_buttons(update, context, user_id)
        else:
            await update.message.reply_text("Введите ваш 6-значный пароль:")
            set_session_value(user_id, "id", client_id)
            return LOGIN_PASSWORD

    # New user → start login flow
    await update.message.reply_text("Добро пожаловать! Введите свой 4-значный ID:")
    return LOGIN_ID



async def get_client_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    client_id = update.message.text.strip()

    if not client_id.isdigit() or len(client_id) != 4:
        await update.message.reply_text("❌ Неверный формат ID. Введите 4-значный ID:")
        return LOGIN_ID

    set_session_value(user_id, "id", client_id)
    await update.message.reply_text("Теперь введите свой 6-значный пароль:")
    return LOGIN_PASSWORD


async def get_client_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    password = update.message.text.strip()

    client_id = get_session_value(user_id, "id")
    if not client_id:
        await update.message.reply_text("⚠️ Сессия истекла. Пожалуйста, начните снова. /start")
        return ConversationHandler.END

    if not password.isdigit() or len(password) != 6:
        await update.message.reply_text("❌ Неверный формат пароля. Введите пароль из 6 цифр:")
        return LOGIN_PASSWORD

    result = validate_password(client_id, password)
    if not result:
        await update.message.reply_text("❌ Неверный ID или пароль. Попробуйте еще раз с помощью /start.")
        return ConversationHandler.END

    client_info = get_client(client_id)
    package_type = int(client_info[5])
    visits_remaining = int(client_info[6])
    full_name = client_info[3]
    expire_date = datetime.strptime(str(client_info[8]), "%Y-%m-%d").strftime("%d/%m/%Y")
    used_visits = package_type - visits_remaining

    set_session_value(user_id, "package", package_type)
    set_session_value(user_id, "validated", True)

    cur = conn.cursor()
    cur.execute("""
        INSERT INTO sessions (telegram_id, client_id)
        VALUES (%s, %s)
        ON CONFLICT (telegram_id) DO UPDATE SET client_id = EXCLUDED.client_id
    """, (user_id, client_id))
    conn.commit()
    cur.close()

    buttons = [[InlineKeyboardButton(f"Посещение {i}", callback_data=f"visit_{i}")] 
               for i in range(used_visits + 1, package_type + 1)]
    buttons.append([InlineKeyboardButton("🔒 Выйти", callback_data="logout")])
    reply_markup = append_back_button(buttons)

    await update.message.reply_text(
    f"✅ Вы успешно вошли!\n"
    f"Имя: {full_name}\n"
    f"Пакет: {package_type} посещений\n"
    f"Осталось: {visits_remaining}\n"
    f"Действует до: {expire_date}\n\n"
    f"Пожалуйста, выберите дату следующего посещения:",
    reply_markup=reply_markup
    )
    return ConversationHandler.END


async def return_visit_buttons(update, context, user_id):
    client_id = get_session_value(user_id, "id")

    if not client_id:
        cur = conn.cursor()
        cur.execute("SELECT client_id FROM sessions WHERE telegram_id = %s", (user_id,))
        row = cur.fetchone()
        cur.close()
        if not row:
            await update.message.reply_text("Сеанс не найден. Пожалуйста, начните заново командой /start.")
            return ConversationHandler.END
        client_id = row[0]
        set_session_value(user_id, "id", client_id)

    client_info = get_client(client_id)
    if not client_info:
        await update.message.reply_text("❌ Клиент не найден. Пожалуйста, свяжитесь с администратором - @almanest_contact.")
        return ConversationHandler.END

    package_type = int(client_info[5])
    visits_remaining = int(client_info[6])
    full_name = client_info[3]
    expire_raw = client_info[8]
    expire_date = datetime.strptime(str(expire_raw), "%Y-%m-%d").strftime("%d/%m/%Y")
    used_visits = package_type - visits_remaining

    # If expired or used all visits, end session
    if visits_remaining == 0 or datetime.today().date() > datetime.strptime(str(expire_raw), "%Y-%m-%d").date():
        cur = conn.cursor()
        cur.execute("DELETE FROM sessions WHERE telegram_id = %s", (user_id,))
        conn.commit()
        cur.close()
        await update.message.reply_text("❌ Ваш пакет закончился или срок его действия истёк. Пожалуйста, свяжитесь с администратором - @almanest_contact.")
        return ConversationHandler.END

    set_session_value(user_id, "package", package_type)

    buttons = [[InlineKeyboardButton(f"Посещение {i}", callback_data=f"visit_{i}")]
               for i in range(used_visits + 1, package_type + 1)]
    buttons.append([InlineKeyboardButton("🔒 Выйти", callback_data="logout")])
    reply_markup = append_back_button(buttons, include_back=False)

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text = (
            f"✅ С возвращением!\n"
            f"Имя: {full_name}\n"
            f"Пакет: {package_type} посещений\n"
            f"Осталось: {visits_remaining}\n"
            f"Действует до: {expire_date}\n\n"
            f"Выберите дату следующего посещения:"
        ),
        reply_markup=reply_markup
    )

async def visit_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query


    user_id = update.effective_user.id
    client_id = get_session_value(user_id, "id")
    if not client_id:
        return ConversationHandler.END

    client_info = get_client(client_id)
    if not client_info:
        return ConversationHandler.END

    package_type = int(client_info[5])
    visits_remaining = int(client_info[6])
    used_visits = package_type - visits_remaining

    data = query.data
    if not data.startswith("visit_"):
        return ConversationHandler.END

    clicked_visit = int(data.split("_")[1])
    expected_visit = used_visits + 1

    # ❌ If wrong visit clicked → show popup alert, but don't delete buttons
    if clicked_visit != expected_visit:
        await query.answer(
            text=f"⚠️ Сначала необходимо выбрать Посещение {expected_visit}.",
            show_alert=True
        )
        return

    # ✅ Correct visit → delete old message
    await query.message.delete()

    set_session_value(user_id, "last_visit", clicked_visit)

    today = datetime.today()
    buttons, row = [], []
    for i in range(30):
        date = today + timedelta(days=i)
        label = date.strftime("%#d-%b")
        row.append(InlineKeyboardButton(label, callback_data=f"day_{date.strftime('%Y-%m-%d')}"))
        if len(row) == 4:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append([InlineKeyboardButton("🔒 Выйти", callback_data="logout")])
    reply_markup = append_back_button(buttons)

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text = f"📅 Выберите день для Посещения {clicked_visit}:",
        reply_markup=reply_markup
    )


async def select_day_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.delete()

    user_id = update.effective_user.id
    if not query.data.startswith("day_"):
        return

    selected_date = query.data.split("_")[1]
    parsed_date = datetime.strptime(selected_date, "%Y-%m-%d")
    formatted_date = parsed_date.strftime("%d/%m/%Y")

    set_session_value(user_id, "selected_day", formatted_date)

    client_id = get_session_value(user_id, "id")
    if not client_id:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ Session expired.")
        return ConversationHandler.END

    client_info = get_client(client_id)
    package_type = int(client_info[5])
    now = datetime.now()

    if package_type == 8:
        periods = [("08:00", "11:00"), ("11:00", "14:00"), ("14:00", "17:00"), ("17:00", "20:00")]
    elif package_type == 10:
        periods = [("08:00", "12:00"), ("12:00", "16:00"), ("16:00", "20:00")]
    else:
        periods = [("08:00", "14:00"), ("14:00", "20:00")]

    buttons, row = [], []
    for start_str, end_str in periods:
        label = f"{start_str}–{end_str}"
        start_time = datetime.strptime(start_str, "%H:%M").time()

        if parsed_date.date() == now.date() and now.time() > start_time:
            row.append(InlineKeyboardButton(f"⛔ {label}", callback_data="ignore"))
        else:
            count = count_bookings_for_period(parsed_date.date(), label)
            if count >= MAX_CAPACITY.get(package_type, 10):
                row.append(InlineKeyboardButton(f"⛔ {label}", callback_data="full"))
            else:
                row.append(InlineKeyboardButton(label, callback_data=f"time_{label}"))

        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    last_visit = get_session_value(user_id, "last_visit") or "?"
    reply_markup = append_back_button(buttons)

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text = f"⏰ Выберите время для Посещения {last_visit} на дату {formatted_date}:",        reply_markup=reply_markup
    )


async def select_time_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.delete()

    user_id = update.effective_user.id
    if not query.data.startswith("time_"):
        return

    selected_time = query.data.split("_", 1)[1]
    selected_day = get_session_value(user_id, "selected_day")
    visit = get_session_value(user_id, "last_visit")
    client_id = get_session_value(user_id, "id")

    if not selected_day or not visit or not client_id:
        return

    date_obj = datetime.strptime(selected_day, "%d/%m/%Y").date()

    #decrement_visit(client_id, int(visit), date_obj, selected_time)
    set_session_value(user_id, "visit_day", selected_day)
    set_session_value(user_id, "visit_time", selected_time)

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text = (
            f"📌 Посещение {visit} запланировано на {selected_day} в {selected_time}.\n"
            f"👶 Пожалуйста, укажите количество детей, которые будут присутствовать:"
        )
    )

async def children_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not all([
        get_session_value(user_id, "last_visit"),
        get_session_value(user_id, "visit_day"),
        get_session_value(user_id, "visit_time")
    ]):
        return
    if str(user_id) == str(ADMIN_ID):
        return ConversationHandler.END

    text = update.message.text.strip()
    if not text.isdigit() or not (1 <= int(text) <= 20):
        await update.message.reply_text("❌ Пожалуйста, введите корректное количество детей (от 1 до 20).")
        return

    visit = get_session_value(user_id, "last_visit")
    selected_day = get_session_value(user_id, "selected_day")
    selected_time = get_session_value(user_id, "visit_time")
    client_id = get_session_value(user_id, "id")

    if not all([visit, selected_day, selected_time, client_id]):
        await update.message.reply_text("⚠️ Сессия нарушена. Пожалуйста, начните сначала командой /start.")
        return ConversationHandler.END

    # ✅ 1. Send confirmation before deletion
    await update.message.reply_text(
        f"✅ Посещение {visit} забронировано на {selected_day} в {selected_time} для {text} детей.\nДо встречи!"
    )

    client_data = get_client(client_id)
    full_name = client_data[3] if client_data else "Unknown"

    # ✅ 2. Notify admin
    requests.post(
        f"https://api.telegram.org/bot{NOTIFIER_BOT_TOKEN}/sendMessage",
        json={
            "chat_id": ADMIN_ID,
            "text": (
                f"📢 New Booking\n"
                f"👤 Name: {full_name}\n"
                f"🆔 ID: {client_id}\n"
                f"📅 Visit {visit} booked for {selected_day} at {selected_time}\n"
                f"👶 Children: {text}"
            )
        }
    )

    # 3. Only now — decrement and possibly delete
    date_obj = datetime.strptime(selected_day, "%d/%m/%Y").date()
    decrement_visit(client_id, int(visit), date_obj, selected_time)
    clear_session_keys(user_id, ["last_visit", "visit_day", "visit_time"])
    # 4. Try to return visit buttons — if client still exists
    if get_client(client_id):
        await return_visit_buttons(update, context, user_id)
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            "✅ Ваше последнее посещение учтено, и ваш профиль теперь неактивен.\n"
            "Пожалуйста, свяжитесь с администратором, чтобы получить новый пакет - @almanest_contact."
        )
        cur = conn.cursor()
        cur.execute("DELETE FROM sessions WHERE telegram_id = %s", (user_id,))
        conn.commit()
        cur.close()
        return ConversationHandler.END


async def ignore_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("⚠️ Этот сеанс уже начался.", show_alert=True)


async def full_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("❌ Это временное окно уже заполнено. Пожалуйста, выберите другое.", show_alert=True)



async def logout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Fully remove from session table
    cur = conn.cursor()
    cur.execute("DELETE FROM sessions WHERE telegram_id = %s", (user_id,))
    conn.commit()
    cur.close()

    # Optional: clear keys if session stays
    # clear_session_keys(user_id, ["id", "package", "selected_day", "last_visit", "visit_time"])

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.edit_text("👋 Вы успешно вышли из аккаунта. /start")
    elif update.message:
        await update.message.reply_text("👋 Вы успешно вышли из аккаунта. /start")


async def client_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Отменено.")
    return ConversationHandler.END