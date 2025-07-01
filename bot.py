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
    """Sends a welcome message."""
    user = update.effective_user
    await update.message.reply_html(
        rf"Hi {user.mention_html()}! 👋",
        f"I am your personal media downloader bot.\n\n"
        f"Just send me any link from a supported website, and I'll ask you what quality you want to download.\n\n"
        f"Powered by yt-dlp."
    )

# --- Message and Callback Handlers ---

async def ask_for_quality(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Receives a link and asks the user for the desired quality with inline buttons."""
    url = update.message.text
    if not (url.startswith('http://') or url.startswith('https://')):
        await update.message.reply_text("Please send a valid link.")
        return

    # Create the inline keyboard buttons
    keyboard = [
        [InlineKeyboardButton("📹 Highest Video", callback_data=f"video|{url}")],
        [InlineKeyboardButton("🎵 Highest Audio (MP3)", callback_data=f"audio|{url}")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text('What quality would you like to download?', reply_markup=reply_markup)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Parses the CallbackQuery and starts the download."""
    query = update.callback_query
    await query.answer() # Acknowledge the button press

    # The callback_data is in the format "action|url"
    action, url = query.data.split('|', 1)

    is_video = (action == 'video')
    
    # Let the user know the process has started
    await query.edit_message_text(text=f"Request received! Starting download for {action}...")
    
    await process_download(update, context, url, is_video, query.message)

# --- Core Download Logic ---

async def process_download(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str, is_video: bool, original_message) -> None:
    """Unified function to process downloads."""
    try:
        if not os.path.exists('downloads'):
            os.makedirs('downloads')

        ydl_opts = {
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'noplaylist': True,
            'max_filesize': 50 * 1024 * 1024, # 50MB Telegram limit
            'logger': logger,
            'progress_hooks': [lambda d: None],
        }

        if is_video:
            # We no longer restrict resolution, but yt-dlp will pick the best single file < 50MB
            ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        else: # Audio
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
            ydl_opts['keepvideo'] = False
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            await original_message.edit_text("📥 Downloading & Converting, please wait...")
            info = ydl.extract_info(url, download=True)
            
            base_filename, _ = os.path.splitext(ydl.prepare_filename(info))
            final_ext = 'mp3' if not is_video else info.get('ext', 'mp4')
            filename = f"{base_filename}.{final_ext}"

        if not os.path.exists(filename):
            raise FileNotFoundError("Could not find the final downloaded file.")

        await original_message.edit_text("⬆️ Uploading to Telegram...")

        caption = info.get('title', 'Downloaded Media')
        if is_video:
            await context.bot.send_video(chat_id=update.effective_chat.id, video=open(filename, 'rb'), caption=caption, write_timeout=120)
        else:
            await context.bot.send_audio(chat_id=update.effective_chat.id, audio=open(filename, 'rb'), title=caption, performer=info.get('uploader', ''), write_timeout=120)
        
        os.remove(filename)
        await original_message.delete()

    except yt_dlp.utils.DownloadError as e:
        error_message = str(e).split(': ERROR: ')[-1]
        logger.error(f"Download error for URL {url}: {error_message}")
        await original_message.edit_text(
            f"Sorry, I couldn't download from that link.\n\n*Reason:* `{escape_markdown(error_message, version=2)}`",
            parse_mode='MarkdownV2'
        )
    except Exception as e:
        logger.error(f"An unexpected error occurred for URL {url}: {e}")
        await original_message.edit_text(f"An unexpected error occurred: {e}")

# --- Main Bot Runner ---

def main() -> None:
    """Start the bot."""
    if TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        logger.error("!!! BOT TOKEN NOT SET! Please set your bot token in the code or as an environment variable. !!!")
        return

    application = Application.builder().token(TOKEN).build()

    # --- Add Handlers ---
    application.add_handler(CommandHandler("start", start))
    
    # Handles any link sent to the bot
    link_filter = filters.TEXT & ~filters.COMMAND & (filters.Regex(r'http[s]?://'))
    application.add_handler(MessageHandler(link_filter, ask_for_quality))

    # Handles button clicks
    application.add_handler(CallbackQueryHandler(button_handler))

    logger.info("Bot is starting with interactive quality selection...")
    application.run_polling()

if __name__ == "__main__":
    main()
