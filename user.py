from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from db import validate_password, decrement_visit, get_client
from config import ADMIN_ID
from datetime import datetime

# Conversation states
LOGIN_ID, LOGIN_PASSWORD, VISIT = range(3)

# Temporary session storage for clients
client_session = {}

async def client_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) == str(ADMIN_ID):
        return ConversationHandler.END  # don't enter client flow for admin

    await update.message.reply_text("Welcome! Please enter your 4-digit ID:")
    return LOGIN_ID


async def get_client_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    client_id = update.message.text.strip()
    if not client_id.isdigit() or len(client_id) != 4:
        await update.message.reply_text("❌ Invalid ID format. Please enter a 4-digit ID.")
        return LOGIN_ID
    client_session[update.effective_user.id] = {"id": client_id}
    await update.message.reply_text("Now enter your 6-digit password:")
    return LOGIN_PASSWORD


async def get_client_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = client_session.get(update.effective_user.id, {})
    client_id = user_data.get("id")
    password = update.message.text.strip()

    if not password.isdigit() or len(password) != 6:
        await update.message.reply_text("❌ Invalid password format. Please enter a 6-digit password.")
        return LOGIN_PASSWORD

    result = validate_password(client_id, password)
    if result:
        client_info = get_client(client_id)
        package_type = int(client_info[5])         # 8, 10, or 12
        visits_remaining = int(client_info[6])     # Current visits left
        full_name = client_info[3]
        expire_raw = client_info[8]
        expire_date = datetime.strptime(str(expire_raw), "%Y-%m-%d").strftime("%d/%m/%Y")

        used_visits = package_type - visits_remaining

        # Store session info
        client_session[update.effective_user.id]["package"] = package_type

        # Generate remaining visit buttons
        buttons = []
        for i in range(used_visits + 1, package_type + 1):
            buttons.append([InlineKeyboardButton(f"Visit {i}", callback_data=f"visit_{i}")])

        if not buttons:
            await update.message.reply_text("✅ All visits used. Contact admin to renew your package.")
            return ConversationHandler.END

        await update.message.reply_text(
        f"✅ Logged in!\n"
        f"Name: {full_name}\n"
        f"Package: {package_type} visits\n"
        f"Remaining: {visits_remaining}\n"
        f"Expires: {expire_date}\n\n"
        f"Click a button for your next visit:",
        reply_markup=InlineKeyboardMarkup(buttons)
        )
        return VISIT
    else:
        await update.message.reply_text("❌ Invalid ID or password. Please try again with /start.")
        return ConversationHandler.END


async def visit_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    # Get client ID from session
    client_id = client_session.get(user_id, {}).get("id")
    if not client_id:
        await query.message.edit_text("⚠️ Session expired or invalid.")
        return ConversationHandler.END

    # Get latest client info from database
    client_info = get_client(client_id)
    if not client_info:
        await query.message.edit_text("⚠️ Client not found.")
        return ConversationHandler.END

    package_type = int(client_info[5])
    visits_remaining = int(client_info[6])
    used_visits = package_type - visits_remaining

    # Extract which visit button was clicked
    data = query.data
    if not data.startswith("visit_"):
        await query.message.edit_text("⚠️ Invalid visit action.")
        return ConversationHandler.END

    clicked_visit = int(data.split("_")[1])
    expected_visit = used_visits + 1

    # ❗ Block if they clicked out of order
    if clicked_visit != expected_visit:
        await query.message.reply_text(
            f"⚠️ You must use Visit {expected_visit} first before Visit {clicked_visit}."
        )
        return VISIT

    # ✅ Log visit and update database
    decrement_visit(client_id)

    await query.message.delete()

# Send a new success message
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"✅ Visit {clicked_visit} recorded. See you next time!"
    )
    return ConversationHandler.END


async def client_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Canceled.")
    return ConversationHandler.END
