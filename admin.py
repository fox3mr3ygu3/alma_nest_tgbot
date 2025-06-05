from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from db import add_client, get_all_clients
from config import ADMIN_ID
from telegram.error import BadRequest

# Conversation states
NAME, CHILDREN, PACKAGE = range(3)
admin_temp_data = {}




#  Shows admin menu again (used after callback button clicks)
async def admin_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "add_client":
        # Ask for name — start conversation manually
        await query.message.edit_text("Enter client name:")
        return NAME

    elif query.data == "list_clients":
        # Placeholder — do whatever listing should do
        await query.message.edit_text("📋 Listing clients coming soon...")
        return ConversationHandler.END

    # Show default buttons again (if something unknown)
    keyboard = [
        [InlineKeyboardButton("➕ Add Client", callback_data="add_client")],
        [InlineKeyboardButton("📋 List Clients", callback_data="list_clients")]
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
    for i, (name, children, package, visits_left, expire_date) in enumerate(clients, 1):
        formatted_date = expire_date.strftime("%d/%m/%Y")
        message += (
            f"{i}. 👤 *{name}* — {children} children\n"
            f"   📦 {package} visits, {visits_left} left, ⏳ until {formatted_date}\n\n"
        )

    await query.message.edit_text(message, parse_mode="Markdown")
    return ConversationHandler.END


# Step 1: Get client name
async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_temp_data[update.effective_user.id] = {"name": update.message.text}
    await update.message.reply_text("How many children?")
    return CHILDREN

# Step 2: Get children count
async def get_children(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_temp_data[update.effective_user.id]["children"] = int(update.message.text)
    keyboard = [
        [InlineKeyboardButton("8 Visits", callback_data="8")],
        [InlineKeyboardButton("10 Visits", callback_data="10")],
        [InlineKeyboardButton("12 Visits", callback_data="12")]
    ]
    await update.message.reply_text("Choose package:", reply_markup=InlineKeyboardMarkup(keyboard))
    return PACKAGE

# Step 3: Select package and finalize client creation
async def get_package(update: Update, context: ContextTypes.DEFAULT_TYPE):
    package = int(update.callback_query.data)
    data = admin_temp_data.get(update.effective_user.id, {})
    client_id, password, start, expire = add_client(
        data["name"], data["children"], package
    )
    await update.callback_query.answer()
    await update.callback_query.message.edit_text(
        f"✅ Client added!\nID: `{client_id}`\nPassword: `{password}`\nValid till: {expire}",
        parse_mode="Markdown"
    )
    return ConversationHandler.END

# Cancel command
async def admin_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Admin process canceled.")
    return ConversationHandler.END
