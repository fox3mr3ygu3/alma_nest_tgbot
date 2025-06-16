from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from db import (
    add_client, get_all_clients, count_bookings_for_period, decrement_visit,
    set_session_value, get_session_value, clear_session_keys
)
from config import ADMIN_ID
from telegram.error import BadRequest
from datetime import datetime, timedelta
from superuser import start_superuser_flow

# Conversation states
NAME, PHONE, CHILDREN, PACKAGE = range(4)
DAYS_PER_PAGE = 5
MAX_PAGES = 6

all_periods = {
    "08:00–11:00": 15, "11:00–14:00": 15, "14:00–17:00": 15, "17:00–20:00": 15,
    "08:00–12:00": 10, "12:00–16:00": 10, "16:00–20:00": 10,
    "08:00–14:00": 5, "14:00–20:00": 5
}

async def admin_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "add_client":
        await query.message.edit_text("Enter client name:")
        return NAME
    elif query.data == "offline_superuser":
        return await start_superuser_flow(update, context)
    elif query.data == "list_clients":
        await query.message.edit_text("📋 Listing clients coming soon...")
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton("➕ Add Client", callback_data="add_client")],
        [InlineKeyboardButton("📋 List Clients", callback_data="list_clients")],
        [InlineKeyboardButton("📊 Available Slots", callback_data="available_slots")],
        [InlineKeyboardButton("📥 Offline Client", callback_data="offline_superuser")]
    ]
    try:
        await query.message.edit_text("Welcome Admin. Choose:", reply_markup=InlineKeyboardMarkup(keyboard))
    except BadRequest as e:
        if "Message is not modified" not in str(e):
            raise
    return ConversationHandler.END

