"""
Free Proxy Bot - High-performance Telegram bot for proxy services
Version: 2.0 - Optimized Architecture
"""

import asyncio
import aiohttp
import random
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, BotCommand
from aiogram.enums import ParseMode

# ==================== CONFIGURATION ====================

@dataclass
class Config:
    BOT_TOKEN: str = "YOUR_BOT_TOKEN_HERE"
    ADMIN_ID: int = 123456789
    
    # Limits
    FREE_LIMIT: int = 5
    MAX_PROXY_PER_REQUEST: int = 20
    PROXY_CACHE_TTL: int = 300
    
    # Pricing
    PRICE_1_MONTH: str = "$5"
    PRICE_3_MONTHS: str = "$12"
    PRICE_6_MONTHS: str = "$20"
    
    # Proxy Sources
    PROXY_SOURCES: List[str] = field(default_factory=lambda: [
        "https://api.proxyscrape.com/v4/?request=getproxies&proxytype=http&timeout=10000&country=all&anonymity=elite",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt",
        "https://raw.githubusercontent.com/Shifuimam/proxy-list/main/http.txt",
    ])
    
    # Database
    DB_PATH: str = "proxy_bot.db"
    
    # Timeouts
    REQUEST_TIMEOUT: int = 10
    PROXY_CHECK_TIMEOUT: int = 3


config = Config()

# ==================== LOGGING ====================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== DATABASE ====================

class Database:
    """SQLite Database Manager with connection pooling and optimized queries"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize database tables"""
        with sqlite3.connect(self.db_path, check_same_thread=False) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    free_count INTEGER DEFAULT 0,
                    is_paid BOOLEAN DEFAULT FALSE,
                    paid_until TEXT,
                    total_requests INTEGER DEFAULT 0,
                    last_request_date TEXT,
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
            
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_user_id ON users(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_requests_user_id ON requests(user_id)')
            
            conn.commit()
    
    def get_user(self, user_id: int) -> Dict:
        """Get user data with auto-initialization"""
        with sqlite3.connect(self.db_path, check_same_thread=False) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            user = cursor.fetchone()
            
            if not user:
                today = datetime.now().strftime('%Y-%m-%d')
                cursor.execute(
                    'INSERT INTO users (user_id, username, free_count, last_request_date) VALUES (?, ?, 0, ?)',
                    (user_id, "Anonymous", today)
                )
                conn.commit()
                return {
                    'user_id': user_id,
                    'username': "Anonymous",
                    'free_count': 0,
                    'is_paid': False,
                    'paid_until': None,
                    'total_requests': 0,
                    'last_request_date': today
                }
            
            return {
                'user_id': user[0],
                'username': user[1],
                'free_count': user[2],
                'is_paid': bool(user[3]),
                'paid_until': user[4],
                'total_requests': user[5],
                'last_request_date': user[6]
            }
    
    def update_user_count(self, user_id: int, count: int):
        """Update user request count with daily reset check"""
        today = datetime.now().strftime('%Y-%m-%d')
        
        with sqlite3.connect(self.db_path, check_same_thread=False) as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT last_request_date FROM users WHERE user_id = ?', (user_id,))
            user = cursor.fetchone()
            
            if user and user[0] != today:
                cursor.execute('UPDATE users SET free_count = 0, last_request_date = ? WHERE user_id = ?', (today, user_id))
            
            cursor.execute('UPDATE users SET free_count = free_count + ?, total_requests = total_requests + ? WHERE user_id = ?',
                          (count, count, user_id))
            cursor.execute('INSERT INTO requests (user_id, count) VALUES (?, ?)', (user_id, count))
            
            conn.commit()
    
    def set_paid_status(self, user_id: int, months: int) -> str:
        """Set premium status for user"""
        paid_until = (datetime.now() + timedelta(days=30 * months)).strftime('%Y-%m-%d %H:%M:%S')
        
        with sqlite3.connect(self.db_path, check_same_thread=False) as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET is_paid = TRUE, paid_until = ? WHERE user_id = ?',
                          (paid_until, user_id))
            conn.commit()
        
        return paid_until
    
    def is_paid_active(self, user_id: int) -> bool:
        """Check if user has active premium status"""
        user = self.get_user(user_id)
        
        if not user or not user['is_paid'] or not user['paid_until']:
            return False
        
        try:
            paid_until = datetime.strptime(user['paid_until'], '%Y-%m-%d %H:%M:%S')
            return datetime.now() < paid_until
        except:
            return False
    
    def can_get_proxy(self, user_id: int, count: int) -> Tuple[bool, str]:
        """Check if user can get proxies"""
        is_paid = self.is_paid_active(user_id)
        
        if is_paid:
            return True, "paid"
        
        user = self.get_user(user_id)
        remaining = config.FREE_LIMIT - user['free_count']
        
        if count <= remaining:
            return True, "free"
        
        return False, "limit_exceeded"
    
    def get_user_stats(self, user_id: int) -> Dict:
        """Get user statistics"""
        user = self.get_user(user_id)
        is_paid = self.is_paid_active(user_id)
        
        stats = {
            'user_id': user['user_id'],
            'username': user['username'],
            'total_requests': user['total_requests'],
            'free_count': user['free_count'],
            'is_paid': is_paid
        }
        
        if is_paid and user['paid_until']:
            try:
                paid_until = datetime.strptime(user['paid_until'], '%Y-%m-%d %H:%M:%S')
                stats['days_left'] = (paid_until - datetime.now()).days
                stats['paid_until'] = paid_until.strftime('%d.%m.%Y')
            except:
                pass
        
        return stats


