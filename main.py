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
from admin import admin_buttons, list_clients, get_name, get_children, get_package, admin_cancel, NAME, CHILDREN, PACKAGE
from user import client_start, get_client_id, get_client_password, visit_button_handler, client_cancel, LOGIN_ID, LOGIN_PASSWORD, VISIT
from db import init_db
from config import ADMIN_ID, BOT_TOKEN

init_db()


admin_conv = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(admin_buttons, pattern="^add_client$")
    ],
    states={
        NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
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
        VISIT: [CallbackQueryHandler(visit_button_handler)],
    },
    fallbacks=[CommandHandler("cancel", client_cancel)]
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)

    if user_id == str(ADMIN_ID):
        # Admin: show buttons
        keyboard = [
            [InlineKeyboardButton("➕ Add Client", callback_data="add_client")],
            [InlineKeyboardButton("📋 List Clients", callback_data="list_clients")]
        ]
        await update.message.reply_text("👋 Welcome Admin!", reply_markup=InlineKeyboardMarkup(keyboard))
        return 

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start)) 
    app.add_handler(admin_conv, group=0)
    app.add_handler(CallbackQueryHandler(list_clients, pattern="^list_clients$"), group=0)
    app.add_handler(client_conv, group=1)
    print("✅ Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()