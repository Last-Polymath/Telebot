import logging
import os
import yt_dlp
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- Configuration ---
# Get your bot token from environment variables for security
TOKEN = os.environ.get("7136286649:AAEcL6C2OcURC26hLQEiBSA0GExpDoLgA8w", "7136286649:AAEcL6C2OcURC26hLQEiBSA0GExpDoLgA8w") # Fallback for local testing

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
            # --- KEY CHANGES FOR VIDEO ---
            # 1. Format is set to download the best possible video and audio streams and merge them.
            # 2. 'max_filesize' is removed to allow downloading files of any size.
            ydl_opts = {
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'outtmpl': 'downloads/%(title)s.%(ext)s',
                'noplaylist': True,
                'logger': logger,
                'progress_hooks': [lambda d: None],
                'merge_output_format': 'mp4', # Ensures the final merged file is an MP4
            }
        else: # Audio options remain the same
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': 'downloads/%(title)s.%(ext)s',
                'noplaylist': True,
                'max_filesize': 50 * 1024 * 1024, # 50MB limit is fine for audio
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
            
            base_filename = ydl.prepare_filename(info).rsplit('.', 1)[0]
            # Set expected extension based on the processing type
            expected_ext = 'mp4' if is_video else 'mp3'
            filename = f"{base_filename}.{expected_ext}"
        
        # Check if the file exists, as errors can sometimes be silent
        if not os.path.exists(filename):
             raise FileNotFoundError("Could not find the final downloaded file. An error might have occurred during conversion.")

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
            f"Sorry, I couldn't download from that link. It might be unsupported, private, or too large for Telegram to handle.\n\n"
        )
    except Exception as e:
        logger.error(f"An unexpected error occurred for URL {url}: {e}")
        await message.edit_text(f"An unexpected error occurred: {e}")

# --- Main Bot Runner ---

def main() -> None:
    """Start the bot."""
    if TOKEN == "YOUR_TELEGRAM_BOT_TOKEN": # Generic check for a placeholder token
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
