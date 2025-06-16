from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from datetime import datetime, timedelta
from db import count_bookings_for_period, conn
from config import SUPERUSER_ID, SUPERUSER_PASSWORD

MAX_CAPACITY = {
    8: 15,
    10: 10,
    12: 5
}
SUPER_CHILDREN = 101  

async def start_superuser_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    context.user_data["client_id"] = SUPERUSER_ID
    context.user_data["password"] = SUPERUSER_PASSWORD
    context.user_data["visit_number"] = 1

    await query.message.edit_text("👶 Enter number of children:")
    return SUPER_CHILDREN


async def handle_superuser_package(update: Update, context: ContextTypes.DEFAULT_TYPE):
    package_type = int(update.callback_query.data.split("_")[2])
    context.user_data["package"] = package_type
    await update.callback_query.answer()

    today = datetime.today()
    buttons = []
    row = []
    for i in range(30):
        date = today + timedelta(days=i)
        label = date.strftime("%d-%b")
        callback_data = f"super_day_{date.strftime('%Y-%m-%d')}"
        row.append(InlineKeyboardButton(label, callback_data=callback_data))
        if len(row) == 4:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    await update.callback_query.message.edit_text(
        "📅 Select a day for Visit 1:", reply_markup=InlineKeyboardMarkup(buttons)
    )


async def handle_superuser_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    selected_date = update.callback_query.data.split("_")[2]
    date_obj = datetime.strptime(selected_date, "%Y-%m-%d").date()
    context.user_data["date"] = date_obj

    package = context.user_data["package"]
    if package == 8:
        periods = ["08:00–11:00", "11:00–14:00", "14:00–17:00", "17:00–20:00"]
    elif package == 10:
        periods = ["08:00–12:00", "12:00–16:00", "16:00–20:00"]
    else:
        periods = ["08:00–14:00", "14:00–20:00"]

    now = datetime.now()
    is_today = (date_obj == now.date())
    max_allowed = MAX_CAPACITY.get(package, 10)

    buttons = []
    for period in periods:
        start_str = period.split("–")[0]
        start_time = datetime.strptime(start_str, "%H:%M").time()

        count = count_bookings_for_period(date_obj, period)

        if is_today and now.time() > start_time:
            buttons.append([InlineKeyboardButton(f"⛔ {period}", callback_data="ignore")])
        elif count >= max_allowed:
            buttons.append([InlineKeyboardButton(f"⛔ {period}", callback_data="full")])
        else:
            buttons.append([InlineKeyboardButton(period, callback_data=f"super_time_{period}")])

    await update.callback_query.message.edit_text(
        "⏰ Select time slot:", reply_markup=InlineKeyboardMarkup(buttons)
    )


async def handle_superuser_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    time_period = update.callback_query.data.split("_", 2)[2]
    client_id = context.user_data["client_id"]
    date_value = context.user_data["date"]
    visit_number = context.user_data["visit_number"]

    cur = conn.cursor()
    cur.execute("""
        INSERT INTO visit_logs (client_id, visit_number, visit_date, time_period)
        VALUES (%s, %s, %s, %s)
    """, (client_id, visit_number, date_value, time_period))
    conn.commit()
    cur.close()

    await update.callback_query.message.edit_text(
        f"✅ Visit logged for superuser on {date_value.strftime('%d/%m/%Y')} at {time_period}"
    )


async def ask_superuser_children(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    context.user_data["client_id"] = SUPERUSER_ID
    context.user_data["password"] = SUPERUSER_PASSWORD
    context.user_data["visit_number"] = 1

    await query.message.edit_text("👶 Enter number of children:")
    return SUPER_CHILDREN


async def handle_superuser_children(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("client_id") != SUPERUSER_ID:
        return ConversationHandler.END
    
    text = update.message.text
    if not text.isdigit():
        await update.message.reply_text("❌ Please enter a valid number.")
        return SUPER_CHILDREN

    context.user_data["children"] = int(text)

    keyboard = [
        [InlineKeyboardButton("8 Visits", callback_data="super_pkg_8")],
        [InlineKeyboardButton("10 Visits", callback_data="super_pkg_10")],
        [InlineKeyboardButton("12 Visits", callback_data="super_pkg_12")],
    ]
    await update.message.reply_text("Select package type:", reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END  # We are not using classic conversation here
