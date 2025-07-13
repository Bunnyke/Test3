
import re
import os
import json
import asyncio
import requests
from aiogram import Bot, Dispatcher, types, executor
from pyrogram import Client

# 🔐 Replace with your credentials
BOT_TOKEN = "8039426526:AAFSqWU-fRl_gwTPqYLK8yxuS0N9at1hC4s"
API_ID = "20711021"
API_HASH = "84459a13351f6a102e087fdfc3547e31"
PHONE_NUMBER = "+917803946534"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
user_client = Client("my_account", api_id=API_ID, api_hash=API_HASH, phone_number=PHONE_NUMBER)

scrape_queue = asyncio.Queue()
default_limit = 100000

def extract_channel_identifier(raw_input: str):
    raw_input = raw_input.strip()
    if raw_input.startswith("https://t.me/+"):
        return raw_input
    elif raw_input.startswith("https://t.me/"):
        return raw_input.split("/")[-1]
    elif raw_input.startswith("@"):
        return raw_input[1:]
    else:
        return raw_input

def remove_duplicates(messages):
    unique = list(set(messages))
    return unique, len(messages) - len(unique)

async def scrape_messages(user_client, channel_username, limit, start_number=None):
    messages, count = [], 0
    pattern = r'\d{16}\D*\d{2}\D*\d{2,4}\D*\d{3,4}'
    async for message in user_client.search_messages(channel_username):
        if count >= limit:
            break
        text = message.text or message.caption
        if text:
            for match in re.findall(pattern, text):
                values = re.findall(r'\d+', match)
                if len(values) == 4:
                    cc, mo, year, cvv = values
                    year = year[-2:]
                    messages.append(f"{cc}|{mo}|{year}|{cvv}")
                    count += 1
    if start_number:
        messages = [m for m in messages if m.startswith(start_number)]
    return messages[:limit]

async def process_scrape_queue(user_client, bot):
    while True:
        task = await scrape_queue.get()
        message, channel_username, limit, start_number, temp_msg, reply_to_msg_id = task
        try:
            chat_info = await user_client.get_chat(channel_username)
            channel_name = chat_info.title
        except:
            channel_name = str(channel_username)

        user = message.from_user
        first_name = user.first_name
        username = user.username
        scrapper = f"<a href='https://t.me/{username}'>{first_name}</a>" if username else first_name

        results = await scrape_messages(user_client, channel_username, limit, start_number)
        if results:
            unique, dupes = remove_duplicates(results)
            if unique:
                fname = f"cc_{len(unique)}_{channel_name}.txt"
                with open(fname, "w") as f:
                    f.write("\n".join(unique))
                with open(fname, "rb") as f:
                    caption = (
                        f"🧹 <b>CC Scrapped Successful ✅</b>\n"
                        f"━━━━━━━━━━━━━━━━\n"
                        f"<b>Channel:</b> <code>{channel_name}</code>\n"
                        f"<b>Amount:</b> <code>{len(unique)}</code>\n"
                        f"<b>Duplicates Removed:</b> <code>{dupes}</code>\n"
                        f"━━━━━━━━━━━━━━━━\n"
                        f"<b>Scrapped By:</b> {scrapper}"
                    )
                    await temp_msg.delete()
                    await bot.send_document(message.chat.id, f, caption=caption, parse_mode='html', reply_to_message_id=reply_to_msg_id)
                os.remove(fname)
            else:
                await temp_msg.delete()
                await bot.send_message(message.chat.id, "❌ No valid CCs found.", reply_to_message_id=reply_to_msg_id)
        else:
            await temp_msg.delete()
            await bot.send_message(message.chat.id, "❌ No CCs found in that channel.", reply_to_message_id=reply_to_msg_id)
        scrape_queue.task_done()

@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    msg = (
        "<b>👋 Welcome to the MultiTool Bot</b>\n\n"
        "🔧 <b>Available Commands:</b>\n"
        "/fake <code>US</code> – Generate fake user\n"
        "/bin <code>519603</code> – Check BIN info\n"
        "/gen <code>519603 | 10</code> – Generate credit cards\n"
        "/img <code>astronaut riding horse | 42</code> – Generate AI image\n"
        "/scr <code>channel amount [bin]</code> – Scrape cards from a Telegram channel"
    )
    await bot.send_message(message.chat.id, msg, parse_mode='html')