async def list_clients(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    clients = get_all_clients()
    if not clients:
        await query.message.edit_text("❌ No clients found.")
        return ConversationHandler.END

    message = "📋 *Client List:*\n\n"
    for i, (name, phone, children, package, visits_left, expire_date, client_id, password) in enumerate(clients, 1):
        formatted_date = expire_date.strftime("%d/%m/%Y") if expire_date else "—"
        message += (
            f"{i}. 👤 *{name}* — {children} children\n"
            f"   📞 Phone number: {phone}\n"
            f"   🔑 ID: `{client_id}` | Password: `{password}`\n"
            f"   📦 {package} visits, {visits_left} left, ⏳ until {formatted_date}\n\n"
        )

    await query.message.edit_text(message, parse_mode="Markdown")

    keyboard = [
        [InlineKeyboardButton("➕ Add Client", callback_data="add_client")],
        [InlineKeyboardButton("📋 List Clients", callback_data="list_clients")],
        [InlineKeyboardButton("📊 Available Slots", callback_data="available_slots")],
        [InlineKeyboardButton("📥 Offline Client", callback_data="offline_superuser")]
    ]
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="🔁 Choose next action:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END

# Step 1: Get client name
async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    set_session_value(user_id, "name", update.message.text.strip())
    await update.message.reply_text("Enter phone number:")
    return PHONE

# Step 2: Get phone number
async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    set_session_value(user_id, "phone", update.message.text.strip())
    await update.message.reply_text("How many children?")
    return CHILDREN

# Step 3: Get number of children
async def get_children(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        children = int(update.message.text.strip())
        set_session_value(user_id, "children", children)
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid number.")
        return CHILDREN

    keyboard = [
        [InlineKeyboardButton("8 Visits", callback_data="8")],
        [InlineKeyboardButton("10 Visits", callback_data="10")],
        [InlineKeyboardButton("12 Visits", callback_data="12")]
    ]
    await update.message.reply_text("Choose package:", reply_markup=InlineKeyboardMarkup(keyboard))
    return PACKAGE

# Step 4: Select package
async def get_package(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.callback_query.answer()

    try:
        package = int(update.callback_query.data)
        name = get_session_value(user_id, "name")
        phone = get_session_value(user_id, "phone")
        children = get_session_value(user_id, "children")

        if not all([name, phone, children]):
            await update.callback_query.message.edit_text("⚠️ Session expired or invalid. Please /start again.")
            return ConversationHandler.END

        client_id, password, start, expire = add_client(name, phone, children, package)

        await update.callback_query.message.edit_text(
            f"✅ Client added!\nID: `{client_id}`\nPassword: `{password}`\nValid till: {expire}",
            parse_mode="Markdown"
        )

    finally:
        clear_session_keys(user_id, ["name", "phone", "children"])

    keyboard = [
        [InlineKeyboardButton("➕ Add Client", callback_data="add_client")],
        [InlineKeyboardButton("📋 List Clients", callback_data="list_clients")],
        [InlineKeyboardButton("📊 Available Slots", callback_data="available_slots")],
        [InlineKeyboardButton("📥 Offline Client", callback_data="offline_superuser")]
    ]
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="🔁 Choose next action:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END

async def show_available_slots(update, context):
    query = update.callback_query
    await query.answer()
    context.user_data["slot_page"] = 0
    return await send_slot_page(update, context)

async def send_slot_page(update, context):
    page = context.user_data.get("slot_page", 0)
    today = datetime.today()
    start = page * DAYS_PER_PAGE
    end = start + DAYS_PER_PAGE
    message = f"📊 *Available Slots — Days {start + 1} to {end}*\n\n"

    for i in range(start, end):
        current_day = today + timedelta(days=i)
        formatted_day = current_day.strftime("%d/%m/%Y")
        message += f"📅 *{formatted_day}*\n"
        shown = set()
        for period, max_cap in all_periods.items():
            if period in shown:
                continue
            shown.add(period)
            booked = count_bookings_for_period(current_day.date(), period)
            available = max_cap - booked
            message += f"{period} — {booked} booked/{available} available\n"
    message += f"\n📄 *Page {page + 1} of {MAX_PAGES}*"

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("◀️ Prev", callback_data="slot_prev"))
    if page < MAX_PAGES - 1:
        nav_row.append(InlineKeyboardButton("Next ▶️", callback_data="slot_next"))

    buttons = []
    if nav_row:
        buttons.append(nav_row)
    buttons.append([InlineKeyboardButton("🔁 Back to Menu", callback_data="back_to_menu")])

    keyboard = InlineKeyboardMarkup(buttons)

    try:
        await update.callback_query.edit_message_text(
            message, parse_mode="Markdown", reply_markup=keyboard
        )
    except Exception as e:
        if "Message is not modified" not in str(e):
            await update.callback_query.answer("⚠️ Unable to update. Please try again.", show_alert=True)

    return ConversationHandler.END

async def slot_next(update, context):
    context.user_data["slot_page"] = context.user_data.get("slot_page", 0) + 1
    return await send_slot_page(update, context)

async def slot_prev(update, context):
    context.user_data["slot_page"] = max(0, context.user_data.get("slot_page", 0) - 1)
    return await send_slot_page(update, context)

async def admin_manual_book(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        _, date_str, time_period = query.data.split("_", 2)
        visit_date = datetime.strptime(date_str, "%d-%m-%Y").date()

        dummy_client_id = "admin_manual"
        dummy_visit_number = 0

        decrement_visit(dummy_client_id, dummy_visit_number, visit_date, time_period)
        await query.answer("✅ Slot booked manually!", show_alert=True)
        await show_available_slots(update, context)
    except Exception as e:
        await query.answer(f"❌ Error: {str(e)}", show_alert=True)

async def admin_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("➕ Add Client", callback_data="add_client")],
        [InlineKeyboardButton("📋 List Clients", callback_data="list_clients")],
        [InlineKeyboardButton("📊 Available Slots", callback_data="available_slots")]
    ]
    await update.message.reply_text(
        "❌ Canceled. Choose next action:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )