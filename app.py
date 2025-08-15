import os
import tempfile
import re
from fastapi import FastAPI, Request
from telegram import Bot, Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes, ApplicationBuilder, MessageHandler, filters
import asyncio

TOKEN = "7984661913:AAGkyFxtLchakz5mH1yXZ2_pdXnxrvQQyZQ"
bot = Bot(token=TOKEN)
fastapi_app = FastAPI()  # renamed to avoid conflict

async def download_instagram(update: Update, context: ContextTypes.DEFAULT_TYPE = None):
    url = update.message.text.strip() if update.message.text else ""
    if not url:
        await bot.send_message(
            chat_id=update.message.chat.id,
            text="❗ *Please send an Instagram post, reel, or story link.*\n\n📥 Just paste the link here and I'll grab the media for you!",
            parse_mode="Markdown"
        )
        return

    await bot.send_chat_action(chat_id=update.message.chat.id, action=ChatAction.TYPING)
    await bot.send_message(
        chat_id=update.message.chat.id,
        text="🔗 *Link received!*\n⏳ _Fetching your Instagram content..._\nPlease wait while I grab the media. 🚀",
        parse_mode="Markdown"
    )

    try:
        import instaloader
    except ImportError:
        await bot.send_message(
            chat_id=update.message.chat.id,
            text="❌ Instaloader module not found!\n\n🔧 Please install it using:\n`pip install instaloader`",
            parse_mode="Markdown"
        )
        return

    try:
        L = instaloader.Instaloader(
            dirname_pattern="{target}",
            save_metadata=False,
            download_comments=False,
            post_metadata_txt_pattern=""
        )
        # --- NEW: Load session file if available ---
        SESSIONFILE = os.getenv("INSTALOADER_SESSIONFILE")
        if SESSIONFILE and os.path.exists(SESSIONFILE):
            try:
                L.load_session_from_file(os.getenv("INSTAGRAM_USERNAME", ""), SESSIONFILE)
            except Exception as session_err:
                await bot.send_message(
                    chat_id=update.message.chat.id,
                    text=f"❌ Failed to load Instagram session!\n\n_Error:_ `{session_err}`",
                    parse_mode="Markdown"
                )
                return
        # --- END NEW ---
        with tempfile.TemporaryDirectory() as tmpdirname:
            L.dirname_pattern = tmpdirname
            m = re.search(r"instagram\.com/(?:reel|p|tv|stories)/([A-Za-z0-9_\-]+)/?", url)
            if not m:
                await bot.send_message(
                    chat_id=update.message.chat.id,
                    text="⚠️ *Invalid URL!*\nPlease send a valid Instagram post, reel, or story link. 🔗",
                    parse_mode="Markdown"
                )
                return
            shortcode = m.group(1)
            await bot.send_chat_action(chat_id=update.message.chat.id, action=ChatAction.TYPING)
            await bot.send_message(chat_id=update.message.chat.id, text="📡 Connecting to Instagram...")
            post = instaloader.Post.from_shortcode(L.context, shortcode)
            await bot.send_chat_action(chat_id=update.message.chat.id, action=ChatAction.UPLOAD_DOCUMENT)
            await bot.send_message(chat_id=update.message.chat.id, text="📥 Downloading media files...")
            L.download_post(post, target=shortcode)
            files = [
                os.path.join(tmpdirname, f)
                for f in os.listdir(tmpdirname)
                if f.endswith(('.mp4', '.jpg', '.jpeg', '.png'))
            ]
            if not files:
                await bot.send_message(chat_id=update.message.chat.id, text="😔 Sorry, I couldn't find any media in this post.")
                return
            for file_path in files:
                with open(file_path, "rb") as f:
                    if file_path.endswith('.mp4'):
                        await bot.send_chat_action(chat_id=update.message.chat.id, action=ChatAction.UPLOAD_VIDEO)
                        await bot.send_video(chat_id=update.message.chat.id, video=f, caption="🎬 Here's your Instagram *video*! Enjoy! 😎", parse_mode="Markdown")
                    else:
                        await bot.send_chat_action(chat_id=update.message.chat.id, action=ChatAction.UPLOAD_PHOTO)
                        await bot.send_photo(chat_id=update.message.chat.id, photo=f, caption="🖼️ Here's your Instagram *photo*!", parse_mode="Markdown")
            await bot.send_message(chat_id=update.message.chat.id, text="✅ *Done!* If you want to download more, just send another link. ✨", parse_mode="Markdown")
    except Exception as e:
        await bot.send_message(chat_id=update.message.chat.id, text=f"❌ *Download failed!*\n\n_Error:_ `{e}`", parse_mode="Markdown")

@fastapi_app.post("/webhook")
async def telegram_webhook(req: Request):
    try:
        data = await req.json()
        update = Update.de_json(data, bot)
        if update.message and update.message.text:
            await download_instagram(update)
        return {"ok": True}
    except Exception as e:
        if update and update.message:
            await update.message.reply_text(f"❌ *Download failed!*\n\n_Error:_ `{e}`", parse_mode="Markdown")
        return {"ok": False, "error": str(e)}

# Start the bot (polling mode)
tg_app = ApplicationBuilder().token(TOKEN).build()
tg_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), download_instagram))

print("🤖 Instagram Bot is running.")
tg_app.run_polling()
