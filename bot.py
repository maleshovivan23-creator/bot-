import asyncio
import aiohttp
import random
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode

# Конфигурация
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # Замените на свой токен

# Список API для получения бесплатных прокси
PROXY_APIS = [
    "https://api.proxyscrape.com/v3/?request=getproxies&proxytype=http&timeout=10000&country=all",
    "https://www.sslproxies.org/",
    "https://free-proxy-list.net/",
    "https://raw.githubusercontent.com/jundymek/free-proxy/main/proxy_list.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt",
]

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


async def fetch_proxy_list():
    """Получаем список прокси из всех доступных источников"""
    proxies = []
    
    async with aiohttp.ClientSession() as session:
        tasks = []
        for api_url in PROXY_APIS:
            try:
                tasks.append(fetch_from_url(session, api_url))
            except:
                continue
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, list):
                proxies.extend(result)
    
    # Удаляем дубликаты
    unique_proxies = list(set(proxies))
    return unique_proxies


async def fetch_from_url(session, url):
    """Получаем прокси из конкретного URL"""
    try:
        async with session.get(url, timeout=10) as response:
            if response.status == 200:
                text = await response.text()
                return parse_proxy_list(text, url)
    except Exception as e:
        print(f"Ошибка при загрузке {url}: {e}")
    return []


def parse_proxy_list(text, source_url):
    """Парсим текстовый список прокси"""
    proxies = []
    lines = text.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Формат: IP:PORT
        if ':' in line and line.count(':') in [1, 2]:
            parts = line.split(':')
            if len(parts) >= 2:
                ip = parts[0].strip()
                port = parts[1].strip()
                if is_valid_ip(ip) and port.isdigit():
                    proxy = f"{ip}:{port}"
                    if proxy not in proxies:
                        proxies.append(proxy)
        
        # Формат: IP:PORT:USER:PASS (если есть авторизация)
        elif line.count(':') >= 3:
            parts = line.split(':')
            ip = parts[0].strip()
            port = parts[1].strip()
            if is_valid_ip(ip) and port.isdigit():
                proxy = f"{ip}:{port}"
                if proxy not in proxies:
                    proxies.append(proxy)
    
    return proxies


def is_valid_ip(ip):
    """Проверяем валидность IP адреса"""
    parts = ip.split('.')
    if len(parts) != 4:
        return False
    for part in parts:
        if not part.isdigit() or not 0 <= int(part) <= 255:
            return False
    return True


@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    welcome_text = """
🚀 <b>🔥 Free Proxy Bot 🔥</b> 🚀

Этот бот предоставляет <b>бесплатные прокси</b> для тестирования и разработки.

📋 <b>Доступные команды:</b>
• /start - Начать работу
• /proxy - Получить случайный прокси
• /proxy 10 - Получить 10 прокси
• /help - Показать справку

⚠️ <b>Внимание:</b> Бесплатные прокси могут быть нестабильными. Используйте на свой страх и риск!
    """
    await message.answer(welcome_text, parse_mode=ParseMode.HTML)


@dp.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help"""
    help_text = """
📖 <b>📚 Справка по боту 📚</b> 📖

<b>Что умеет этот бот:</b>
• Предоставляет бесплатные HTTP/HTTPS прокси
• Прокси обновляются автоматически из нескольких источников
• Можно запросить несколько прокси за раз

<b>Команды:</b>
• /start - Начать работу с ботом
• /proxy - Получить 1 случайный прокси
• /proxy N - Получить N прокси (максимум 20)
• /help - Эта справка

<b>Пример использования:</b>
<code>/proxy</code> - один прокси
<code>/proxy 5</code> - пять прокси

💡 <b>Совет:</b> Проверяйте прокси перед использованием!
    """
    await message.answer(help_text, parse_mode=ParseMode.HTML)


@dp.message(Command("proxy"))
async def cmd_proxy(message: Message):
    """Обработчик команды /proxy"""
    await message.answer("⏳ Ищем доступные прокси...", parse_mode=ParseMode.HTML)
    
    try:
        # Получаем количество прокси из команды
        args = message.text.split()
        count = 1
        if len(args) > 1:
            try:
                count = int(args[1])
                count = max(1, min(count, 20))  # Ограничиваем от 1 до 20
            except ValueError:
                count = 1
        
        # Получаем список прокси
        proxies = await fetch_proxy_list()
        
        if not proxies:
            await message.answer("❌ К сожалению, не удалось получить прокси. Попробуйте позже.", 
                               parse_mode=ParseMode.HTML)
            return
        
        # Выбираем случайные прокси
        selected = random.sample(proxies, min(count, len(proxies)))
        
        # Формируем ответ
        response = f"🔥 <b>Список прокси ({len(selected)} шт.):</b>\n\n"
        for i, proxy in enumerate(selected, 1):
            response += f"{i}. <code>{proxy}</code>\n"
        
        response += f"\n📊 <b>Всего доступно:</b> {len(proxies)} прокси"
        
        await message.answer(response, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        await message.answer(f"❌ Произошла ошибка: {e}", parse_mode=ParseMode.HTML)


@dp.message(Command("check"))
async def cmd_check(message: Message):
    """Проверяем работоспособность прокси"""
    await message.answer("⏳ Проверяем прокси...", parse_mode=ParseMode.HTML)
    
    try:
        proxies = await fetch_proxy_list()
        working = []
        
        # Проверяем первые 10 прокси
        test_url = "https://httpbin.org/ip"
        timeout = aiohttp.ClientTimeout(total=5)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for proxy in proxies[:10]:
                try:
                    async with session.get(
                        test_url,
                        proxy=f"http://{proxy}",
                        timeout=3
                    ) as response:
                        if response.status == 200:
                            working.append(proxy)
                except:
                    continue
        
        if working:
            response = f"✅ <b>Рабочие прокси ({len(working)}/10):</b>\n\n"
            for i, proxy in enumerate(working, 1):
                response += f"{i}. <code>{proxy}</code>\n"
            await message.answer(response, parse_mode=ParseMode.HTML)
        else:
            await message.answer("❌ К сожалению, ни один прокси не работает.", 
                               parse_mode=ParseMode.HTML)
            
    except Exception as e:
        await message.answer(f"❌ Ошибка при проверке: {e}", parse_mode=ParseMode.HTML)


@dp.message()
async def echo(message: Message):
    """Обработчик остальных сообщений"""
    await message.answer(
        "🤖 Я бот для прокси! Используйте команды /start, /proxy или /help",
        parse_mode=ParseMode.HTML
    )


async def main():
    """Запуск бота"""
    print("🤖 Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
