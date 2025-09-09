import asyncio
import re
from pyrogram import Client, filters
from pyrogram.types import Message, ChatPermissions
from pyrogram.enums import ChatMemberStatus

# Настройки API
API_ID = 111111 #заменить с my.telegram.org
API_HASH = "xxxxxx" #заменить с my.telegram.org

group_settings = {}
last_processed_messages = {}
active_alerts = {}

app = Client(
    "my_userbot", 
    api_id=API_ID, 
    api_hash=API_HASH
)

@app.on_message(filters.group & filters.new_chat_members)
async def on_new_member(client, message: Message):
    for member in message.new_chat_members:
        if member.id == (await client.get_me()).id:
            await client.send_message(
                message.chat.id,
                "Здравствуйте! Я - помощник, который будет Вас информировать об опасности БПЛА.\n"
                "Чтобы меня настроить отправьте /start в чат (отправить могут только админы)"
            )
            break

@app.on_message(filters.group & filters.command("start"))
async def start_command(client, message: Message):
    try:
        member = await client.get_chat_member(message.chat.id, message.from_user.id)
        if member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            await message.reply("❌ Только администраторы могут настраивать меня!")
            return
    except Exception:
        await message.reply("❌ Не удалось проверить ваши права!")
        return

    await message.reply(
        "🔑 Пожалуйста, введите ключевые слова для мониторинга (через запятую):\n"
        "Пример: Никольское, Таврово, Дубовое"
    )
    
    group_settings[message.chat.id] = {"waiting_for_keywords": True, "admin_id": message.from_user.id}

@app.on_message(filters.group & filters.text & ~filters.command("start"))
async def handle_keywords(client, message: Message):
    chat_id = message.chat.id
    
    if (chat_id in group_settings and 
        group_settings[chat_id].get("waiting_for_keywords") and 
        group_settings[chat_id].get("admin_id") == message.from_user.id):
        
        group_settings[chat_id]["waiting_for_keywords"] = False
        
        keywords = [word.strip() for word in message.text.split(",") if word.strip()]
        
        if not keywords:
            await message.reply("❌ Неверный формат! Пожалуйста, введите ключевые слова через запятую.")
            return
        
        if chat_id not in group_settings:
            group_settings[chat_id] = {}
        group_settings[chat_id]["keywords"] = keywords
        
        await message.reply(
            f"✅ Настройки сохранены!\n"
            f"Ключевые слова: {', '.join(keywords)}\n"
        )
        
        asyncio.create_task(monitor_channel(client, chat_id, keywords))

async def monitor_channel(client, chat_id, keywords):
    channel_id = -1002820362754  # ID канала @BelgorodDRONE
    
    try:
        async for message in client.get_chat_history(channel_id, limit=1):
            if message:
                last_processed_messages[chat_id] = message.id
                break
        
        print(f"🚀 Начал мониторинг канала для группы {chat_id} с ключевыми словами: {keywords}")
        
        while True:
            try:
                new_messages = []
                async for message in client.get_chat_history(channel_id, limit=5):
                    if message.id > last_processed_messages.get(chat_id, 0):
                        new_messages.append(message)
                
                for message in reversed(new_messages):
                    if message.text:
                        await check_and_forward_message(client, chat_id, keywords, message)
                        last_processed_messages[chat_id] = message.id
                
                await asyncio.sleep(10)
                
            except Exception as e:
                print(f"Ошибка в цикле мониторинга для группы {chat_id}: {e}")
                await asyncio.sleep(60)
            
    except Exception as e:
        print(f"Ошибка при запуске мониторинга канала для группы {chat_id}: {e}")

async def check_and_forward_message(client, chat_id, keywords, message):
    text = message.text.lower()
    
    keyword_found = None
    for keyword in keywords:
        keyword_lower = keyword.lower()
        if (keyword_lower in text.split() or 
            keyword_lower in re.findall(r'\b\w+\b', text) or
            f" {keyword_lower} " in f" {text} "):
            
            keyword_found = keyword
            break
    
    has_otboy = any(word in text for word in ["отбой", "отбоя", "отбою"])
    
    if keyword_found and not has_otboy:
        try:
            await client.send_message(chat_id, f"{message.text}")
            print(f"🚨 Отправлена тревога в группу {chat_id} по ключевому слову '{keyword_found}'")
            
            active_alerts[chat_id] = {
                "keyword": keyword_found,
                "message_id": message.id,
                "timestamp": asyncio.get_event_loop().time()
            }
            
        except Exception as e:
            print(f"Ошибка при отправке сообщения в группу {chat_id}: {e}")
    
    elif keyword_found and has_otboy:
        try:
            await client.send_message(chat_id, f"{message.text}")
            print(f"✅ Отправлен отбой в группу {chat_id} по ключевому слову '{keyword_found}'")
            
            if chat_id in active_alerts:
                del active_alerts[chat_id]
                
        except Exception as e:
            print(f"Ошибка при отправке отбоя в группу {chat_id}: {e}")
    
    elif has_otboy and chat_id in active_alerts:
        try:
            await client.send_message(chat_id, f"{message.text}")
            print(f"✅ Отправлен отбой в группу {chat_id} (без ключевого слова)")
            
            del active_alerts[chat_id]
                
        except Exception as e:
            print(f"Ошибка при отправке отбоя в группу {chat_id}: {e}")

@app.on_message(filters.private)
async def ignore_private_messages(client, message: Message):
    pass

if __name__ == "__main__":
    print("Юзер-бот запускается...")
    app.run()