# Initialize database
db = Database(config.DB_PATH)

# ==================== PROXY MANAGER ====================

class ProxyManager:
    """Manages proxy fetching, caching, and validation with async operations"""
    
    def __init__(self):
        self._cache: List[str] = []
        self._cache_time: Optional[datetime] = None
    
    async def fetch_proxy_list(self, force_refresh: bool = False) -> List[str]:
        """Fetch proxy list with caching"""
        if not force_refresh and self._cache and self._cache_time:
            if (datetime.now() - self._cache_time).seconds < config.PROXY_CACHE_TTL:
                logger.debug("Returning cached proxies")
                return self._cache.copy()
        
        logger.info("Fetching fresh proxy list...")
        
        try:
            proxies = await self._fetch_all_sources()
            proxies = list(set(proxies))
            proxies = [p for p in proxies if self._is_valid_proxy(p)]
            
            self._cache = proxies
            self._cache_time = datetime.now()
            
            logger.info(f"Fetched {len(proxies)} proxies from {len(config.PROXY_SOURCES)} sources")
            return proxies
        except Exception as e:
            logger.error(f"Error fetching proxies: {e}")
            return self._cache.copy() if self._cache else []
    
    async def _fetch_all_sources(self) -> List[str]:
        """Fetch proxies from all sources concurrently"""
        connector = aiohttp.TCPConnector(limit=10, force_close=True)
        timeout = aiohttp.ClientTimeout(total=config.REQUEST_TIMEOUT)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            tasks = [self._fetch_source(session, url) for url in config.PROXY_SOURCES]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            proxies = []
            for result in results:
                if isinstance(result, list):
                    proxies.extend(result)
            
            return proxies
    
    async def _fetch_source(self, session: aiohttp.ClientSession, url: str) -> List[str]:
        """Fetch proxies from a single source"""
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    text = await response.text()
                    return self._parse_proxy_list(text)
        except Exception as e:
            logger.warning(f"Failed to fetch {url}: {e}")
        return []
    
    def _parse_proxy_list(self, text: str) -> List[str]:
        """Parse proxy list from text"""
        proxies = []
        for line in text.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            
            if ':' in line:
                parts = line.split(':')
                if len(parts) >= 2:
                    ip, port = parts[0].strip(), parts[1].strip()
                    if self._is_valid_ip(ip) and port.isdigit():
                        proxies.append(f"{ip}:{port}")
        
        return proxies
    
    def _is_valid_ip(self, ip: str) -> bool:
        """Validate IP address"""
        parts = ip.split('.')
        if len(parts) != 4:
            return False
        return all(part.isdigit() and 0 <= int(part) <= 255 for part in parts)
    
    def _is_valid_proxy(self, proxy: str) -> bool:
        """Validate proxy format"""
        if ':' not in proxy:
            return False
        ip, port = proxy.rsplit(':', 1)
        return self._is_valid_ip(ip) and port.isdigit() and 1 <= int(port) <= 65535
    
    async def check_proxy(self, proxy: str, timeout: int = 3) -> bool:
        """Check if proxy is working"""
        try:
            test_url = "https://httpbin.org/ip"
            connector = aiohttp.TCPConnector(force_close=True)
            timeout_obj = aiohttp.ClientTimeout(total=timeout)
            
            async with aiohttp.ClientSession(connector=connector, timeout=timeout_obj) as session:
                async with session.get(test_url, proxy=f"http://{proxy}", timeout=timeout) as response:
                    return response.status == 200
        except Exception as e:
            logger.debug(f"Proxy {proxy} failed: {e}")
            return False
    
    async def get_working_proxies(self, count: int = 10) -> List[str]:
        """Get list of working proxies"""
        proxies = await self.fetch_proxy_list()
        if not proxies:
            return []
        
        working = []
        tasks = [self.check_proxy(proxy) for proxy in proxies[:min(count * 3, len(proxies))]]
        results = await asyncio.gather(*tasks)
        
        for proxy, is_working in zip(proxies[:min(count * 3, len(proxies))], results):
            if is_working:
                working.append(proxy)
                if len(working) >= count:
                    break
        
        return working


