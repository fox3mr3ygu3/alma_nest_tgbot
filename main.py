import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters
)
from admin import admin_buttons, admin_manual_book, show_available_slots, slot_next, slot_prev, list_clients, get_name, get_children, get_package, admin_cancel, get_phone, NAME, CHILDREN, PACKAGE, PHONE
from user import client_start, logout_handler, children_input_handler, select_time_handler, full_handler, ignore_handler, select_day_handler, get_client_id, get_client_password, visit_button_handler, client_cancel, LOGIN_ID, LOGIN_PASSWORD
from superuser import start_superuser_flow, handle_superuser_day, handle_superuser_package, handle_superuser_time, ask_superuser_children, handle_superuser_children, SUPER_CHILDREN
from db import init_db, ensure_superuser, clear_session_keys
from config import ADMIN_ID, BOT_TOKEN
from back_utils import append_back_button


init_db()
ensure_superuser()

admin_conv = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(admin_buttons, pattern="^add_client$")
    ],
    states={
        NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
        PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
        CHILDREN: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_children)],
        PACKAGE: [CallbackQueryHandler(get_package)],
    },
    fallbacks=[CommandHandler("cancel", admin_cancel)],
    allow_reentry=True,
)

client_conv = ConversationHandler(
    entry_points=[CommandHandler("start", client_start)],
    states={
        LOGIN_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_client_id)],
        LOGIN_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_client_password)],
    },
    fallbacks=[CommandHandler("cancel", client_cancel)],
)


async def handle_back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Delete the current inline message to avoid edit errors
    await update.callback_query.message.delete()

    if str(user_id) == str(ADMIN_ID):
        keyboard = [
            [InlineKeyboardButton("➕ Add Client", callback_data="add_client")],
            [InlineKeyboardButton("📋 List Clients", callback_data="list_clients")],
            [InlineKeyboardButton("📊 Available Slots", callback_data="available_slots")],
            [InlineKeyboardButton("📥 Offline Client", callback_data="offline_superuser")]
        ]
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="🔙 Returned to Admin Menu",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        # For regular users, clear session and return to login flow
        clear_session_keys(user_id, ["last_visit", "selected_day", "visit_time"])
        await client_start(update, context)

    return ConversationHandler.END


async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)

    if user_id != str(ADMIN_ID):
        await update.message.reply_text("🚫 You are not authorized.")
        return

    keyboard = [
        [InlineKeyboardButton("➕ Add Client", callback_data="add_client")],
        [InlineKeyboardButton("📋 List Clients", callback_data="list_clients")],
        [InlineKeyboardButton("📊 Available Slots", callback_data="available_slots")],
        [InlineKeyboardButton("📥 Offline Client", callback_data="offline_superuser")]
    ]
    await update.message.reply_text("👋 Welcome Admin!", reply_markup=InlineKeyboardMarkup(keyboard))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)

    if user_id == str(ADMIN_ID):
        # Admin: show buttons
        keyboard = [
            [InlineKeyboardButton("➕ Add Client", callback_data="add_client")],
            [InlineKeyboardButton("📋 List Clients", callback_data="list_clients")],
            [InlineKeyboardButton("📊 Available Slots", callback_data="available_slots")],
            [InlineKeyboardButton("📥 Offline Client", callback_data="offline_superuser")]
        ]
        await update.message.reply_text("👋 Welcome Admin!", reply_markup=InlineKeyboardMarkup(keyboard))
        return 


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("admin", admin_start), group=0)
      # Admin-only conversation
    app.add_handler(admin_conv, group=0)

    # Client login only
    app.add_handler(client_conv, group=0)
    # Global handlers (group=0)
    app.add_handler(CallbackQueryHandler(handle_back_to_menu, pattern="^back_to_menu$"), group=0)
    app.add_handler(CallbackQueryHandler(start_superuser_flow, pattern="^offline_superuser$"), group=0)
    app.add_handler(CallbackQueryHandler(list_clients, pattern="^list_clients$"), group=0)
    app.add_handler(CallbackQueryHandler(show_available_slots, pattern="^available_slots$"), group=0)
    app.add_handler(CallbackQueryHandler(slot_next, pattern="^slot_next$"), group=0)
    app.add_handler(CallbackQueryHandler(slot_prev, pattern="^slot_prev$"), group=0)
    app.add_handler(CallbackQueryHandler(admin_manual_book, pattern="^adminbook_"), group=0)

    # Visit flow (moved outside client_conv)
    app.add_handler(CallbackQueryHandler(visit_button_handler, pattern="^visit_"), group=0)
    app.add_handler(CallbackQueryHandler(select_day_handler, pattern="^day_"), group=0)
    app.add_handler(CallbackQueryHandler(select_time_handler, pattern="^time_"), group=0)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, children_input_handler), group=1)

    # Superuser flow
    app.add_handler(CallbackQueryHandler(handle_superuser_package, pattern="^super_pkg_"), group=0)
    app.add_handler(CallbackQueryHandler(handle_superuser_day, pattern="^super_day_"), group=0)
    app.add_handler(CallbackQueryHandler(handle_superuser_time, pattern="^super_time_"), group=0)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_superuser_children), group=1)

    # Shared handlers
    app.add_handler(CallbackQueryHandler(full_handler, pattern="^full$"), group=0)
    app.add_handler(CallbackQueryHandler(ignore_handler, pattern="^ignore$"), group=0)
    app.add_handler(CommandHandler("logout", logout_handler))
    app.add_handler(CallbackQueryHandler(logout_handler, pattern="^logout$"), group=0)


    print("✅ Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()