import logging
import os
import yt_dlp
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- Configuration ---
# Get your bot token from environment variables for security
TOKEN = os.environ.get("8051480351:AAEVeFG1ch9ZW-bJTgaAAWspUh646LsrnSI", "8051480351:AAEVeFG1ch9ZW-bJTgaAAWspUh646LsrnSI") # Fallback for local testing

# Enable logging
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
        f"➡️ **To download a video:** Just send me the link.\n"
        f"➡️ **To download audio only:** Send /audio <link>\n\n"
        f"Powered by yt-dlp."
    )

async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles video download requests based on a direct link."""
    await process_download(update, context, is_video=True)

async def download_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles audio download requests from the /audio command."""
    await process_download(update, context, is_video=False)


# --- Core Download Logic ---

async def process_download(update: Update, context: ContextTypes.DEFAULT_TYPE, is_video: bool) -> None:
    """A unified function to process both video and audio downloads."""
    
    # Check if the message is from the /audio command or a direct link
    if is_video:
        url = update.message.text
    else: # From /audio command
        if not context.args:
            await update.message.reply_text("Please provide a link after the /audio command.\nExample: /audio https://youtu.be/dQw4w9WgXcQ")
            return
        url = context.args[0]
        
    message = await update.message.reply_text("🔗 Processing your link...")

    try:
        # Create a downloads directory if it doesn't exist
        if not os.path.exists('downloads'):
            os.makedirs('downloads')

        # --- yt-dlp Configuration ---
        if is_video:
            ydl_opts = {
                'format': 'best[ext=mp4][height<=720]/best[ext=mp4]/best',
                'outtmpl': 'downloads/%(title)s.%(ext)s',
                'noplaylist': True,
                'max_filesize': 50 * 1024 * 1024, # 50MB
                'logger': logger,
                'progress_hooks': [lambda d: None],
            }
        else: # Audio options
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': 'downloads/%(title)s.%(ext)s',
                'noplaylist': True,
                'max_filesize': 50 * 1024 * 1024, # 50MB
                'logger': logger,
                'progress_hooks': [lambda d: None],
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192', # 192 kbps
                }],
            }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            await message.edit_text("📥 Downloading, please wait...")
            info = ydl.extract_info(url, download=True)
            # The filename after post-processing might change (e.g., .webm to .mp3)
            # So, we build the expected path.
            base_filename = ydl.prepare_filename(info).rsplit('.', 1)[0]
            expected_ext = 'mp3' if not is_video else info.get('ext')
            filename = f"{base_filename}.{expected_ext}"
        
        # Check if the file exists, sometimes post-processing fails silently
        if not os.path.exists(filename):
             raise FileNotFoundError("Could not find the final downloaded file. It might have been too large or an error occurred during conversion.")

        await message.edit_text("⬆️ Uploading to Telegram...")

        # Send the correct file type
        if is_video:
            await update.message.reply_video(video=open(filename, 'rb'), caption=info.get('title', 'Downloaded Video'))
        else:
            await update.message.reply_audio(audio=open(filename, 'rb'), title=info.get('title', 'Downloaded Audio'), performer=info.get('uploader', ''))
        
        os.remove(filename)
        await message.delete()

    except yt_dlp.utils.DownloadError as e:
        logger.error(f"Download error for URL {url}: {e}")
        await message.edit_text(
            f"Sorry, I couldn't download from that link. It might be unsupported, private, or the file is too large (>50MB).\n\n"
        )
    except Exception as e:
        logger.error(f"An unexpected error occurred for URL {url}: {e}")
        await message.edit_text(f"An unexpected error occurred: {e}")

# --- Main Bot Runner ---

def main() -> None:
    """Start the bot."""
    if TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        logger.error("!!! BOT TOKEN NOT SET! Please set your bot token in the code or as an environment variable. !!!")
        return

    application = Application.builder().token(TOKEN).build()

    # --- Add Handlers ---
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("audio", download_audio)) # New handler for /audio
    
    link_filter = filters.TEXT & ~filters.COMMAND & (filters.Regex(r'http[s]?://'))
    application.add_handler(MessageHandler(link_filter, download_video))

    logger.info("Bot is starting...")
    application.run_polling()

if __name__ == "__main__":
    main()