proxy_manager = ProxyManager()

# ==================== ROUTERS ====================

router = Router()


# ==================== HANDLERS ====================

@router.message(CommandStart())
async def cmd_start(message: Message):
    """Start command handler"""
    user_id = message.from_user.id
    username = message.from_user.username or "Аноним"
    
    db.get_user(user_id)
    
    is_paid = db.is_paid_active(user_id)
    stats = db.get_user_stats(user_id)
    remaining = config.FREE_LIMIT - stats['free_count']
    
    status_text = "✅ Платный доступ" if is_paid else f"❌ Бесплатный ({remaining}/5)"
    
    welcome_text = f"""🚀 <b>Free Proxy Bot v2.0</b> 🚀

Бот предоставляет HTTP/HTTPS прокси.

<b>Статус:</b> {status_text}

<b>Команды:</b>
/start - Начать
/proxy - Получить прокси
/buy - Тарифы
/my_stats - Статистика
/help - Справка

⚠️ Бесплатные прокси могут быть нестабильными!
"""
    
    await message.answer(welcome_text, parse_mode=ParseMode.HTML)


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Help command handler"""
    help_text = """📖 <b>Справка</b>

<b>🎯 Тарифы:</b>
• Бесплатно: 5 прокси/день
• Платный: неограниченно

<b>📋 Команды:</b>
/start - Начать
/proxy - 1 прокси
/proxy N - N прокси
/buy - Купить доступ
/my_stats - Статистика
/check - Проверить прокси

<b>💡 Совет:</b> Проверяйте прокси перед использованием!
"""
    await message.answer(help_text, parse_mode=ParseMode.HTML)


@router.message(Command("my_stats"))
async def cmd_my_stats(message: Message):
    """User statistics handler"""
    user_id = message.from_user.id
    stats = db.get_user_stats(user_id)
    
    if stats['is_paid'] and 'paid_until' in stats:
        status = f"✅ Платный до {stats['paid_until']} ({stats.get('days_left', 0)} дней)"
    else:
        remaining = config.FREE_LIMIT - stats['free_count']
        status = f"❌ Бесплатный ({remaining}/5)"
    
    stats_text = f"""📊 <b>Ваша статистика</b>

<b>Статус:</b> {status}

<b>Общее:</b>
• Запросов: {stats['total_requests']}
• Прокси: {stats['free_count']}

💡 Для неограниченного доступа: /buy
"""
    await message.answer(stats_text, parse_mode=ParseMode.HTML)


@router.message(Command("buy"))
async def cmd_buy(message: Message):
    """Buy command handler"""
    buy_text = """💰 <b>Купить доступ</b>

<b>✅ Преимущества:</b>
• Неограниченные прокси
• Быстрый доступ
• Приоритетная поддержка

<b>📋 Тарифы:</b>
1. 1 месяц - $5
2. 3 месяца - $12 (экономия 25%)
3. 6 месяцев - $20 (экономия 40%)

<b>💳 Как оплатить:</b>
/buy_1 - Купить 1 месяц
/buy_3 - Купить 3 месяца
/buy_6 - Купить 6 месяцев

❓ Вопросы? @admin
"""
    await message.answer(buy_text, parse_mode=ParseMode.HTML)


@router.message(Command("buy_1", "buy_3", "buy_6"))
async def cmd_buy_plan(message: Message):
    """Buy plan handler"""
    command = message.text.split()[0]
    months = 1 if command == "/buy_1" else 3 if command == "/buy_3" else 6
    price = config.PRICE_1_MONTH if months == 1 else config.PRICE_3_MONTHS if months == 3 else config.PRICE_6_MONTHS
    
    payment_text = f"""💳 <b>Оплата за {months} месяц{'а' if months in [2,3,4] else 'ев' if months >=5 else ''} ({price})</b>

