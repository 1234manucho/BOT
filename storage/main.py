import os
import asyncio
import sys

# Ensure the project directory is in the Python path
sys.path.append(os.path.dirname(__file__))
from aiogram import Bot, Dispatcher, types
from dotenv import load_dotenv
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Message
from aiogram.filters import CommandStart, Command
from storage.database import ( # type: ignore
    init_db, add_user, add_bad_word, remove_bad_word, get_bad_words, get_users,
    is_bad_word_in_message, warn_user, get_user_warns, get_group_config,
    update_group_config, add_authorized_user, remove_authorized_user, is_authorized_user
)
from poison.gemini import is_offensive_with_gemini # type: ignore
from poison.checks import check_dependencies # type: ignore

# Check dependencies
check_dependencies()

# Load environment variables
load_dotenv()
AUTHORIZED_USER_ID = int(os.getenv("USER_ID", 0))
TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise ValueError("BOT_TOKEN is not set in the environment variables.")

# Initialize bot and dispatcher
bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

def is_authorized(message: Message):
    return message.from_user.id == AUTHORIZED_USER_ID

@dp.message(CommandStart())
async def start_handler(message: Message):
    user_id = message.from_user.id
    full_name = message.from_user.full_name
    add_user(user_id, full_name)
    await message.answer(f"Hello <b>{full_name}</b>! You've been saved to the DB.")

@dp.message(Command("kick"))
async def kick_command(message: types.Message):
    if not is_authorized(message):
        await message.answer("You are not authorized to use this command.")
        return

    if message.chat.type not in ("group", "supergroup"):
        await message.answer("This command can only be used in groups.")
        return

    args = message.text.split(' ')[1].strip().lower()
    if args not in ['on', 'off']:
        await message.answer("Usage: /kick <on/off>")
        return

    kick_enabled = True if args == 'on' else False
    group_id = message.chat.id
    update_group_config(group_id, kick_enabled, None)
    await message.answer(f"Kick setting updated to {args.upper()} for this group.")

@dp.message(Command("ban"))
async def ban_command(message: types.Message):
    if not is_authorized(message):
        await message.answer("You are not authorized to use this command.")
        return

    if message.chat.type not in ("group", "supergroup"):
        await message.answer("This command can only be used in groups.")
        return

    args = message.text.split(' ')[1].strip().lower()
    if args not in ['on', 'off']:
        await message.answer("Usage: /ban <on/off>")
        return

    ban_enabled = True if args == 'on' else False
    group_id = message.chat.id
    _, kick_enabled = get_group_config(group_id)
    update_group_config(group_id, kick_enabled, ban_enabled)
    await message.answer(f"Ban setting updated to {args.upper()} for this group.")

@dp.message(Command("bad"))
async def add_bad_words_handler(message: Message):
    args = message.text.replace('/bad', '').strip()
    if not args:
        await message.answer("Usage: <code>/bad word1, word2, word3</code>")
        return

    words = [word.strip().lower() for word in args.split(',') if word.strip()]
    added = []
    skipped = []

    for word in words:
        if add_bad_word(word):
            added.append(word)
        else:
            skipped.append(word)

    response = ""
    if added:
        response += f"✅ Added: <b>{', '.join(added)}</b>\n"
    if skipped:
        response += f"⚠️ Already exists: <b>{', '.join(skipped)}</b>"

    await message.answer(response or "Nothing happened.")

@dp.message(Command("removebad"))
async def remove_bad_words_handler(message: Message):
    args = message.text.replace('/removebad', '').strip()
    if not args:
        await message.answer("Usage: <code>/removebad word1, word2, word3</code>")
        return

    words = [word.strip().lower() for word in args.split(',') if word.strip()]
    removed = []
    not_found = []

    for word in words:
        if remove_bad_word(word):
            removed.append(word)
        else:
            not_found.append(word)

    response = ""
    if removed:
        response += f"✅ Removed: <b>{', '.join(removed)}</b>\n"
    if not_found:
        response += f"⚠️ Not found: <b>{', '.join(not_found)}</b>"

    await message.answer(response or "Nothing happened.")

@dp.message(Command("badwords"))
async def get_bad_words_handler(message: Message):
    words = get_bad_words()
    if not words:
        await message.answer("No bad words found.")
    else:
        await message.answer(f"Bad words: <code>{', '.join(words)}</code>")

@dp.message(Command("users"))
async def get_users_handler(message: Message):
    users = get_users()
    if not users:
        await message.answer("No users found.")
    else:
        response = "Users:\n"
        for user_id, name, warns in users:
            response += f"<b>{name}</b> (<code>{user_id}</code>) - Warns: <b>{warns}</b>\n"
        await message.answer(response)

@dp.message()
async def monitor_bad_words(message: Message):
    if message.chat.type not in ("group", "supergroup"):
        return

    if not message.text:
        return

    if message.chat.type in ('supergroup', 'group'):
        admins = await message.chat.get_administrators()
        admin_user_ids = [admin.user.id for admin in admins]

        if message.from_user.id in admin_user_ids:
            return

    if is_bad_word_in_message(message.text) or is_offensive_with_gemini(message.text):
        try:
            await message.delete()

            group_id = message.chat.id
            kick_enabled, ban_enabled = get_group_config(group_id)

            if kick_enabled:
                await message.chat.kick(message.from_user.id)
                await message.answer(f"🚫 {message.from_user.first_name} has been kicked for using inappropriate language.")

            if ban_enabled:
                await message.chat.ban(message.from_user.id)
                await message.answer(f"🚫 {message.from_user.first_name} has been banned for using inappropriate language.")
            
        except Exception as e:
            print(f"Error: {e}")

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
