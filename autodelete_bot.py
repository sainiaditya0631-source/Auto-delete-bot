import os
import asyncio
import json
from datetime import datetime
from telegram import Update
from telegram.ext import (
    Application, MessageHandler, CommandHandler,
    filters, ContextTypes
)

BOT_TOKEN    = os.getenv("BOT_TOKEN")
DELETE_AFTER = 60  # seconds
OWNER_ID     = 6289856752  # Owner ka Telegram ID

SAVE_FILE = "protected.json"

def load_protected() -> dict:
    try:
        with open(SAVE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_protected(data: dict):
    with open(SAVE_FILE, "w") as f:
        json.dump(data, f)

protected = load_protected()


def is_protected(chat_id: int, msg_id: int) -> bool:
    return str(chat_id) in protected and protected[str(chat_id)] == msg_id


async def is_allowed(update: Update, ctx) -> bool:
    """Owner ya Admin — dono allowed hain."""
    user = update.effective_user
    if not user:
        return False
    # Owner hamesha allowed
    if user.id == OWNER_ID:
        return True
    # Admin check
    try:
        member = await ctx.bot.get_chat_member(
            update.effective_chat.id, user.id
        )
        return member.status in ("administrator", "creator")
    except Exception:
        return False


async def try_delete(bot, chat_id: int, msg_id: int):
    if is_protected(chat_id, msg_id):
        return
    try:
        await bot.delete_message(chat_id, msg_id)
    except Exception:
        pass


async def delayed_delete(bot, chat_id: int, msg_id: int):
    await asyncio.sleep(DELETE_AFTER)
    await try_delete(bot, chat_id, msg_id)


# ══════════════════════════════════════════════════
#  COMMANDS
# ══════════════════════════════════════════════════

async def cmd_keep(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if not await is_allowed(update, ctx):
        asyncio.create_task(delayed_delete(ctx.bot, chat_id, update.message.message_id))
        return

    if not update.message.reply_to_message:
        m = await update.message.reply_text(
            "ℹ️ Jis message ko protect karna hai uske reply mein /keep likho."
        )
        asyncio.create_task(delayed_delete(ctx.bot, chat_id, update.message.message_id))
        asyncio.create_task(delayed_delete(ctx.bot, chat_id, m.message_id))
        return

    target_id = update.message.reply_to_message.message_id
    protected[str(chat_id)] = target_id
    save_protected(protected)

    m = await update.message.reply_text(
        "✅ Message protect ho gaya! Yeh kabhi delete nahi hoga."
    )
    asyncio.create_task(delayed_delete(ctx.bot, chat_id, update.message.message_id))
    asyncio.create_task(delayed_delete(ctx.bot, chat_id, m.message_id))


async def cmd_unkeep(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if not await is_allowed(update, ctx):
        asyncio.create_task(delayed_delete(ctx.bot, chat_id, update.message.message_id))
        return

    if str(chat_id) in protected:
        del protected[str(chat_id)]
        save_protected(protected)
        m = await update.message.reply_text("✅ Protection hata di.")
    else:
        m = await update.message.reply_text("ℹ️ Koi protected message nahi hai.")

    asyncio.create_task(delayed_delete(ctx.bot, chat_id, update.message.message_id))
    asyncio.create_task(delayed_delete(ctx.bot, chat_id, m.message_id))


async def cmd_clean(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Last 500 messages ek baar mein delete karo."""
    chat_id = update.effective_chat.id

    if not await is_allowed(update, ctx):
        asyncio.create_task(delayed_delete(ctx.bot, chat_id, update.message.message_id))
        return

    current_id = update.message.message_id

    # Command message pehle delete karo
    await try_delete(ctx.bot, chat_id, current_id)

    # Last 500 messages delete karo
    tasks = []
    for mid in range(current_id - 1, max(current_id - 500, 0), -1):
        if not is_protected(chat_id, mid):
            tasks.append(try_delete(ctx.bot, chat_id, mid))

    # Batch mein delete karo — flood se bachne ke liye
    batch_size = 20
    for i in range(0, len(tasks), batch_size):
        await asyncio.gather(*tasks[i:i+batch_size])
        await asyncio.sleep(0.5)


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    pid = protected.get(str(chat_id))

    if pid:
        text = (f"🛡 Protected Message ID: <code>{pid}</code>\n"
                f"⏱ Auto-delete: {DELETE_AFTER} seconds")
    else:
        text = (f"ℹ️ Koi protected message nahi hai\n"
                f"⏱ Auto-delete: {DELETE_AFTER} seconds")

    m = await update.message.reply_text(text, parse_mode="HTML")
    asyncio.create_task(delayed_delete(ctx.bot, chat_id, update.message.message_id))
    asyncio.create_task(delayed_delete(ctx.bot, chat_id, m.message_id))


async def cmd_settime(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Delete time change karo — /settime 120 (seconds mein)"""
    global DELETE_AFTER
    chat_id = update.effective_chat.id

    if not await is_allowed(update, ctx):
        asyncio.create_task(delayed_delete(ctx.bot, chat_id, update.message.message_id))
        return

    try:
        secs = int(ctx.args[0])
        if secs < 10:
            secs = 10
        DELETE_AFTER = secs
        m = await update.message.reply_text(
            f"✅ Ab messages {DELETE_AFTER} seconds baad delete honge."
        )
    except Exception:
        m = await update.message.reply_text(
            "❌ Format: /settime 60\n(seconds mein likho)"
        )

    asyncio.create_task(delayed_delete(ctx.bot, chat_id, update.message.message_id))
    asyncio.create_task(delayed_delete(ctx.bot, chat_id, m.message_id))


# ══════════════════════════════════════════════════
#  AUTO DELETE — SABKE MESSAGES
# ══════════════════════════════════════════════════

async def handle_all(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Har message — admin ka, user ka, bot ka — sab 60s baad delete."""
    msg = update.effective_message
    if not msg:
        return

    chat_id = msg.chat_id
    msg_id  = msg.message_id

    # Protected message skip karo
    if is_protected(chat_id, msg_id):
        return

    asyncio.create_task(delayed_delete(ctx.bot, chat_id, msg_id))


# ══════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════

def main():
    print(f"\n{'='*45}")
    print(f"  Auto Delete Bot  |  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Owner ID: {OWNER_ID}")
    print(f"  Delete after: {DELETE_AFTER} seconds")
    print(f"{'='*45}\n")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("keep",    cmd_keep))
    app.add_handler(CommandHandler("unkeep",  cmd_unkeep))
    app.add_handler(CommandHandler("clean",   cmd_clean))
    app.add_handler(CommandHandler("status",  cmd_status))
    app.add_handler(CommandHandler("settime", cmd_settime))

    # Sabke messages pakdo
    app.add_handler(MessageHandler(filters.ALL, handle_all))

    print("✅ Bot polling...")
    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
        
