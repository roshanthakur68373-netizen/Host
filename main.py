import os
import requests
import sys
import json
import time
import re
import subprocess
import signal
import psutil

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
from telegram.request import HTTPXRequest
from telegram.error import TimedOut

# ================= CONFIG =================

BOT_TOKEN = "8153587701:AAELDDLQDjWNw_fSylj3xsAj0n_4RntZ2T4
UPDATES_CHANNEL = "https://t.me/your_updates_channel"
OWNER_USERNAME = "@RaushanTha"

BOT_DIR = "bots"
LOG_DIR = "logs"
PID_FILE = "pids.json"

START_TIME = time.time()

os.makedirs(BOT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# ================= PID STORAGE =================

def load_pids():
    if not os.path.exists(PID_FILE):
        return {}
    with open(PID_FILE) as f:
        return json.load(f)

def save_pids(data):
    with open(PID_FILE, "w") as f:
        json.dump(data, f, indent=2)

PROCESSES = load_pids()

# clean dead processes
for bot, pid in list(PROCESSES.items()):
    if not psutil.pid_exists(pid):
        PROCESSES.pop(bot)
save_pids(PROCESSES)

# ================= UI =================

def bottom_menu():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📤 Upload File"), KeyboardButton("🛠 Manage Bots")],
            [KeyboardButton("📂 Check Files"), KeyboardButton("📊 Status")],
            [KeyboardButton("⏱ Uptime"), KeyboardButton("📢 Updates Channel")],
            [KeyboardButton("📞 Contact Owner")]
        ],
        resize_keyboard=True
    )

def bot_list_menu():
    rows = []
    for bot in os.listdir(BOT_DIR):
        pid = PROCESSES.get(bot)
        icon = "🟢" if pid and psutil.pid_exists(pid) else "🔴"
        rows.append([
            InlineKeyboardButton(f"{icon} {bot}", callback_data=f"bot|{bot}")
        ])
    return InlineKeyboardMarkup(rows)

def bot_actions(bot):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("▶ Start", callback_data=f"start|{bot}"),
            InlineKeyboardButton("⏹ Stop", callback_data=f"stop|{bot}")
        ],
        [
            InlineKeyboardButton("📄 Logs", callback_data=f"logs|{bot}"),
            InlineKeyboardButton("🗑 Delete", callback_data=f"delete|{bot}")
        ]
    ])

# ================= PROCESS HELPERS =================

def start_bot(bot):
    path = os.path.join(BOT_DIR, bot)
    log = open(os.path.join(LOG_DIR, f"{bot}.log"), "a")

    proc = subprocess.Popen(
        [sys.executable, path],
        stdout=log,
        stderr=log,
        preexec_fn=os.setsid
    )

    PROCESSES[bot] = proc.pid
    save_pids(PROCESSES)
    return proc.pid

def stop_bot(bot):
    pid = PROCESSES.get(bot)
    if pid:
        try:
            os.killpg(pid, signal.SIGTERM)
        except:
            pass
        PROCESSES.pop(bot, None)
        save_pids(PROCESSES)

def auto_install_module(bot):
    log_path = os.path.join(LOG_DIR, f"{bot}.log")
    if not os.path.exists(log_path):
        return None

    with open(log_path) as f:
        text = f.read()

    match = re.search(r"No module named ['\"]([^'\"]+)['\"]", text)
    if not match:
        return None

    module = match.group(1)
    subprocess.call([sys.executable, "-m", "pip", "install", module])
    return module

# ================= ERROR HANDLER =================

async def error_handler(update, context):
    if isinstance(context.error, TimedOut):
        print("⚠️ Telegram request timed out (handled safely)")
    else:
        print(context.error)

# ================= COMMANDS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 **Python Host Bot**\n\n"
        "Stable hosting with monitoring.",
        parse_mode="Markdown",
        reply_markup=bottom_menu()
    )

