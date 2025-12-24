import os
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import yt_dlp
import asyncio

# Bot token from BotFather
BOT_TOKEN = "7517008297:AAH8BKochtPctbRLa3PVZneJmaRct_RwWH0"

# Download directory
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def extract_video_id(url):
    """Extract video ID from YouTube URL"""
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/shorts\/)([^&\n?#]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def get_video_info(url):
    """Get video information without downloading"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'cookiefile': 'www.youtube.com_cookies.txt',
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'web'],
                'skip': ['hls', 'dash']
            }
        },
        'http_headers': {
            'User-Agent': 'com.google.android.youtube/17.36.4 (Linux; U; Android 12; GB) gzip',
            'Accept-Language': 'en-US,en;q=0.9',
        }
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info
    except Exception as e:
        print(f"Error getting video info: {e}")
        return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    welcome_message = (
        "🎥 *YouTube Video Downloader Bot*\n\n"
        "Send me any YouTube link (video or shorts) and I'll help you download it!\n\n"
        "Features:\n"
        "• Video preview\n"
        "• Multiple quality options\n"
        "• Audio extraction (M4A)\n"
        "• Fast downloads\n\n"
        "Just send a YouTube link to get started!"
    )
    await update.message.reply_text(welcome_message, parse_mode='Markdown')

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle YouTube URL"""
    url = update.message.text.strip()
    
    # Validate YouTube URL
    video_id = extract_video_id(url)
    if not video_id:
        await update.message.reply_text("❌ Invalid YouTube URL. Please send a valid YouTube video or shorts link.")
        return
    
    # Send processing message
    processing_msg = await update.message.reply_text("⏳ Processing your request...")
    
    try:
        # Get video information
        info = get_video_info(url)
        if not info:
            await processing_msg.edit_text("❌ Failed to fetch video information. Please try again.")
            return
        
        # Extract video details
        title = info.get('title', 'Unknown')
        duration = info.get('duration', 0)
        thumbnail = info.get('thumbnail', '')
        uploader = info.get('uploader', 'Unknown')
        view_count = info.get('view_count', 0)
        
        # Format duration
        minutes, seconds = divmod(duration, 60)
        duration_str = f"{int(minutes)}:{int(seconds):02d}"
        
        # Format view count
        if view_count >= 1000000:
            views_str = f"{view_count/1000000:.1f}M"
        elif view_count >= 1000:
            views_str = f"{view_count/1000:.1f}K"
        else:
            views_str = str(view_count)
        
        # Create caption
        caption = (
            f"🎬 *{title}*\n\n"
            f"👤 Channel: {uploader}\n"
            f"⏱ Duration: {duration_str}\n"
            f"👁 Views: {views_str}\n\n"
            f"Choose download option:"
        )
        
        # Create inline keyboard with quality options
        keyboard = [
            [InlineKeyboardButton("🎥 Best Quality (MP4)", callback_data=f"best_{video_id}")],
            [InlineKeyboardButton("📹 High Quality (720p)", callback_data=f"720_{video_id}")],
            [InlineKeyboardButton("📱 Medium Quality (480p)", callback_data=f"480_{video_id}")],
            [InlineKeyboardButton("🎵 Audio Only (M4A)", callback_data=f"mp3_{video_id}")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Send thumbnail with options
        if thumbnail:
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=thumbnail,
                caption=caption,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=caption,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        
        # Delete processing message
        await processing_msg.delete()
        
        # Store URL in context for callback
        context.user_data[video_id] = url
        
    except Exception as e:
        await processing_msg.edit_text(f"❌ Error: {str(e)}")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()
    
    # Parse callback data
    data = query.data
    quality, video_id = data.split('_', 1)
    
    # Get URL from context
    url = context.user_data.get(video_id)
    if not url:
        await query.edit_message_caption(caption="❌ Session expired. Please send the link again.")
        return
    
    # Send downloading message
    await query.edit_message_caption(caption=f"⬇️ Downloading... Please wait.")
    
    try:
        # Configure download options based on quality
        base_opts = {
            'outtmpl': os.path.join(DOWNLOAD_DIR, f'{video_id}.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'cookiefile': 'www.youtube.com_cookies.txt',
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'ios', 'web'],
                    'skip': ['hls', 'dash']
                }
            },
            'http_headers': {
                'User-Agent': 'com.google.android.youtube/17.36.4 (Linux; U; Android 12; GB) gzip',
                'Accept-Language': 'en-US,en;q=0.9',
            }
        }
        
        if quality == 'mp3':
            ydl_opts = {
                **base_opts,
                'format': 'bestaudio[ext=m4a]/bestaudio/best',
            }
            file_ext = 'm4a'
        elif quality == 'best':
            ydl_opts = {
                **base_opts,
                'format': 'bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            }
            file_ext = 'mp4'
        elif quality == '720':
            ydl_opts = {
                **base_opts,
                'format': 'bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best',
            }
            file_ext = 'mp4'
        else:  # 480p
            ydl_opts = {
                **base_opts,
                'format': 'bestvideo[ext=mp4][height<=480]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best',
            }
            file_ext = 'mp4'
        
        # Download video
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'video')
        
        # Find downloaded file
        file_path = None
        for file in os.listdir(DOWNLOAD_DIR):
            if file.startswith(video_id):
                file_path = os.path.join(DOWNLOAD_DIR, file)
                break
        
        if not file_path or not os.path.exists(file_path):
            await query.edit_message_caption(caption="❌ Download failed. File not found.")
            return
        
        # Check file size
        file_size = os.path.getsize(file_path)
        max_size = 50 * 1024 * 1024  # 50MB Telegram limit
        
        if file_size > max_size:
            await query.edit_message_caption(
                caption=f"❌ File too large ({file_size/1024/1024:.1f}MB). Telegram limit is 50MB.\nTry a lower quality option."
            )
            os.remove(file_path)
            return
        
        # Upload file
        await query.edit_message_caption(caption="⬆️ Uploading... Please wait.")
        
        if quality == 'mp3':
            await context.bot.send_audio(
                chat_id=update.effective_chat.id,
                audio=open(file_path, 'rb'),
                title=title,
                caption="✅ Downloaded successfully!"
            )
        else:
            await context.bot.send_video(
                chat_id=update.effective_chat.id,
                video=open(file_path, 'rb'),
                caption="✅ Downloaded successfully!",
                supports_streaming=True
            )
        
        # Delete the file after sending
        os.remove(file_path)
        
        # Update message
        await query.edit_message_caption(caption="✅ Download complete! Check the file above.")
        
    except Exception as e:
        await query.edit_message_caption(caption=f"❌ Error during download: {str(e)}")
        # Clean up any partial downloads
        for file in os.listdir(DOWNLOAD_DIR):
            if file.startswith(video_id):
                try:
                    os.remove(os.path.join(DOWNLOAD_DIR, file))
                except:
                    pass

def main():
    """Start the bot"""
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Start bot
    print("🤖 Bot is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
