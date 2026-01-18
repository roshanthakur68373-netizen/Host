# ===== KEEP ALIVE =====
from keep_alive import keep_alive
keep_alive()

# ===== IMPORTS =====
import requests import os, sys, json, time, re, subprocess, signal
import psutil

from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.request import HTTPXRequest
from telegram.error import TimedOut

# ===== CONFIG =====
BOT_TOKEN = os.getenv("BOT_TOKEN") or "PUT_BOT_TOKEN"
BOT_DIR = "bots"
LOG_DIR = "logs"
PID_FILE = "pids.json"

os.makedirs(BOT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# ===== PID STORAGE =====
def load_pids():
    if not os.path.exists(PID_FILE):
        return {}
    with open(PID_FILE) as f:
        return json.load(f)

def save_pids(d):
    with open(PID_FILE, "w") as f:
        json.dump(d, f, indent=2)

PROCESSES = load_pids()

# ===== PROCESS HELPERS =====
def start_bot(bot):
    log = open(f"{LOG_DIR}/{bot}.log", "a")
    p = subprocess.Popen(
        [sys.executable, f"{BOT_DIR}/{bot}"],
        stdout=log, stderr=log, preexec_fn=os.setsid
    )
    PROCESSES[bot] = p.pid
    save_pids(PROCESSES)
    return p.pid

def stop_bot(bot):
    pid = PROCESSES.get(bot)
    if pid:
        try:
            os.killpg(pid, signal.SIGTERM)
        except:
            pass
        PROCESSES.pop(bot, None)
        save_pids(PROCESSES)

# ===== UI =====
def bottom_menu():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📤 Upload"), KeyboardButton("🛠 Manage")]],
        resize_keyboard=True
    )

def bot_list():
    rows = []
    for b in os.listdir(BOT_DIR):
        pid = PROCESSES.get(b)
        icon = "🟢" if pid and psutil.pid_exists(pid) else "🔴"
        rows.append([InlineKeyboardButton(f"{icon} {b}", callback_data=f"bot|{b}")])
    return InlineKeyboardMarkup(rows)

def bot_actions(bot):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶ Start", callback_data=f"start|{bot}"),
         InlineKeyboardButton("⏹ Stop", callback_data=f"stop|{bot}")],
        [InlineKeyboardButton("📄 Logs", callback_data=f"logs|{bot}"),
         InlineKeyboardButton("🗑 Delete", callback_data=f"delete|{bot}")]
    ])

# ===== HANDLERS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Host Bot running on Replit (FREE)",
        reply_markup=bottom_menu()
    )

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "📤 Upload":
        context.user_data["upload"] = True
        await update.message.reply_text("Send .py file")

    elif update.message.text == "🛠 Manage":
        await update.message.reply_text(
            "Select bot",
            reply_markup=bot_list()
        )

async def file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("upload"):
        return

    doc = update.message.document
    if not doc.file_name.endswith(".py"):
        return

    file = await doc.get_file()
    await file.download_to_drive(f"{BOT_DIR}/{doc.file_name}")
    pid = start_bot(doc.file_name)
    context.user_data.clear()

    await update.message.reply_text(
        f"✅ Started `{doc.file_name}`\nPID: `{pid}`",
        parse_mode="Markdown"
    )

async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    act, bot = q.data.split("|", 1)

    if act == "bot":
        await q.edit_message_text(
            f"⚙ {bot}",
            reply_markup=bot_actions(bot)
        )

    elif act == "start":
        pid = start_bot(bot)
        await q.edit_message_text(f"▶ Started `{pid}`", reply_markup=bot_actions(bot))

    elif act == "stop":
        stop_bot(bot)
        await q.edit_message_text("⏹ Stopped", reply_markup=bot_actions(bot))

    elif act == "logs":
        with open(f"{LOG_DIR}/{bot}.log") as f:
            await q.edit_message_text(
                f"📄 Logs\n\n{''.join(f.readlines()[-20:])}",
                reply_markup=bot_actions(bot)
            )

    elif act == "delete":
        stop_bot(bot)
        os.remove(f"{BOT_DIR}/{bot}")
        await q.edit_message_text("🗑 Deleted")

# ===== ERROR HANDLER =====
async def error_handler(update, context):
    if isinstance(context.error, TimedOut):
        print("Telegram timeout handled")

# ===== MAIN =====
def main():
    request = HTTPXRequest(
        connect_timeout=20,
        read_timeout=20,
        write_timeout=20,
        pool_timeout=20
    )

    app = ApplicationBuilder().token(BOT_TOKEN).request(request).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, file_handler))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_error_handler(error_handler)

    print("✅ Running on Replit with Flask alive")
    app.run_polling()

if __name__ == "__main__":
    main()