# ================= TEXT HANDLER =================

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "📤 Upload File":
        context.user_data["upload"] = True
        await update.message.reply_text("📤 Send a `.py` file")

    elif text == "🛠 Manage Bots":
        await update.message.reply_text(
            "🛠 **Select a bot**",
            parse_mode="Markdown",
            reply_markup=bot_list_menu()
        )

    elif text == "📂 Check Files":
        files = os.listdir(BOT_DIR)
        await update.message.reply_text("\n".join(files) or "No files uploaded.")

    elif text == "📊 Status":
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory().percent
        await update.message.reply_text(
            f"📊 **System Status**\n\nCPU: {cpu}%\nRAM: {ram}%",
            parse_mode="Markdown"
        )

    elif text == "⏱ Uptime":
        await update.message.reply_text(
            f"⏱ Uptime: {int(time.time() - START_TIME)} seconds"
        )

    elif text == "📢 Updates Channel":
        await update.message.reply_text(
            "📢 Updates",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Open Channel", url=UPDATES_CHANNEL)]
            ])
        )

    elif text == "📞 Contact Owner":
        await update.message.reply_text(
            "📞 Contact Owner",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Message Owner", url=OWNER_USERNAME)]
            ])
        )

# ================= FILE HANDLER =================

async def file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("upload"):
        return

    doc = update.message.document
    if not doc.file_name.endswith(".py"):
        return

    msg = await update.message.reply_text("⏳ Processing...")
    file = await doc.get_file()
    await file.download_to_drive(os.path.join(BOT_DIR, doc.file_name))

    pid = start_bot(doc.file_name)
    context.user_data.clear()

    await msg.edit_text(
        f"✅ **Bot Started**\n\nFile: `{doc.file_name}`\nPID: `{pid}`",
        parse_mode="Markdown"
    )

# ================= CALLBACK HANDLER =================

async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    action, bot = q.data.split("|", 1)

    if action == "bot":
        pid = PROCESSES.get(bot)
        cpu = ram = "-"
        if pid and psutil.pid_exists(pid):
            p = psutil.Process(pid)
            cpu = f"{p.cpu_percent(interval=0.5)}%"
            ram = f"{p.memory_percent():.2f}%"

        await q.edit_message_text(
            f"⚙ **{bot}**\n\nPID: `{pid if pid else '-'}`\nCPU: {cpu}\nRAM: {ram}",
            parse_mode="Markdown",
            reply_markup=bot_actions(bot)
        )

    elif action == "start":
        pid = start_bot(bot)
        await q.edit_message_text(
            f"▶ Started\nPID: `{pid}`",
            parse_mode="Markdown",
            reply_markup=bot_actions(bot)
        )

    elif action == "stop":
        stop_bot(bot)
        await q.edit_message_text(
            "⏹ Stopped",
            parse_mode="Markdown",
            reply_markup=bot_actions(bot)
        )

    elif action == "logs":
        module = auto_install_module(bot)
        if module:
            pid = start_bot(bot)
            await q.edit_message_text(
                f"📦 Installed `{module}`\nRestarted\nPID: `{pid}`",
                parse_mode="Markdown",
                reply_markup=bot_actions(bot)
            )
            return

        with open(os.path.join(LOG_DIR, f"{bot}.log")) as f:
            await q.edit_message_text(
                f"📄 Logs\n\n{''.join(f.readlines()[-25:])}",
                reply_markup=bot_actions(bot)
            )

    elif action == "delete":
        stop_bot(bot)
        os.remove(os.path.join(BOT_DIR, bot))
        await q.edit_message_text("🗑 Deleted")

# ================= MAIN =================

def main():
    request = HTTPXRequest(
        connect_timeout=20,
        read_timeout=20,
        write_timeout=20,
        pool_timeout=20
    )

    app = ApplicationBuilder() \
        .token(BOT_TOKEN) \
        .request(request) \
        .build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, file_handler))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_error_handler(error_handler)

    print("✅ Host Bot running with psutil + timeout fix")
    app.run_polling()

if __name__ == "__main__":
    main()
