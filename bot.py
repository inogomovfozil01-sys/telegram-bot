import os
import yt_dlp
import logging
import time
import socket
import asyncio
from functools import partial
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters
)

# ================== ВАШ ТОКЕН ==================
BOT_TOKEN = "8318059900:AAHXW1Y2K6c32tAmelmZ_f3mVZVY_0dZyd0"

# ================== ЛОГИРОВАНИЕ ==================
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ================== ПРОВЕРКА ДАТА-ЦЕНТРОВ TELEGRAM ==================
def check_telegram_dc():
    telegram_dcs = {
        "DC1": "149.154.167.40",
        "DC2": "149.154.167.50",
        "DC3": "149.154.167.91",
        "DC4": "149.154.167.92",
        "DC5": "91.108.56.136",
    }

    logger.info("🌐 Проверка доступности дата-центров Telegram...")
    best_dc = None
    best_ping = float("inf")

    for dc_name, ip in telegram_dcs.items():
        start = time.time()
        try:
            sock = socket.create_connection((ip, 443), timeout=1)
            sock.close()
            ping = (time.time() - start) * 1000
            logger.info(f"✅ {dc_name} ({ip}) отклик: {ping:.1f} ms")
            if ping < best_ping:
                best_ping = ping
                best_dc = (dc_name, ip)
        except Exception:
            logger.warning(f"❌ {dc_name} ({ip}) недоступен")

    if best_dc:
        logger.info(f"🏆 Лучший дата-центр: {best_dc[0]} ({best_dc[1]}) — {best_ping:.1f} ms")
    else:
        logger.error("⚠️ Ни один дата-центр Telegram не отвечает! Проверь интернет.")
        time.sleep(5)
        check_telegram_dc()

# ================== СКАЧИВАНИЕ ВИДЕО С ПОДДЕРЖКОЙ COOKIE ==================
def download_video_info(url: str, filename_noext: str, cookies_file: str = None):
    """
    Скачивание видео через yt_dlp с поддержкой cookies для приватных видео.
    """
    ydl_opts = {
        'format': 'best',
        'outtmpl': filename_noext + '.%(ext)s',
        'quiet': True,
        'noplaylist': True,
        'max_filesize': 500 * 1024 * 1024,  # 500 МБ
    }

    if cookies_file and os.path.exists(cookies_file):
        ydl_opts['cookiefile'] = cookies_file
        logger.info(f"Используются cookies из {cookies_file}")

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return info

# ================== /start ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"Пользователь {user.username} (ID: {user.id}) запустил /start")

    await update.message.reply_text(
        "👋 Привет! Я бот для скачивания видео с YouTube, Instagram и TikTok.\n\n"
        "📎 Пришли мне ссылку на видео, и я скачаю его для тебя.\n"
        "💡 Для приватных видео добавь файл cookies (cookies.txt) рядом с ботом."
    )

# ================== ОБРАБОТКА СООБЩЕНИЙ ==================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message_text = update.message.text.strip()
    logger.info(f"Сообщение от {user.username} (ID: {user.id}): {message_text}")

    if not (message_text.startswith("http://") or message_text.startswith("https://")):
        await update.message.reply_text("⚠️ Это не похоже на ссылку. Пришли настоящую ссылку на видео.")
        return

    await update.message.reply_text("⏳ Скачиваю видео... Это может занять некоторое время 🕒")
    logger.info(f"⬇️ Начало скачивания для {user.username} — {message_text}")

    loop = asyncio.get_running_loop()
    try:
        # Уникальное имя файла для каждого пользователя
        timestamp = int(time.time())
        base_filename = f"video_{user.id}_{timestamp}"
        cookies_file = "cookies.txt"  # можно заменить на путь к своему cookies файлу

        download_func = partial(download_video_info, message_text, base_filename, cookies_file)
        info = await loop.run_in_executor(None, download_func)

        ext = info.get("ext", "mp4")
        filepath = f"{base_filename}.{ext}"

        total_seconds = int(info.get("duration") or 0)
        mins = total_seconds // 60
        secs = total_seconds % 60

        title = info.get("title", "Без названия")
        uploader = info.get("uploader", "Неизвестный автор")

        caption = (
            f"🎥 <b>{title}</b>\n"
            f"👤 Автор: {uploader}\n"
            f"⏱️ Длительность: {mins}:{secs:02d}\n\n"
            f"✅ Видео скачано! 🎉"
        )

        # Отправляем видео пользователю
        with open(filepath, "rb") as video:
            await update.message.reply_video(
                video=video,
                caption=caption,
                parse_mode="HTML"
            )

        logger.info(f"✅ Видео отправлено {user.username} ({user.id}) — {title}")
        os.remove(filepath)

    except yt_dlp.utils.DownloadError as e:
        logger.error(f"⚠️ Ошибка загрузки у {user.username}: {e}")
        await update.message.reply_text(
            "⚠️ Видео недоступно или требует авторизации. Проверь cookies.txt или попробуй другую ссылку."
        )
    except Exception as e:
        logger.exception(f"❌ Ошибка у {user.username}: {e}")
        await update.message.reply_text("⚠️ Произошла ошибка. Попробуй снова.")

# ================== ОСНОВНАЯ ФУНКЦИЯ ==================
def main():
    check_telegram_dc()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("✅ Бот запущен и готов к работе!")
    print("✅ Бот запущен! Теперь поддерживает многопользовательское скачивание больших видео.")
    app.run_polling()

if __name__ == "__main__":
    main()