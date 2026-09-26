import asyncio
import aiohttp
import random
import sqlite3
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode

# Конфигурация
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # Замените на свой токен
ADMIN_ID = 123456789  # Замените на ваш Telegram ID

# Настройки лимитов
FREE_LIMIT = 5  # Бесплатный лимит прокси в день

# Цены (можно изменить)
PRICE_1_MONTH = "$5"
PRICE_3_MONTHS = "$12"
PRICE_6_MONTHS = "$20"

# Источники прокси
PROXY_APIS = [
    "https://api.proxyscrape.com/v4/?request=getproxies&proxytype=http&timeout=10000&country=all&anonymity=elite",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt",
    "https://raw.githubusercontent.com/Shifuimam/proxy-list/main/http.txt",
]

# База данных
DB_PATH = "proxy_bot.db"


def init_db():
    """Инициализация базы данных"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            free_count INTEGER DEFAULT 0,
            is_paid BOOLEAN DEFAULT FALSE,
            paid_until TEXT,
            total_requests INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            count INTEGER,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    conn.commit()
    conn.close()


init_db()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


def get_user_status(user_id):
    """Получаем статус пользователя"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    if not user:
        cursor.execute('INSERT INTO users (user_id, free_count) VALUES (?, 0)', (user_id,))
        conn.commit()
        conn.close()
        return {'user_id': user_id, 'free_count': 0, 'is_paid': False, 'paid_until': None, 'total_requests': 0}
    
    user_data = {
        'user_id': user[0],
        'username': user[1],
        'free_count': user[2],
        'is_paid': bool(user[3]),
        'paid_until': user[4],
        'total_requests': user[5]
    }
    conn.close()
    return user_data


def update_user_count(user_id, count):
    """Обновляем счетчик запросов"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('UPDATE users SET free_count = free_count + ? WHERE user_id = ?', (count, user_id))
    cursor.execute('UPDATE users SET total_requests = total_requests + ? WHERE user_id = ?', (count, user_id))
    cursor.execute('INSERT INTO requests (user_id, count) VALUES (?, ?)', (user_id, count))
    
    conn.commit()
    conn.close()


def set_paid_status(user_id, months):
    """Устанавливаем платный статус"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    paid_until = (datetime.now() + timedelta(days=30 * months)).strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('UPDATE users SET is_paid = TRUE, paid_until = ? WHERE user_id = ?', (paid_until, user_id))
    
    conn.commit()
    conn.close()
    return paid_until


def check_paid_status(user_id):
    """Проверяем активен ли платный статус"""
    user_data = get_user_status(user_id)
    
    if not user_data['is_paid']:
        return False
    
    if not user_data['paid_until']:
        return False
    
    paid_until = datetime.strptime(user_data['paid_until'], '%Y-%m-%d %H:%M:%S')
    return datetime.now() < paid_until


def reset_daily_limit(user_id):
    """Сбрасываем дневной лимит (если прошел новый день)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT created_at FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    if user:
        created_at = datetime.strptime(user[0], '%Y-%m-%d %H:%M:%S')
        if (datetime.now() - created_at).days >= 1:
            cursor.execute('UPDATE users SET free_count = 0 WHERE user_id = ?', (user_id,))
    
    conn.commit()
    conn.close()


def can_get_proxy(user_id, count):
    """Проверяем может ли пользователь получить прокси"""
    reset_daily_limit(user_id)
    
    is_paid = check_paid_status(user_id)
    
    if is_paid:
        return True, "paid"
    
    user_data = get_user_status(user_id)
    remaining = FREE_LIMIT - user_data['free_count']
    
    if count <= remaining:
        return True, "free"
    
    return False, "limit_exceeded"


async def fetch_proxy_list():
    """Получаем список прокси из всех источников"""
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
    
    return list(set(proxies))


async def fetch_from_url(session, url):
    """Получаем прокси из URL"""
    try:
        async with session.get(url, timeout=10) as response:
            if response.status == 200:
                text = await response.text()
                return parse_proxy_list(text)
    except Exception as e:
        print(f"Ошибка при загрузке {url}: {e}")
    return []


def parse_proxy_list(text):
    """Парсим список прокси"""
    proxies = []
    lines = text.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        if ':' in line:
            parts = line.split(':')
            if len(parts) >= 2:
                ip = parts[0].strip()
                port = parts[1].strip()
                if is_valid_ip(ip) and port.isdigit():
                    proxy = f"{ip}:{port}"
                    if proxy not in proxies:
                        proxies.append(proxy)
    
    return proxies


def is_valid_ip(ip):
    """Проверяем валидность IP"""
    parts = ip.split('.')
    if len(parts) != 4:
        return False
    for part in parts:
        if not part.isdigit() or not 0 <= int(part) <= 255:
            return False
    return True


# ============ КОМАНДЫ БОТА ============

@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    username = message.from_user.username or "Аноним"
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)', (user_id, username))
    conn.commit()
    conn.close()
    
    is_paid = check_paid_status(user_id)
    user_data = get_user_status(user_id)
    remaining = FREE_LIMIT - user_data['free_count']
    
    if is_paid:
        status_text = "✅ Платный доступ"
    else:
        status_text = f"❌ Бесплатный ({remaining}/5 осталось)"
    
    welcome_text = f"""
