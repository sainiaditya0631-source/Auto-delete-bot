import os
import asyncio
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, MessageHandler, CommandHandler,
    CallbackQueryHandler, filters, ContextTypes
)

BOT_TOKEN    = os.getenv("BOT_TOKEN")
DELETE_AFTER = 60
OWNER_ID     = 6289856752

SAVE_FILE = "data.json"

def load_data() -> dict:
    try:
        with open(SAVE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"protected": {}, "whitelist": {}}

def save_data(data: dict):
    with open(SAVE_FILE, "w") as f:
        json.dump(data, f)

data      = load_data()
protected = data.get("protected", {})
whitelist = data.get("whitelist", {})  # {chat_id: [user_id, ...]}


def save_all():
    save_data({"protected": protected, "whitelist": whitelist})


def is_protected(chat_id: int, msg_id: int) -> bool:
    return str(chat_id) in protected and protected[str(chat_id)] == msg_id


def is_whitelisted(chat_id: int, user_id: int) -> bool:
    """Whitelist mein hai to message delete nahi hoga."""
    if user_id == OWNER_ID:
        return True
    wl = whitelist.get(str(chat_id), [])
    return user_id in wl


async def is_allowed(update: Update, ctx) -> bool:
    """Owner ya Telegram Admin — command chala sakte hain."""
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


async def delayed_delete(bot, chat_id: int, msg_id: int, user_id: int = 0):
    """Whitelist wale users ke messages delete nahi honge."""
    await asyncio.sleep(DELETE_AFTER)
    if is_protected(chat_id, msg_id):
        return
    if user_id and is_whitelisted(chat_id, user_id):
        return
    await try_delete(bot, chat_id, msg_id)


async def owner_notify(ctx, text: str):
    try:
        await ctx.bot.send_message(OWNER_ID, text, parse_mode="HTML")
    except Exception:
        pass


# ══════════════════════════════════════════════════
#  SETTIME INLINE KEYBOARD
# ══════════════════════════════════════════════════

def settime_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("30 sec",  callback_data="st_30"),
            InlineKeyboardButton("1 min",   callback_data="st_60"),
            InlineKeyboardButton("2 min",   callback_data="st_120"),
        ],
        [
            InlineKeyboardButton("5 min",   callback_data="st_300"),
            InlineKeyboardButton("10 min",  callback_data="st_600"),
            InlineKeyboardButton("Custom ✏️", callback_data="st_custom"),
        ],
    ])


