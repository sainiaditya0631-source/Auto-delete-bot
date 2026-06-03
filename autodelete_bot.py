import os
import asyncio
import json
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message

API_ID       = int(os.getenv("API_ID", "0"))
API_HASH     = os.getenv("API_HASH", "")
SESSION      = os.getenv("SESSION_STRING", "")
OWNER_ID     = 6289856752
DELETE_AFTER = 60

SAVE_FILE = "userbot_data.json"

def load_data():
    try:
        with open(SAVE_FILE) as f:
            return json.load(f)
    except:
        return {"protected": {}, "whitelist": {}, "active_groups": []}

def save_data(d):
    with open(SAVE_FILE, "w") as f:
        json.dump(d, f)

data          = load_data()
protected     = data.get("protected", {})
whitelist     = data.get("whitelist", {})
active_groups = set(data.get("active_groups", []))

def save_all():
    save_data({
        "protected":     protected,
        "whitelist":     whitelist,
        "active_groups": list(active_groups)
    })

def is_protected(chat_id, msg_id):
    return str(chat_id) in protected and protected[str(chat_id)] == msg_id

def is_whitelisted(chat_id, user_id):
    if not user_id:
        return False
    if user_id == OWNER_ID:
        return True
    return user_id in whitelist.get(str(chat_id), [])

app = Client(
    "userbot",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION
)

async def try_delete(chat_id, msg_id):
    if is_protected(chat_id, msg_id):
        return
    try:
        await app.delete_messages(chat_id, msg_id)
    except Exception:
        pass

async def delayed_delete(chat_id, msg_id, user_id=0):
    await asyncio.sleep(DELETE_AFTER)
    if is_protected(chat_id, msg_id):
        return
    if is_whitelisted(chat_id, user_id):
        return
    await try_delete(chat_id, msg_id)

async def notify(text):
    """Owner ke Saved Messages mein bhejo."""
    try:
        await app.send_message("me", text)
    except Exception as e:
        print(f"Notify error: {e}")


# ══════════════════════════════════════════════════
#  AUTO DELETE
# ══════════════════════════════════════════════════

COMMANDS = ["enable","disable","keep","unkeep","clean","settime","addwl","rmwl","wllist","status"]

@app.on_message(filters.group & ~filters.command(COMMANDS))
async def handle_all(client, msg: Message):
    chat_id = msg.chat.id
    if chat_id not in active_groups:
        return
    # Anonymous admin ya channel post ka from_user None hoga
    user_id = msg.from_user.id if msg.from_user else 0
    asyncio.create_task(delayed_delete(chat_id, msg.id, user_id))


# ══════════════════════════════════════════════════
#  COMMANDS
# ══════════════════════════════════════════════════

def is_owner(msg: Message) -> bool:
    return msg.from_user is not None and msg.from_user.id == OWNER_ID


@app.on_message(filters.command("enable") & filters.group)
async def cmd_enable(client, msg: Message):
    if not is_owner(msg): return
    active_groups.add(msg.chat.id)
    save_all()
    m = await msg.reply("✅ Auto-delete **ON** is group mein!")
    await asyncio.sleep(5)
    await try_delete(msg.chat.id, msg.id)
    await try_delete(msg.chat.id, m.id)


@app.on_message(filters.command("disable") & filters.group)
async def cmd_disable(client, msg: Message):
    if not is_owner(msg): return
    active_groups.discard(msg.chat.id)
    save_all()
    m = await msg.reply("❌ Auto-delete **OFF** is group mein!")
    await asyncio.sleep(5)
    await try_delete(msg.chat.id, msg.id)
    await try_delete(msg.chat.id, m.id)


@app.on_message(filters.command("keep") & filters.group)
async def cmd_keep(client, msg: Message):
    if not is_owner(msg): return
    await try_delete(msg.chat.id, msg.id)
    if not msg.reply_to_message:
        await notify("ℹ️ /keep — kisi message ke reply mein use karo.")
        return
    protected[str(msg.chat.id)] = msg.reply_to_message.id
    save_all()
    await notify(f"✅ Message `{msg.reply_to_message.id}` protect ho gaya!")