@dp.message_handler(commands=['scr'])
async def scr_cmd(message: types.Message):
    args = message.text.split()[1:]
    reply_to_msg_id = message.reply_to_message.message_id if message.reply_to_message else message.message_id
    if len(args) < 2 or len(args) > 3:
        await bot.send_message(message.chat.id, "<b>⚠️ Use /scr channel amount [bin]</b>", parse_mode='html')
        return
    raw_input = args[0]
    limit = int(args[1])
    start_number = args[2] if len(args) == 3 else None
    if limit > default_limit:
        await bot.send_message(message.chat.id, f"<b>❌ Limit cannot exceed {default_limit}</b>", parse_mode='html')
        return
    channel_identifier = extract_channel_identifier(raw_input)
    try:
        try:
            await user_client.join_chat(channel_identifier)
        except Exception as e:
            if "INVITE_REQUEST_SENT" in str(e):
                await bot.send_message(message.chat.id, "⚠️ Request to join sent. Please wait for admin approval.", parse_mode='html')
                return
            elif "USER_ALREADY_PARTICIPANT" not in str(e):
                await bot.send_message(message.chat.id, f"❌ Could not join the channel.\n<code>{str(e)}</code>", parse_mode='html')
                return
        chat = await user_client.get_chat(channel_identifier)
        channel_username = chat.id
    except Exception as e:
        await bot.send_message(message.chat.id, f"❌ Channel not found or inaccessible.\n<code>{str(e)}</code>", parse_mode='html')
        return
    temp_msg = await bot.send_message(message.chat.id, "⏳ Scraping in progress...", parse_mode='html')
    await scrape_queue.put((message, channel_username, limit, start_number, temp_msg, reply_to_msg_id))

@dp.message_handler(commands=['fake'])
async def fake_user_cmd(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        await message.reply("Usage: <code>/fake US</code>", parse_mode='html')
        return
    try:
        res = requests.get(f"https://randomuser.me/api/?nat={args[1]}").json()
        user = res['results'][0]
        loc = user['location']
        text = (
            f"📍 <b>{loc['country']} Address Generated</b>\n\n"
            f"𝗙𝘂𝗹𝗹 𝗡𝗮𝗺𝗲: {user['name']['first']} {user['name']['last']}\n"
            f"𝗦𝘁𝗿𝗲𝗲𝘁: {loc['street']['number']} {loc['street']['name']}\n"
            f"𝗖𝗶𝘁𝘆: {loc['city']}\n"
            f"𝗦𝘁𝗮𝘁𝗲: {loc['state']}\n"
            f"𝗭𝗶𝗽 𝗖𝗼𝗱𝗲: {loc['postcode']}\n"
            f"𝗣𝗵𝗼𝗻𝗲: {user['phone']}\n"
            f"𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {loc['country']}"
        )
        await message.reply(text, parse_mode='html')
    except Exception as e:
        await message.reply(f"❌ Error fetching data: {e}", parse_mode='html')

@dp.message_handler(commands=['bin'])
async def bin_lookup_cmd(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        await message.reply("Usage: <code>/bin 519603</code>", parse_mode='html')
        return
    bin_code = args[1]
    try:
        res = requests.get(f"https://bins.antipublic.cc/bins/{bin_code}")
        info = res.text.strip()
        await message.reply(f"🔍 <b>𝗕𝗜𝗡 𝗟𝗼𝗼𝗸𝘂𝗽 𝗥𝗲𝘀𝘂𝗹𝘁</b>\n\n𝗕𝗶𝗻 ⇾ <code>{bin_code}</code>\n\n𝐈𝐧𝐟𝐨 ⇾ {info}", parse_mode='html')
    except Exception as e:
        await message.reply(f"❌ Error fetching BIN: {e}", parse_mode='html')

@dp.message_handler(commands=['gen'])
async def gen_cc_cmd(message: types.Message):
    args = message.text.split(None, 1)
    if len(args) < 2 or "|" not in args[1]:
        await message.reply("Usage: <code>/gen 519603 | 10</code>", parse_mode='html')
        return
    try:
        bin_code, count = map(str.strip, args[1].split("|"))
        res = requests.get(f"https://drlabapis.onrender.com/api/ccgenerator?bin={bin_code}&count={count}").json()
        cards = res.get("data", [])
        bininfo = requests.get(f"https://bins.antipublic.cc/bins/{bin_code}").text.strip()
        if not cards:
            await message.reply("❌ No cards generated.", parse_mode='html')
            return
        text = f"𝗕𝗜𝗡: {bin_code}\n𝗔𝗺𝗼𝘂𝗻𝘁: {count}\n\n" + "\n".join(cards) + f"\n\n𝐈𝐧𝐟𝐨: {bininfo}"
        await message.reply(text, parse_mode='html')
    except Exception as e:
        await message.reply(f"❌ Generation failed: {e}", parse_mode='html')

@dp.message_handler(commands=['img'])
async def generate_image_cmd(message: types.Message):
    args = message.text.split(None, 1)
    if len(args) < 2 or "|" not in args[1]:
        await message.reply("Usage: <code>/img astronaut riding horse | 42</code>", parse_mode='html')
        return
    try:
        prompt, seed = map(str.strip, args[1].split("|"))
        url = f"https://image.pollinations.ai/prompt/{prompt.replace(' ', '%20')}?width=1024&height=1024&seed={seed}&nologo=true&model=flux-pro"
        await message.reply_photo(photo=url, caption="🎨 Generated Image", parse_mode='html')
    except Exception as e:
        await message.reply(f"❌ Image generation failed: {e}", parse_mode='html')

async def on_startup(dp):
    await user_client.start()
    asyncio.create_task(process_scrape_queue(user_client, bot))

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