async def cb_settime(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global DELETE_AFTER
    q = update.callback_query
    await q.answer()

    if q.from_user.id != OWNER_ID:
        allowed = False
        try:
            m = await ctx.bot.get_chat_member(
                update.effective_chat.id, q.from_user.id
            )
            allowed = m.status in ("administrator", "creator")
        except Exception:
            pass
        if not allowed:
            return

    val = q.data.split("_")[1]

    if val == "custom":
        await q.edit_message_text(
            "✏️ Custom time set karna hai?\n"
            "Group mein type karo: <code>/settime 90</code>\n"
            "(seconds mein)",
            parse_mode="HTML"
        )
        return

    DELETE_AFTER = int(val)
    mins = DELETE_AFTER // 60
    secs = DELETE_AFTER % 60
    label = f"{mins} min" if secs == 0 else f"{DELETE_AFTER} sec"

    await q.edit_message_text(
        f"✅ Delete time set: <b>{label}</b>",
        parse_mode="HTML"
    )


# ══════════════════════════════════════════════════
#  COMMANDS
# ══════════════════════════════════════════════════

async def cmd_keep(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await try_delete(ctx.bot, chat_id, update.message.message_id)
    if not await is_allowed(update, ctx):
        return
    if not update.message.reply_to_message:
        await owner_notify(ctx, "ℹ️ /keep — kisi message ke reply mein use karo.")
        return
    target_id = update.message.reply_to_message.message_id
    protected[str(chat_id)] = target_id
    save_all()
    await owner_notify(ctx, f"✅ Message <code>{target_id}</code> protect ho gaya!")


async def cmd_unkeep(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await try_delete(ctx.bot, chat_id, update.message.message_id)
    if not await is_allowed(update, ctx):
        return
    if str(chat_id) in protected:
        del protected[str(chat_id)]
        save_all()
        await owner_notify(ctx, "✅ Protection hata di.")
    else:
        await owner_notify(ctx, "ℹ️ Koi protected message nahi tha.")


async def cmd_clean(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id    = update.effective_chat.id
    current_id = update.message.message_id
    await try_delete(ctx.bot, chat_id, current_id)
    if not await is_allowed(update, ctx):
        return
    await owner_notify(ctx, "🧹 Cleaning shuru...")
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
    await owner_notify(ctx, f"✅ <b>{deleted}</b> messages delete kiye!")


async def cmd_settime(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global DELETE_AFTER
    chat_id = update.effective_chat.id
    await try_delete(ctx.bot, chat_id, update.message.message_id)
    if not await is_allowed(update, ctx):
        return

    # Agar argument diya toh seedha set karo
    if ctx.args:
        try:
            secs = max(10, int(ctx.args[0]))
            DELETE_AFTER = secs
            await owner_notify(ctx, f"✅ Delete time: <b>{secs} seconds</b>")
            return
        except Exception:
            pass

    # Warna inline buttons bhejo DM mein
    try:
        await ctx.bot.send_message(
            OWNER_ID,
            f"⏱ <b>Delete time select karo:</b>\n(current: {DELETE_AFTER}s)",
            parse_mode="HTML",
            reply_markup=settime_kb()
        )
    except Exception:
        pass


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await try_delete(ctx.bot, chat_id, update.message.message_id)
    pid = protected.get(str(chat_id))
    wl  = whitelist.get(str(chat_id), [])
    text = (
        f"📊 <b>Bot Status</b>\n\n"
        f"⏱ Auto-delete: <b>{DELETE_AFTER}s</b>\n"
        f"🛡 Protected msg: <code>{pid or 'None'}</code>\n"
        f"✅ Whitelist: <b>{len(wl)} users</b>"
    )
    await owner_notify(ctx, text)


async def cmd_addwl(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Whitelist mein user add karo — /addwl reply karke ya /addwl USER_ID"""
    chat_id = update.effective_chat.id
    await try_delete(ctx.bot, chat_id, update.message.message_id)
    if not await is_allowed(update, ctx):
        return

    target_id = None
    if update.message.reply_to_message:
        target_id = update.message.reply_to_message.from_user.id
    elif ctx.args:
        try:
            target_id = int(ctx.args[0])
        except Exception:
            pass

    if not target_id:
        await owner_notify(ctx,
            "ℹ️ Use: kisi ke message pe reply karke /addwl\n"
            "Ya: <code>/addwl USER_ID</code>"
        )
        return

    wl = whitelist.setdefault(str(chat_id), [])
    if target_id not in wl:
        wl.append(target_id)
        save_all()
        await owner_notify(ctx, f"✅ User <code>{target_id}</code> whitelist mein add!")
    else:
        await owner_notify(ctx, f"ℹ️ User <code>{target_id}</code> pehle se whitelist mein hai.")


async def cmd_rmwl(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Whitelist se user remove karo."""
    chat_id = update.effective_chat.id
    await try_delete(ctx.bot, chat_id, update.message.message_id)
    if not await is_allowed(update, ctx):
        return

    target_id = None
    if update.message.reply_to_message:
        target_id = update.message.reply_to_message.from_user.id
    elif ctx.args:
        try:
            target_id = int(ctx.args[0])
        except Exception:
            pass

    if not target_id:
        await owner_notify(ctx, "ℹ️ Use: reply karke /rmwl ya /rmwl USER_ID")
        return

    wl = whitelist.get(str(chat_id), [])
    if target_id in wl:
        wl.remove(target_id)
        save_all()
        await owner_notify(ctx, f"✅ User <code>{target_id}</code> whitelist se remove!")
    else:
        await owner_notify(ctx, f"ℹ️ User <code>{target_id}</code> whitelist mein tha hi nahi.")


async def cmd_wllist(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Whitelist dekho."""
    chat_id = update.effective_chat.id
    await try_delete(ctx.bot, chat_id, update.message.message_id)
    wl = whitelist.get(str(chat_id), [])
    if wl:
        ids = "\n".join(f"• <code>{uid}</code>" for uid in wl)
        await owner_notify(ctx, f"✅ <b>Whitelist ({len(wl)} users):</b>\n{ids}")
    else:
        await owner_notify(ctx, "ℹ️ Whitelist khali hai.")


# ══════════════════════════════════════════════════
#  AUTO DELETE
# ══════════════════════════════════════════════════

async def handle_all(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg:
        return
    chat_id = msg.chat_id
    msg_id  = msg.message_id
    user_id = msg.from_user.id if msg.from_user else 0

    if is_protected(chat_id, msg_id):
        return

    asyncio.create_task(delayed_delete(ctx.bot, chat_id, msg_id, user_id))


# ══════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════

def main():
    print(f"\n{'='*45}")
    print(f"  Auto Delete Bot  |  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Owner: {OWNER_ID}  |  Delete: {DELETE_AFTER}s")
    print(f"{'='*45}\n")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("keep",    cmd_keep))
    app.add_handler(CommandHandler("unkeep",  cmd_unkeep))
    app.add_handler(CommandHandler("clean",   cmd_clean))
    app.add_handler(CommandHandler("settime", cmd_settime))
    app.add_handler(CommandHandler("status",  cmd_status))
    app.add_handler(CommandHandler("addwl",   cmd_addwl))
    app.add_handler(CommandHandler("rmwl",    cmd_rmwl))
    app.add_handler(CommandHandler("wllist",  cmd_wllist))
    app.add_handler(CallbackQueryHandler(cb_settime, pattern=r"^st_"))
    app.add_handler(MessageHandler(filters.ALL, handle_all))

    print("✅ Bot polling...")
    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
    