@app.on_message(filters.command("unkeep") & filters.group)
async def cmd_unkeep(client, msg: Message):
    if not is_owner(msg): return
    await try_delete(msg.chat.id, msg.id)
    key = str(msg.chat.id)
    if key in protected:
        del protected[key]
        save_all()
        await notify("✅ Protection hata di.")
    else:
        await notify("ℹ️ Koi protected message nahi tha.")


@app.on_message(filters.command("clean") & filters.group)
async def cmd_clean(client, msg: Message):
    if not is_owner(msg): return
    chat_id = msg.chat.id
    cur_id  = msg.id
    await try_delete(chat_id, cur_id)
    await notify("🧹 Cleaning shuru...")
    deleted = 0
    for mid in range(cur_id - 1, max(cur_id - 500, 0), -1):
        if is_protected(chat_id, mid):
            continue
        try:
            await app.delete_messages(chat_id, mid)
            deleted += 1
            await asyncio.sleep(0.05)
        except:
            pass
    await notify(f"✅ **{deleted}** messages delete kiye!")


@app.on_message(filters.command("settime") & filters.group)
async def cmd_settime(client, msg: Message):
    global DELETE_AFTER
    if not is_owner(msg): return
    await try_delete(msg.chat.id, msg.id)
    parts = msg.text.split()
    if len(parts) >= 2:
        try:
            secs = max(10, int(parts[1]))
            DELETE_AFTER = secs
            await notify(f"✅ Delete time: **{secs} seconds**")
            return
        except:
            pass
    await notify("⏱ Use: `/settime 60` (seconds mein)")


@app.on_message(filters.command("addwl") & filters.group)
async def cmd_addwl(client, msg: Message):
    if not is_owner(msg): return
    await try_delete(msg.chat.id, msg.id)
    target = None
    if msg.reply_to_message and msg.reply_to_message.from_user:
        target = msg.reply_to_message.from_user.id
    elif len(msg.text.split()) >= 2:
        try: target = int(msg.text.split()[1])
        except: pass
    if not target:
        await notify("ℹ️ Reply karke /addwl ya /addwl USER_ID")
        return
    wl = whitelist.setdefault(str(msg.chat.id), [])
    if target not in wl:
        wl.append(target)
        save_all()
        await notify(f"✅ User `{target}` whitelist mein!")
    else:
        await notify(f"ℹ️ User `{target}` pehle se hai.")


@app.on_message(filters.command("rmwl") & filters.group)
async def cmd_rmwl(client, msg: Message):
    if not is_owner(msg): return
    await try_delete(msg.chat.id, msg.id)
    target = None
    if msg.reply_to_message and msg.reply_to_message.from_user:
        target = msg.reply_to_message.from_user.id
    elif len(msg.text.split()) >= 2:
        try: target = int(msg.text.split()[1])
        except: pass
    if not target:
        await notify("ℹ️ Reply karke /rmwl ya /rmwl USER_ID")
        return
    wl = whitelist.get(str(msg.chat.id), [])
    if target in wl:
        wl.remove(target)
        save_all()
        await notify(f"✅ User `{target}` remove kiya.")
    else:
        await notify(f"ℹ️ User `{target}` tha hi nahi.")


@app.on_message(filters.command("status") & filters.group)
async def cmd_status(client, msg: Message):
    if not is_owner(msg): return
    await try_delete(msg.chat.id, msg.id)
    chat_id = msg.chat.id
    pid = protected.get(str(chat_id))
    wl  = whitelist.get(str(chat_id), [])
    on  = "✅ ON" if chat_id in active_groups else "❌ OFF"
    await notify(
        f"📊 **Status**\n\n"
        f"Auto-delete: **{on}**\n"
        f"⏱ Timer: **{DELETE_AFTER}s**\n"
        f"🛡 Protected: `{pid or 'None'}`\n"
        f"✅ Whitelist: **{len(wl)} users**"
    )


# ══════════════════════════════════════════════════
#  START
# ══════════════════════════════════════════════════

print(f"\n{'='*45}")
print(f"  Userbot  |  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"  Owner: {OWNER_ID}  |  Delete: {DELETE_AFTER}s")
print(f"{'='*45}\n")
print("✅ Userbot running!")

app.run()
