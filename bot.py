import logging
import os
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.helpers import escape_markdown

# --- Configuration ---
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Command Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_html(
        rf"Hi {user.mention_html()}! 👋",
        f"I am your personal media downloader bot. Send me any link and I will ask what quality you want."
    )

# --- Message and Callback Handlers ---
async def ask_for_quality(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    url = update.message.text
    if not (url.startswith('http://') or url.startswith('https://')):
        await update.message.reply_text("Please send a valid link.")
        return
        
    # ** THE FIX: Store the URL in the bot's memory for this user **
    context.user_data['last_url'] = url
    
    # The callback_data is now very small, just the action.
    keyboard = [
        [InlineKeyboardButton("📹 Highest Video", callback_data="video")],
        [InlineKeyboardButton("🎵 Highest Audio (MP3)", callback_data="audio")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('What would you like to download?', reply_markup=reply_markup)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    action = query.data
    
    # ** THE FIX: Retrieve the URL from the bot's memory **
    url = context.user_data.get('last_url')
    
    if not url:
        await query.edit_message_text(text="Sorry, I have forgotten the link. Please send it again.")
        return
        
    await query.edit_message_text(text=f"Request received! Starting download for: {action}...")
    await process_download(update, context, url, action, query.message)
    
    # Clean up the stored URL after use
    if 'last_url' in context.user_data:
        del context.user_data['last_url']

# --- Core Download Logic (No changes needed here) ---
async def process_download(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str, action: str, original_message) -> None:
    try:
        downloads_dir = 'downloads'
        if not os.path.exists(downloads_dir):
            os.makedirs(downloads_dir)

        ydl_opts = {
            'outtmpl': os.path.join(downloads_dir, '%(title)s.%(ext)s'),
            'max_filesize': 50 * 1024 * 1024,
            'logger': logger,
            'progress_hooks': [lambda d: None],
            'noplaylist': True,
        }

        if action == 'video':
            ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        else: # Audio
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            await original_message.edit_text("📥 Downloading & Converting, please wait...")
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            if action == 'audio':
                base, _ = os.path.splitext(filename)
                filename = base + '.mp3'

        if not os.path.exists(filename):
            raise FileNotFoundError("Could not find the final downloaded file.")

        await original_message.edit_text("⬆️ Uploading to Telegram...")
        caption = info.get('title', 'Downloaded Media')

        if action == 'video':
            await context.bot.send_video(chat_id=update.effective_chat.id, video=open(filename, 'rb'), caption=caption, write_timeout=120)
        else:
            await context.bot.send_audio(chat_id=update.effective_chat.id, audio=open(filename, 'rb'), title=caption, performer=info.get('uploader', ''), write_timeout=120)

        os.remove(filename)
        await original_message.delete()
    except Exception as e:
        error_message = str(e).split(': ERROR: ')[-1]
        logger.error(f"An error occurred for URL {url}: {error_message}")
        await original_message.edit_text(
            f"Sorry, an error occurred.\n*Reason:* `{escape_markdown(error_message, version=2)}`",
            parse_mode='MarkdownV2'
        )

# --- Main Bot Runner ---
def main() -> None:
    if os.environ.get("IS_LOCAL_DEV"):
        # For local development, use a different token or method
        # For simplicity, we assume the token is set for both environments
        pass

    if not TOKEN:
        logger.error("!!! TELEGRAM_BOT_TOKEN environment variable not set! !!!")
        return

    # To store user data in memory
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    link_filter = filters.TEXT & ~filters.COMMAND & (filters.Regex(r'http[s]?://'))
    application.add_handler(MessageHandler(link_filter, ask_for_quality))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    logger.info("Bot is starting...")
    application.run_polling()

if __name__ == "__main__":
    main()
