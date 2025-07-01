import logging
import os
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.helpers import escape_markdown

# --- Configuration ---
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN") 
# Path to the cookie file on the Raspberry Pi
COOKIE_FILE_PATH = "/home/pi/Telebot/instagram_cookies.txt"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Command Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_html(
        rf"Hi {user.mention_html()}! 👋",
        f"I am your personal media downloader bot.\n\n"
        f"I can download from many sites, including Instagram stories (if you've set me up with cookies!).\n\n"
        f"Just send me a link."
    )

# --- Message and Callback Handlers ---

async def ask_for_quality(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    url = update.message.text
    if not (url.startswith('http://') or url.startswith('https://')):
        await update.message.reply_text("Please send a valid link.")
        return

    keyboard = [
        [InlineKeyboardButton("📹 Highest Video", callback_data=f"video|{url}")],
        [InlineKeyboardButton("🎵 Highest Audio (MP3)", callback_data=f"audio|{url}")],
    ]
    # Add a special button for Instagram profile links to fetch stories
    if "instagram.com/" in url and "/p/" not in url and "/reel/" not in url:
        keyboard.append([InlineKeyboardButton("📖 Instagram Stories", callback_data=f"stories|{url}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('What would you like to download?', reply_markup=reply_markup)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    action, url = query.data.split('|', 1)
    
    await query.edit_message_text(text=f"Request received! Starting download for {action}...")
    
    await process_download(update, context, url, action, query.message)

# --- Core Download Logic ---

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
        }

        # Add cookies if the file exists, essential for Instagram
        if os.path.exists(COOKIE_FILE_PATH):
            ydl_opts['cookiefile'] = COOKIE_FILE_PATH

        if action == 'video':
            ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
            ydl_opts['noplaylist'] = True
        elif action == 'audio':
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]
            ydl_opts['keepvideo'] = False
            ydl_opts['noplaylist'] = True
        elif action == 'stories':
            # For stories, we want the whole playlist of stories
            ydl_opts['format'] = 'best'
            ydl_opts['noplaylist'] = False # This is key for stories
        
        downloaded_files = []
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            await original_message.edit_text("📥 Downloading, please wait...")
            info = ydl.extract_info(url, download=True)
            
            # Handle single files vs playlists (like stories)
            if 'entries' in info:
                # Playlist or multiple items
                for entry in info['entries']:
                    filename = ydl.prepare_filename(entry)
                    downloaded_files.append(filename)
            else:
                # Single file
                filename = ydl.prepare_filename(info)
                downloaded_files.append(filename)

        await original_message.edit_text(f"Downloaded {len(downloaded_files)} item(s). Now uploading...")

        for i, filename in enumerate(downloaded_files):
            if not os.path.exists(filename):
                logger.warning(f"File not found after download: {filename}")
                continue
            
            await original_message.edit_text(f"⬆️ Uploading item {i+1} of {len(downloaded_files)}...")
            
            # Check if it's a video or photo to use the correct sender
            if filename.endswith(('.mp4', '.mov', '.webm')):
                 await context.bot.send_video(chat_id=update.effective_chat.id, video=open(filename, 'rb'), write_timeout=120)
            elif filename.endswith(('.jpg', '.jpeg', '.png', '.webp')):
                 await context.bot.send_photo(chat_id=update.effective_chat.id, photo=open(filename, 'rb'))
            else: # Send as a document for any other type (like mp3)
                 await context.bot.send_document(chat_id=update.effective_chat.id, document=open(filename, 'rb'))

            os.remove(filename)

        await original_message.delete()

    except Exception as e:
        error_message = str(e)
        logger.error(f"An error occurred for URL {url}: {error_message}")
        await original_message.edit_text(f"An error occurred: {escape_markdown(error_message, version=2)}", parse_mode='MarkdownV2')


# --- Main Bot Runner ---

def main() -> None:
    if TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        logger.error("!!! BOT TOKEN NOT SET !!!")
        return

    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    link_filter = filters.TEXT & ~filters.COMMAND & (filters.Regex(r'http[s]?://'))
    application.add_handler(MessageHandler(link_filter, ask_for_quality))
    application.add_handler(CallbackQueryHandler(button_handler))

    logger.info("Bot is starting...")
    application.run_polling()

if __name__ == "__main__":
    main()
