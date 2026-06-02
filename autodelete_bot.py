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

# File to save protected message id
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

# { chat_id: message_id }
protected = load_protected()


def is_protected(chat_id: int, msg_id: int) -> bool:
    return str(chat_id) in protected and protected[str(chat_id)] == msg_id


async def try_delete(bot, chat_id: int, msg_id: int):
    """Delete a message silently, skip if protected."""
    if is_protected(chat_id, msg_id):
        return
    try:
        await bot.delete_message(chat_id, msg_id)
    except Exception:
        pass


async def delayed_delete(bot, chat_id: int, msg_id: int):
    """Wait DELETE_AFTER seconds then delete."""
    await asyncio.sleep(DELETE_AFTER)
    await try_delete(bot, chat_id, msg_id)


# ══════════════════════════════════════════════════
#  COMMANDS
# ══════════════════════════════════════════════════

async def cmd_keep(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Reply to any message with /keep — woh message permanent ho jaayega."""
    chat_id = update.effective_chat.id
    user    = update.effective_user

    # Only admins
    member = await ctx.bot.get_chat_member(chat_id, user.id)
    if member.status not in ("administrator", "creator"):
        await update.message.reply_text("❌ Sirf admins use kar sakte hain.")
        asyncio.create_task(delayed_delete(ctx.bot, chat_id, update.message.message_id))
        return

    if not update.message.reply_to_message:
        m = await update.message.reply_text(
            "ℹ️ Jis message ko protect karna hai\nuske reply mein /keep likho."
        )
        asyncio.create_task(delayed_delete(ctx.bot, chat_id, update.message.message_id))
        asyncio.create_task(delayed_delete(ctx.bot, chat_id, m.message_id))
        return

    target_id = update.message.reply_to_message.message_id

    # Remove old protected if any
    old = protected.get(str(chat_id))
    if old:
        # Old protected ab normal ban gaya — delete schedule
        pass

    protected[str(chat_id)] = target_id
    save_protected(protected)

    m = await update.message.reply_text("✅ Message protect ho gaya! Yeh delete nahi hoga.")
    asyncio.create_task(delayed_delete(ctx.bot, chat_id, update.message.message_id))
    asyncio.create_task(delayed_delete(ctx.bot, chat_id, m.message_id))


async def cmd_unkeep(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Remove protection from saved message."""
    chat_id = update.effective_chat.id
    user    = update.effective_user

    member = await ctx.bot.get_chat_member(chat_id, user.id)
    if member.status not in ("administrator", "creator"):
        asyncio.create_task(delayed_delete(ctx.bot, chat_id, update.message.message_id))
        return

    if str(chat_id) in protected:
        del protected[str(chat_id)]
        save_protected(protected)
        m = await update.message.reply_text("✅ Protection hata di.")
    else:
        m = await update.message.reply_text("ℹ️ Koi protected message nahi hai abhi.")

    asyncio.create_task(delayed_delete(ctx.bot, chat_id, update.message.message_id))
    asyncio.create_task(delayed_delete(ctx.bot, chat_id, m.message_id))


async def cmd_clean(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Delete last 100 messages at once (except protected)."""
    chat_id = update.effective_chat.id
    user    = update.effective_user

    member = await ctx.bot.get_chat_member(chat_id, user.id)
    if member.status not in ("administrator", "creator"):
        asyncio.create_task(delayed_delete(ctx.bot, chat_id, update.message.message_id))
        return

    current_id = update.message.message_id
    m = await update.message.reply_text("🧹 Cleaning...")

    deleted = 0
    for mid in range(current_id, max(current_id - 200, 0), -1):
        if is_protected(chat_id, mid):
            continue
        try:
            await ctx.bot.delete_message(chat_id, mid)
            deleted += 1
            await asyncio.sleep(0.05)  # Flood limit se bachne ke liye
        except Exception:
            pass

    # Also delete the "Cleaning..." message
    try:
        await ctx.bot.delete_message(chat_id, m.message_id)
    except Exception:
        pass


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show which message is currently protected."""
    chat_id = update.effective_chat.id
    pid = protected.get(str(chat_id))

    if pid:
        text = f"🛡 Protected message ID: <code>{pid}</code>\n⏱ Auto-delete: {DELETE_AFTER}s"
    else:
        text = f"ℹ️ Koi protected message nahi\n⏱ Auto-delete: {DELETE_AFTER}s"

    m = await update.message.reply_text(text, parse_mode="HTML")
    asyncio.create_task(delayed_delete(ctx.bot, chat_id, update.message.message_id))
    asyncio.create_task(delayed_delete(ctx.bot, chat_id, m.message_id))


# ══════════════════════════════════════════════════
#  AUTO DELETE — ALL MESSAGES
# ══════════════════════════════════════════════════

async def handle_all(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Every message — schedule delete after 60s."""
    msg = update.effective_message
    if not msg:
        return
    chat_id = msg.chat_id
    msg_id  = msg.message_id

    # Skip if this message is the protected one
    if is_protected(chat_id, msg_id):
        return

    asyncio.create_task(delayed_delete(ctx.bot, chat_id, msg_id))


# ══════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════

def main():
    print(f"\n{'='*40}")
    print(f"  Auto Delete Bot  |  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Delete after: {DELETE_AFTER} seconds")
    print(f"{'='*40}\n")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("keep",     cmd_keep))
    app.add_handler(CommandHandler("unkeep",   cmd_unkeep))
    app.add_handler(CommandHandler("clean",    cmd_clean))
    app.add_handler(CommandHandler("status",   cmd_status))

    # Sab kuch pakdo — text, media, stickers, sab
    app.add_handler(MessageHandler(filters.ALL, handle_all))

    print("✅ Bot polling...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