🚀 Free Proxy Bot 🚀

Бот предоставляет бесплатные HTTP/HTTPS прокси.

{status_text}

📋 Команды:
• /start - Начать
• /proxy - Получить прокси
• /proxy N - Получить N прокси
• /buy - Тарифы
• /my_stats - Статистика
• /help - Справка

⚠️ Бесплатные прокси могут быть нестабильными!
    """
    await message.answer(welcome_text, parse_mode=ParseMode.HTML)


@dp.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help"""
    help_text = """
📖 Справка

🎯 Тарифы:
• Бесплатно: 5 прокси/день
• Платный: неограниченно

📋 Команды:
• /start - Начать
• /proxy - 1 прокси
• /proxy N - N прокси
• /buy - Купить доступ
• /my_stats - Статистика

💡 Проверяйте прокси перед использованием!
    """
    await message.answer(help_text, parse_mode=ParseMode.HTML)


@dp.message(Command("my_stats"))
async def cmd_my_stats(message: Message):
    """Статистика пользователя"""
    user_id = message.from_user.id
    user_data = get_user_status(user_id)
    is_paid = check_paid_status(user_id)
    
    if is_paid:
        paid_until = datetime.strptime(user_data['paid_until'], '%Y-%m-%d %H:%M:%S')
        days_left = (paid_until - datetime.now()).days
        status = f"✅ Платный до {paid_until.strftime('%d.%m.%Y')}\n({days_left} дней)"
    else:
        remaining = FREE_LIMIT - user_data['free_count']
        status = f"❌ Бесплатный ({remaining}/5)"
    
    stats_text = f"""
📊 Ваша статистика

Статус: {status}

Общее:
• Запросов: {user_data['total_requests']}
• Прокси: {user_data['free_count']}

💡 Для неограниченного доступа: /buy
    """
    await message.answer(stats_text, parse_mode=ParseMode.HTML)


@dp.message(Command("buy"))
async def cmd_buy(message: Message):
    """Информация о покупке"""
    buy_text = f"""
💰 Купить доступ

✅ Преимущества:
• Неограниченные прокси
• Быстрый доступ
• Приоритетная поддержка

📋 Тарифы:

1. 1 месяц - {PRICE_1_MONTH}
   Неограниченные прокси

2. 3 месяца - {PRICE_3_MONTHS}
   Экономия 25%

3. 6 месяцев - {PRICE_6_MONTHS}
   Экономия 40%

💳 Как оплатить:
/buy_1 - Купить 1 месяц
/buy_3 - Купить 3 месяца
/buy_6 - Купить 6 месяцев

❓ Вопросы? @admin
    """
    await message.answer(buy_text, parse_mode=ParseMode.HTML)


@dp.message(Command("buy_1"))
async def cmd_buy_1(message: Message):
    """Оплата за 1 месяц"""
    payment_text = f"""
💳 Оплата за 1 месяц ({PRICE_1_MONTH})

Реквизиты:
• Bitcoin: bc1q...
• USDT (TRC20): TW...
• ETH: 0x...

⚠️ Укажите Telegram ID: {message.from_user.id}
⚠️ Отправьте чек после оплаты
⚠️ Доступ через 24 часа

Альтернатива: @admin
    """
    await message.answer(payment_text, parse_mode=ParseMode.HTML)


