import os
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.environ.get('BOT_TOKEN', "BU_YERGA_TOKENINGIZNI_QOYING")
SERVER_URL = os.environ.get('SERVER_URL', 'http://localhost:8080')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "♟ Shashka botiga xush kelibsiz!\n\n"
        "/newgame — yangi o'yin boshlash"
    )

async def new_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text("⏳ O'yin yaratilmoqda...")

    async with aiohttp.ClientSession() as session:
        async with session.get(f'{SERVER_URL}/create') as resp:
            data = await resp.json()

    game_id = data['game_id']
    base_url = data['url']

    red_url = f"{base_url}?color=r"
    white_url = f"{base_url}?color=w"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔴 Qizil sifatida o'ynash", url=red_url)],
        [InlineKeyboardButton("⚪ Oq sifatida o'ynash", url=white_url)],
    ])

    msg = (
        f"🎮 O'yin tayyor! ID: `{game_id}`\n\n"
        f"@{user.username or user.first_name} o'yin yaratdi!\n\n"
        f"🔴 Siz qizilni tanlang\n"
        f"⚪ Do'stingizga oq linkini yuboring:\n\n"
        f"`{white_url}`\n\n"
        f"Ikkovingiz kirganingizdan so'ng o'yin boshlanadi!"
    )

    await update.message.reply_text(msg, reply_markup=keyboard, parse_mode='Markdown')

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("newgame", new_game))
    print("Bot ishlamoqda...")
    app.run_polling()

if __name__ == "__main__":
    main()
