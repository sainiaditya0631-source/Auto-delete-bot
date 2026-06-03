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
DELETE_AFTER = 60
OWNER_ID     = 6289856752

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
    user = update.effective_user
    if not user:
        return False
    if user.id == OWNER_ID:
        return True
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


async def owner_notify(ctx, text: str):
    """Owner ko private DM mein message bhejo."""
    try:
        await ctx.bot.send_message(OWNER_ID, text, parse_mode="HTML")
    except Exception:
        pass


# ══════════════════════════════════════════════════
#  COMMANDS
# ══════════════════════════════════════════════════

async def cmd_keep(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await try_delete(ctx.bot, chat_id, update.message.message_id)

    if not await is_allowed(update, ctx):
        await owner_notify(ctx, "❌ Unauthorized /keep attempt")
        return

    if not update.message.reply_to_message:
        await owner_notify(ctx, "ℹ️ /keep — jis message ko protect karna hai uske reply mein /keep likho.")
        return

    target_id = update.message.reply_to_message.message_id
    protected[str(chat_id)] = target_id
    save_protected(protected)
    await owner_notify(ctx, f"✅ Message <code>{target_id}</code> protect ho gaya!")


async def cmd_unkeep(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await try_delete(ctx.bot, chat_id, update.message.message_id)

    if not await is_allowed(update, ctx):
        return

    if str(chat_id) in protected:
        del protected[str(chat_id)]
        save_protected(protected)
        await owner_notify(ctx, "✅ Protection hata di.")
    else:
        await owner_notify(ctx, "ℹ️ Koi protected message nahi tha.")


async def cmd_clean(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id    = update.effective_chat.id
    current_id = update.message.message_id
    await try_delete(ctx.bot, chat_id, current_id)

    if not await is_allowed(update, ctx):
        return

    await owner_notify(ctx, "🧹 Cleaning shuru ho raha hai...")

    deleted = 0
    for mid in range(current_id - 1, max(current_id - 500, 0), -1):
        if is_protected(chat_id, mid):
            continue
        try:
            await ctx.bot.delete_message(chat_id, mid)
            deleted += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass

    await owner_notify(ctx, f"✅ Clean complete! <b>{deleted}</b> messages delete kiye.")


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await try_delete(ctx.bot, chat_id, update.message.message_id)

    pid = protected.get(str(chat_id))
    if pid:
        text = (f"🛡 Protected ID: <code>{pid}</code>\n"
                f"⏱ Auto-delete: <b>{DELETE_AFTER}s</b>")
    else:
        text = (f"ℹ️ Koi protected message nahi\n"
                f"⏱ Auto-delete: <b>{DELETE_AFTER}s</b>")

    await owner_notify(ctx, text)


async def cmd_settime(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global DELETE_AFTER
    chat_id = update.effective_chat.id
    await try_delete(ctx.bot, chat_id, update.message.message_id)

    if not await is_allowed(update, ctx):
        return

    try:
        secs = int(ctx.args[0])
        secs = max(10, secs)
        DELETE_AFTER = secs
        await owner_notify(ctx, f"✅ Ab messages <b>{DELETE_AFTER} seconds</b> baad delete honge!")
    except Exception:
        await owner_notify(ctx, "❌ Format: <code>/settime 60</code>\n(seconds mein likho)")


# ══════════════════════════════════════════════════
#  AUTO DELETE — SABKE MESSAGES
# ══════════════════════════════════════════════════

async def handle_all(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg:
        return
    chat_id = msg.chat_id
    msg_id  = msg.message_id

    if is_protected(chat_id, msg_id):
        return

    asyncio.create_task(delayed_delete(ctx.bot, chat_id, msg_id))


# ══════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════

def main():
    print(f"\n{'='*45}")
    print(f"  Auto Delete Bot  |  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Owner ID : {OWNER_ID}")
    print(f"  Delete   : {DELETE_AFTER}s")
    print(f"{'='*45}\n")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("keep",    cmd_keep))
    app.add_handler(CommandHandler("unkeep",  cmd_unkeep))
    app.add_handler(CommandHandler("clean",   cmd_clean))
    app.add_handler(CommandHandler("status",  cmd_status))
    app.add_handler(CommandHandler("settime", cmd_settime))
    app.add_handler(MessageHandler(filters.ALL, handle_all))

    print("✅ Bot polling...")
    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
        