@dp.message(Command("buy_3"))
async def cmd_buy_3(message: Message):
    """Оплата за 3 месяца"""
    payment_text = f"""
💳 Оплата за 3 месяца ({PRICE_3_MONTHS})

Реквизиты:
• Bitcoin: bc1q...
• USDT (TRC20): TW...
• ETH: 0x...

⚠️ Укажите Telegram ID: {message.from_user.id}
⚠️ Отправьте чек после оплаты
⚠️ Доступ через 24 часа

Альтернатива: @admin
    """
    await message.answer(payment_text, parse_mode=ParseMode.HTML)


@dp.message(Command("buy_6"))
async def cmd_buy_6(message: Message):
    """Оплата за 6 месяцев"""
    payment_text = f"""
💳 Оплата за 6 месяцев ({PRICE_6_MONTHS})

Реквизиты:
• Bitcoin: bc1q...
• USDT (TRC20): TW...
• ETH: 0x...

⚠️ Укажите Telegram ID: {message.from_user.id}
⚠️ Отправьте чек после оплаты
⚠️ Доступ через 24 часа

Альтернатива: @admin
    """
    await message.answer(payment_text, parse_mode=ParseMode.HTML)


@dp.message(Command("proxy"))
async def cmd_proxy(message: Message):
    """Обработчик команды /proxy"""
    user_id = message.from_user.id
    
    args = message.text.split()
    count = 1
    if len(args) > 1:
        try:
            count = int(args[1])
            count = max(1, min(count, 20))
        except ValueError:
            count = 1
    
    can_get, reason = can_get_proxy(user_id, count)
    
    if not can_get:
        user_data = get_user_status(user_id)
        remaining = FREE_LIMIT - user_data['free_count']
        await message.answer(
            f"❌ Лимит превышен!\n\n"
            f"Вы использовали {user_data['free_count']}/{FREE_LIMIT}.\n"
            f"Осталось: {remaining}\n\n"
            f"💡 Для неограниченного доступа: /buy",
            parse_mode=ParseMode.HTML
        )
        return
    
    await message.answer("⏳ Ищем прокси...", parse_mode=ParseMode.HTML)
    
    try:
        proxies = await fetch_proxy_list()
        
        if not proxies:
            await message.answer("❌ Не удалось получить прокси. Попробуйте позже.", parse_mode=ParseMode.HTML)
            return
        
        selected = random.sample(proxies, min(count, len(proxies)))
        
        if reason == "free":
            update_user_count(user_id, count)
        
        response = f"🔥 Прокси ({len(selected)} шт.):\n\n"
        for i, proxy in enumerate(selected, 1):
            response += f"{i}. <code>{proxy}</code>\n"
        
        user_data = get_user_status(user_id)
        if not check_paid_status(user_id):
            remaining = FREE_LIMIT - user_data['free_count']
            response += f"\n📊 Осталось: {remaining}/5"
        else:
            response += f"\n✅ Платный доступ - без ограничений!"
        
        response += f"\n📊 Всего доступно: {len(proxies)}"
        
        await message.answer(response, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}", parse_mode=ParseMode.HTML)


@dp.message(Command("check"))
async def cmd_check(message: Message):
    """Проверка работоспособности прокси"""
    await message.answer("⏳ Проверяем...", parse_mode=ParseMode.HTML)
    
    try:
        proxies = await fetch_proxy_list()
        working = []
        
        test_url = "https://httpbin.org/ip"
        timeout = aiohttp.ClientTimeout(total=5)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for proxy in proxies[:10]:
                try:
                    async with session.get(test_url, proxy=f"http://{proxy}", timeout=3) as response:
                        if response.status == 200:
                            working.append(proxy)
                except:
                    continue
        
        if working:
            response = f"✅ Рабочие ({len(working)}/10):\n\n"
            for i, proxy in enumerate(working, 1):
                response += f"{i}. <code>{proxy}</code>\n"
            await message.answer(response, parse_mode=ParseMode.HTML)
        else:
            await message.answer("❌ Ни один прокси не работает.", parse_mode=ParseMode.HTML)
            
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}", parse_mode=ParseMode.HTML)


@dp.message()
async def echo(message: Message):
    """Обработчик остальных сообщений"""
    await message.answer(
        "Я бот для прокси! Используйте /start, /proxy или /help",
        parse_mode=ParseMode.HTML
    )


async def main():
    """Запуск бота"""
    print("Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
