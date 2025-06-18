from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def append_back_button(keyboard_rows, include_back=True):
    if include_back:
        keyboard_rows.append([InlineKeyboardButton("🔁 Вернуться в меню", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(keyboard_rows)