<b>Реквизиты:</b>
• Bitcoin: bc1q...
• USDT (TRC20): TW...
• ETH: 0x...

<b>⚠️ Важно:</b>
• Укажите Telegram ID: {message.from_user.id}
• Отправьте чек после оплаты
• Доступ через 24 часа

Альтернатива: @admin
"""
    await message.answer(payment_text, parse_mode=ParseMode.HTML)


@router.message(Command("proxy"))
async def cmd_proxy(message: Message):
    """Proxy command handler with rate limiting"""
    user_id = message.from_user.id
    
    args = message.text.split()
    count = 1
    if len(args) > 1:
        try:
            count = max(1, min(int(args[1]), config.MAX_PROXY_PER_REQUEST))
        except ValueError:
            count = 1
    
    can_get, reason = db.can_get_proxy(user_id, count)
    
    if not can_get:
        stats = db.get_user_stats(user_id)
        remaining = config.FREE_LIMIT - stats['free_count']
        await message.answer(
            f"❌ <b>Лимит превышен!</b>\n\n"
            f"Вы использовали {stats['free_count']}/{config.FREE_LIMIT}.\n"
            f"Осталось: <b>{remaining}</b>\n\n"
            f"💡 Для неограниченного доступа: /buy",
            parse_mode=ParseMode.HTML
        )
        return
    
    await message.answer("⏳ Ищем прокси...", parse_mode=ParseMode.HTML)
    
    try:
        proxies = await proxy_manager.fetch_proxy_list()
        
        if not proxies:
            await message.answer("❌ Не удалось получить прокси. Попробуйте позже.", parse_mode=ParseMode.HTML)
            return
        
        selected = random.sample(proxies, min(count, len(proxies)))
        
        if reason == "free":
            db.update_user_count(user_id, count)
        
        response = f"🔥 <b>Прокси ({len(selected)} шт.):</b>\n\n"
        for i, proxy in enumerate(selected, 1):
            response += f"{i}. <code>{proxy}</code>\n"
        
        if reason == "free":
            stats = db.get_user_stats(user_id)
            remaining = config.FREE_LIMIT - stats['free_count']
            response += f"\n📊 Осталось: {remaining}/5"
        else:
            response += f"\n✅ Платный доступ - без ограничений!"
        
        response += f"\n📊 Всего доступно: {len(proxies)}"
        
        await message.answer(response, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        logger.error(f"Error in /proxy: {e}")
        await message.answer(f"❌ Ошибка: {e}", parse_mode=ParseMode.HTML)


@router.message(Command("check"))
async def cmd_check(message: Message):
    """Check command handler"""
    await message.answer("⏳ Проверяем прокси...", parse_mode=ParseMode.HTML)
    
    try:
        working = await proxy_manager.get_working_proxies(10)
        
        if working:
            response = f"✅ <b>Рабочие ({len(working)}/10):</b>\n\n"
            for i, proxy in enumerate(working, 1):
                response += f"{i}. <code>{proxy}</code>\n"
            await message.answer(response, parse_mode=ParseMode.HTML)
        else:
            await message.answer("❌ Ни один прокси не работает.", parse_mode=ParseMode.HTML)
            
    except Exception as e:
        logger.error(f"Error in /check: {e}")
        await message.answer(f"❌ Ошибка: {e}", parse_mode=ParseMode.HTML)


@router.message()
async def echo(message: Message):
    """Echo handler"""
    await message.answer(
        "Я бот для прокси! Используйте /start, /proxy или /help",
        parse_mode=ParseMode.HTML
    )


# ==================== BOT SETUP ====================

@asynccontextmanager
async def lifespan(bot: Bot):
    """Bot lifespan manager"""
    commands = [
        BotCommand(command="start", description="Начать"),
        BotCommand(command="help", description="Справка"),
        BotCommand(command="proxy", description="Получить прокси"),
        BotCommand(command="check", description="Проверить прокси"),
        BotCommand(command="buy", description="Купить доступ"),
        BotCommand(command="my_stats", description="Статистика"),
    ]
    await bot.set_my_commands(commands)
    logger.info("Bot started successfully")
    yield
    logger.info("Bot stopped")


async def main():
    """Main entry point"""
    if config.BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("BOT_TOKEN not configured! Set your bot token in config.")
        return
    
    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    
    async with lifespan(bot):
        await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
