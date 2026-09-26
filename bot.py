"""
╔════════════════════════════════════════════════════════════════════════════╗
║                    FREE PROXY BOT v3.0 - PREMIUM EDITION                     ║
║                         🚀 Ultra-Fast Proxy Provider 🚀                      ║
╚════════════════════════════════════════════════════════════════════════════╝

Telegram Bot for Free & Premium Proxy Services
Architecture: Async, Modular, Cached, Optimized
Author: Vibe Code
Version: 3.0
"""

import asyncio
import aiohttp
import random
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from contextlib import asynccontextmanager
from functools import lru_cache

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.types import Message, BotCommand, User
from aiogram.enums import ParseMode
from aiogram.utils.markdown import hide_link

# ============================================================================
# ⚙️  CONFIGURATION - Настройки бота
# ============================================================================

@dataclass
class BotConfig:
    """Конфигурация бота с типовой проверкой"""
    
    # 🤖 Токен бота (ОБЯЗАТЕЛЬНО ИЗМЕНИТЬ!)
    BOT_TOKEN: str = "YOUR_BOT_TOKEN_HERE"
    
    # 👑 Admin ID для уведомлений
    ADMIN_ID: int = 123456789
    
    # 📊 Лимиты
    FREE_LIMIT: int = 5          # Бесплатных прокси в день
    MAX_PROXY_REQUEST: int = 20  # Максимум за один запрос
    CACHE_TTL: int = 300        # Время кэша прокси (секунды)
    
    # 💰 Цены
    PRICES: Dict[str, str] = field(default_factory=lambda: {
        "1": "$5",
        "3": "$12",
        "6": "$20"
    })
    
    # 🌐 Источники прокси
    PROXY_SOURCES: List[str] = field(default_factory=lambda: [
        # Elite proxies
        "https://api.proxyscrape.com/v4/?request=getproxies&proxytype=http&timeout=10000&country=all&anonymity=elite",
        # GitHub repositories
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt",
        "https://raw.githubusercontent.com/Shifuimam/proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxy/http.txt",
        "https://raw.githubusercontent.com/undergroundworld/Proxy-List/master/http.txt",
    ])
    
    # ⏱️ Таймауты
    REQUEST_TIMEOUT: int = 10
    PROXY_CHECK_TIMEOUT: int = 3
    DB_TIMEOUT: int = 5
    
    # 🎨 Оформление
    BOT_NAME: str = "🔥 Free Proxy Bot v3.0"
    FOOTER: str = "\n\n💡 <i>Premium proxies for everyone!</i>"


# Инициализация конфигурации
config = BotConfig()

# ============================================================================
# 📝 LOGGING - Система логирования
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("ProxyBot")

# ============================================================================
# 🗃️  DATABASE - Работа с базой данных
# ============================================================================

class ProxyBotDatabase:
    """
    Высокопроизводительная база данных для бота
    Использует SQLite с оптимизированными запросами
    """
    
    def __init__(self, db_path: str = "proxy_bot.db"):
        self.db_path = db_path
        self._initialize()
        logger.info(f"🗃️  Database initialized: {db_path}")
    
    def _initialize(self):
        """Инициализация таблиц БД"""
        with sqlite3.connect(self.db_path, timeout=config.DB_TIMEOUT) as conn:
            cursor = conn.cursor()
            
            # Таблица пользователей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT DEFAULT 'Anonymous',
                    first_name TEXT,
                    last_name TEXT,
                    free_count INTEGER DEFAULT 0,
                    is_premium BOOLEAN DEFAULT FALSE,
                    premium_until TEXT,
                    total_requests INTEGER DEFAULT 0,
                    last_request_date TEXT DEFAULT CURRENT_TIMESTAMP,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица запросов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    count INTEGER NOT NULL,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Индексы для ускорения
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_id ON users(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_requests_user ON requests(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_requests_time ON requests(timestamp)')
            
            conn.commit()
    
    def _get_connection(self):
        """Получаем соединение с БД"""
        return sqlite3.connect(self.db_path, timeout=config.DB_TIMEOUT)
    
    def get_or_create_user(self, user: User) -> Dict[str, Any]:
        """Получаем или создаем пользователя"""
        user_id = user.id
        username = user.username or ""
        first_name = user.first_name or ""
        last_name = user.last_name or ""
        today = datetime.now().strftime('%Y-%m-%d')
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Проверяем, есть ли пользователь
            cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            existing = cursor.fetchone()
            
            if not existing:
                cursor.execute('''
                    INSERT INTO users (user_id, username, first_name, last_name, last_request_date)
                    VALUES (?, ?, ?, ?, ?)
                ''', (user_id, username, first_name, last_name, today))
                conn.commit()
                
                return {
                    'user_id': user_id,
                    'username': username,
                    'first_name': first_name,
                    'last_name': last_name,
                    'free_count': 0,
                    'is_premium': False,
                    'premium_until': None,
                    'total_requests': 0,
                    'last_request_date': today
                }
            
            # Обновляем информацию о пользователе
            cursor.execute('''
                UPDATE users 
                SET username = ?, first_name = ?, last_name = ?
                WHERE user_id = ?
            ''', (username, first_name, last_name, user_id))
            conn.commit()
            
            return self._user_to_dict(existing)
    
    def _user_to_dict(self, user_tuple: tuple) -> Dict[str, Any]:
        """Конвертируем кортеж в словарь"""
        return {
            'user_id': user_tuple[0],
            'username': user_tuple[1],
            'first_name': user_tuple[2],
            'last_name': user_tuple[3],
            'free_count': user_tuple[4],
            'is_premium': bool(user_tuple[5]),
            'premium_until': user_tuple[6],
            'total_requests': user_tuple[7],
            'last_request_date': user_tuple[8]
        }
    
    def update_request_count(self, user_id: int, count: int):
        """Обновляем счетчик запросов с авто-сбросом"""
        today = datetime.now().strftime('%Y-%m-%d')
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Проверяем, новый ли день
            cursor.execute('SELECT last_request_date FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            
            if result and result[0] != today:
                # Сбрасываем счетчик
                cursor.execute('UPDATE users SET free_count = 0, last_request_date = ? WHERE user_id = ?',
                              (today, user_id))
            
            # Обновляем счетчики
            cursor.execute('''
                UPDATE users 
                SET free_count = free_count + ?,
                    total_requests = total_requests + ?
                WHERE user_id = ?
            ''', (count, count, user_id))
            
            # Логируем запрос
            cursor.execute('INSERT INTO requests (user_id, count) VALUES (?, ?)',
                          (user_id, count))
            
            conn.commit()
    
    def set_premium(self, user_id: int, months: int) -> str:
        """Устанавливаем премиум статус"""
        premium_until = (datetime.now() + timedelta(days=30 * months)).strftime('%Y-%m-%d %H:%M:%S')
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users 
                SET is_premium = TRUE, 
                    premium_until = ?,
                    free_count = 0
                WHERE user_id = ?
            ''', (premium_until, user_id))
            conn.commit()
        
        logger.info(f"👑 User {user_id} upgraded to premium until {premium_until}")
        return premium_until
    
    def is_premium_active(self, user_id: int) -> bool:
        """Проверяем активен ли премиум"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT is_premium, premium_until FROM users WHERE user_id = ?',
                          (user_id,))
            result = cursor.fetchone()
            
            if not result or not result[0] or not result[1]:
                return False
            
            try:
                premium_until = datetime.strptime(result[1], '%Y-%m-%d %H:%M:%S')
                return datetime.now() < premium_until
            except:
                return False
    
    def can_get_proxy(self, user_id: int, count: int) -> Tuple[bool, str]:
        """Проверяем может ли пользователь получить прокси"""
        is_premium = self.is_premium_active(user_id)
        
        if is_premium:
            return True, "premium"
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT free_count FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            
            if not result:
                return False, "user_not_found"
            
            remaining = config.FREE_LIMIT - result[0]
            
            if count <= remaining:
                return True, "free"
            
            return False, "limit_exceeded"
    
    def get_stats(self, user_id: int) -> Dict[str, Any]:
        """Получаем статистику пользователя"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            user = cursor.fetchone()
            
            if not user:
                return {'error': 'user_not_found'}
            
            stats = self._user_to_dict(user)
            
            if stats['is_premium'] and stats['premium_until']:
                try:
                    premium_until = datetime.strptime(stats['premium_until'], '%Y-%m-%d %H:%M:%S')
                    stats['days_left'] = (premium_until - datetime.now()).days
                    stats['premium_until_formatted'] = premium_until.strftime('%d.%m.%Y')
                except:
                    stats['days_left'] = 0
                    stats['premium_until_formatted'] = "Unknown"
            
            return stats
    
    def get_leaderboard(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Получаем топ пользователей"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT user_id, username, total_requests 
                FROM users 
                ORDER BY total_requests DESC 
                LIMIT ?
            ''', (limit,))
            
            return [
                {'user_id': row[0], 'username': row[1], 'total_requests': row[2]}
                for row in cursor.fetchall()
            ]


# Инициализация БД
db = ProxyBotDatabase()

# ============================================================================
# 🌐 PROXY MANAGER - Управление прокси
# ============================================================================

class ProxyScraper:
    """
    Высокопроизводительный скрейпер прокси
    с кэшированием и асинхронной загрузкой
    """
    
    def __init__(self):
        self._cache: List[str] = []
        self._cache_time: Optional[datetime] = None
        self._lock = asyncio.Lock()
        logger.info("🌐 ProxyScraper initialized")
    
    async def get_proxies(self, force_refresh: bool = False) -> List[str]:
        """Получаем список прокси с кэшированием"""
        async with self._lock:
            # Возвращаем кэш если он актуален
            if not force_refresh and self._cache and self._cache_time:
                if (datetime.now() - self._cache_time).seconds < config.CACHE_TTL:
                    logger.debug(f"⚡ Cache hit: {len(self._cache)} proxies")
                    return self._cache.copy()
            
            # Обновляем кэш
            logger.info("🔄 Fetching fresh proxies...")
            proxies = await self._fetch_all_sources()
            
            # Очищаем и валидируем
            proxies = list(set(proxies))
            proxies = [p for p in proxies if self._validate_proxy(p)]
            
            self._cache = proxies
            self._cache_time = datetime.now()
            
            logger.info(f"✅ Fetched {len(proxies)} valid proxies")
            return proxies
    
    async def _fetch_all_sources(self) -> List[str]:
        """Асинхронная загрузка из всех источников"""
        connector = aiohttp.TCPConnector(
            limit=20,
            force_close=True,
            limit_per_host=5
        )
        timeout = aiohttp.ClientTimeout(total=config.REQUEST_TIMEOUT)
        
        async with aiohttp.ClientSession(
            connector=connector,
            timeout=timeout
        ) as session:
            tasks = [
                self._fetch_source(session, url)
                for url in config.PROXY_SOURCES
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            proxies = []
            for result in results:
                if isinstance(result, list):
                    proxies.extend(result)
                elif isinstance(result, Exception):
                    logger.warning(f"⚠️  Source error: {result}")
            
            return proxies
    
    async def _fetch_source(self, session: aiohttp.ClientSession, url: str) -> List[str]:
        """Загрузка из одного источника"""
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    text = await response.text()
                    return self._parse_proxies(text, url)
        except Exception as e:
            logger.error(f"❌ Failed to fetch {url}: {e}")
        return []
    
    def _parse_proxies(self, text: str, source: str) -> List[str]:
        """Парсинг списка прокси"""
        proxies = []
        
        for line in text.strip().split('\n'):
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('//'):
                continue
            
            if ':' in line:
                parts = line.split(':')
                if len(parts) >= 2:
                    ip = parts[0].strip()
                    port = parts[1].strip()
                    if self._validate_ip(ip) and port.isdigit():
                        proxies.append(f"{ip}:{port}")
        
        logger.debug(f"📄 Parsed {len(proxies)} proxies from {source}")
        return proxies
    
    def _validate_ip(self, ip: str) -> bool:
        """Валидация IP адреса"""
        parts = ip.split('.')
        if len(parts) != 4:
            return False
        return all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)
    
    def _validate_proxy(self, proxy: str) -> bool:
        """Валидация формата прокси"""
        if ':' not in proxy:
            return False
        ip, port = proxy.rsplit(':', 1)
        return (self._validate_ip(ip) and 
                port.isdigit() and 
                1 <= int(port) <= 65535)
    
    async def check_proxy(self, proxy: str, test_url: str = "https://httpbin.org/ip") -> bool:
        """Проверяем работоспособность прокси"""
        try:
            connector = aiohttp.TCPConnector(force_close=True)
            timeout = aiohttp.ClientTimeout(total=config.PROXY_CHECK_TIMEOUT)
            
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                async with session.get(
                    test_url,
                    proxy=f"http://{proxy}",
                    timeout=config.PROXY_CHECK_TIMEOUT
                ) as response:
                    return response.status == 200
        except Exception as e:
            logger.debug(f"❌ Proxy {proxy} failed: {e}")
            return False
    
    async def get_working_proxies(self, count: int = 10) -> List[str]:
        """Получаем рабочие прокси"""
        proxies = await self.get_proxies()
        if not proxies:
            return []
        
        # Проверяем больше прокси, чтобы получить достаточно рабочих
        check_count = min(count * 3, len(proxies))
        
        logger.info(f"🔍 Checking {check_count} proxies for working ones...")
        
        tasks = [self.check_proxy(p) for p in proxies[:check_count]]
        results = await asyncio.gather(*tasks)
        
        working = []
        for proxy, is_working in zip(proxies[:check_count], results):
            if is_working:
                working.append(proxy)
                if len(working) >= count:
                    break
        
        logger.info(f"✅ Found {len(working)} working proxies")
        return working


# Инициализация скрейпера
proxy_scraper = ProxyScraper()

# ============================================================================
# 🎯 COMMAND HANDLERS - Обработчики команд
# ============================================================================

router = Router()


@router.message(CommandStart())
async def start_handler(message: Message, command: CommandObject):
    """Обработчик команды /start"""
    user = message.from_user
    user_data = db.get_or_create_user(user)
    
    is_premium = db.is_premium_active(user.id)
    stats = db.get_stats(user.id)
    remaining = config.FREE_LIMIT - stats.get('free_count', 0)
    
    # Формируем статус
    if is_premium:
        days_left = stats.get('days_left', 0)
        status = f"✅ <b>Premium</b> ({days_left} дней)"
    else:
        status = f"❌ <b>Free</b> ({remaining}/5)"
    
    # Формируем приветственное сообщение
    welcome_message = f"""
╔═══════════════════════════════════════════════════════════════╗
║                    🔥 {config.BOT_NAME} 🔥                         ║
║                  Premium HTTP/HTTPS Proxy Provider                 ║
╚═══════════════════════════════════════════════════════════════╝

👋 Привет, <b>{user.first_name or 'Друг'}</b>!

<b>📊 Твой статус:</b> {status}

<b>🎯 Доступные команды:</b>
/start - Начать
/proxy - Получить прокси
/proxy 5 - Получить 5 прокси
/buy - Тарифы
/my_stats - Статистика
/check - Проверить прокси
/leaderboard - Топ пользователей
/help - Справка

<b>⚠️ Внимание:</b> Бесплатные прокси могут быть нестабильными!
{config.FOOTER}
"""
    
    await message.answer(welcome_message, parse_mode=ParseMode.HTML)
    logger.info(f"👤 New user: {user.id} ({user.username or user.first_name})")


@router.message(Command("help"))
async def help_handler(message: Message):
    """Обработчик команды /help"""
    help_message = f"""
╔═══════════════════════════════════════════════════════════════╗
║                     📖 {config.BOT_NAME} - Справка 📖                    ║
╚═══════════════════════════════════════════════════════════════╝

<b>🎯 Что умеет этот бот:</b>
• ⚡ Предоставляет бесплатные и премиум прокси
• 🌐 Автоматическое обновление списка прокси
• 📊 Отслеживание статистики использования
• ✅ Проверка работоспособности прокси

<b>📋 Тарифы:</b>
• <b>Бесплатно:</b> 5 прокси/день
• <b>Premium:</b> Неограниченное количество

<b>💡 Команды:</b>
/start - Начать работу
/proxy - Получить 1 прокси
/proxy N - Получить N прокси
/buy - Купить премиум
/my_stats - Моя статистика
/check - Проверить прокси
/leaderboard - Топ пользователей

<b>⚠️ Важно:</b>
• Бесплатные прокси могут быть медленными
• Премиум прокси обновляются чаще
• Проверяйте прокси перед использованием
{config.FOOTER}
"""
    
    await message.answer(help_message, parse_mode=ParseMode.HTML)


@router.message(Command("my_stats"))
async def my_stats_handler(message: Message):
    """Обработчик команды /my_stats"""
    user_id = message.from_user.id
    stats = db.get_stats(user_id)
    
    if 'error' in stats:
        await message.answer("❌ Ошибка при получении статистики", parse_mode=ParseMode.HTML)
        return
    
    is_premium = db.is_premium_active(user_id)
    
    if is_premium:
        status = f"✅ <b>Premium</b> до {stats.get('premium_until_formatted', '?')}\n({stats.get('days_left', 0)} дней)"
    else:
        remaining = config.FREE_LIMIT - stats.get('free_count', 0)
        status = f"❌ <b>Free</b> ({remaining}/5)"
    
    stats_message = f"""
╔═══════════════════════════════════════════════════════════════╗
║                     📊 Ваша статистика 📊                          ║
╚═══════════════════════════════════════════════════════════════╝

<b>👤 Пользователь:</b> @{stats.get('username', 'Anonymous')}

<b>🎯 Статус:</b> {status}

<b>📈 Общая статистика:</b>
• Всего запросов: <b>{stats.get('total_requests', 0)}</b>
• Прокси сегодня: <b>{stats.get('free_count', 0)}</b>

<b>💡 Совет:</b>
{'Для неограниченного доступа: /buy' if not is_premium else 'Спасибо за поддержку!'}
{config.FOOTER}
"""
    
    await message.answer(stats_message, parse_mode=ParseMode.HTML)


@router.message(Command("leaderboard", "top"))
async def leaderboard_handler(message: Message):
    """Обработчик команды /leaderboard"""
    leaderboard = db.get_leaderboard(10)
    
    if not leaderboard:
        await message.answer("📊 Топ пользователей пока пуст", parse_mode=ParseMode.HTML)
        return
    
    lb_message = f"""
╔═══════════════════════════════════════════════════════════════╗
║                     🏆 Топ пользователей 🏆                          ║
╚═══════════════════════════════════════════════════════════════╝

<b>📊 Топ 10 по количеству запросов:</b>

"""
    
    for i, user in enumerate(leaderboard, 1):
        username = user['username'] or f"User_{user['user_id']}"
        lb_message += f"{i}. <b>{username}</b> - {user['total_requests']} запросов\n"
    
    lb_message += f"\n{config.FOOTER}"
    
    await message.answer(lb_message, parse_mode=ParseMode.HTML)


@router.message(Command("buy"))
async def buy_handler(message: Message):
    """Обработчик команды /buy"""
    buy_message = f"""
╔═══════════════════════════════════════════════════════════════╗
║                     💰 Premium Доступ 💰                           ║
╚═══════════════════════════════════════════════════════════════╝

<b>✨ Преимущества Premium:</b>
✅ Неограниченное количество прокси
✅ Приоритетный доступ к новым прокси
✅ Быстрая поддержка
✅ Отсутствие рекламы
✅ Эксклюзивные прокси

<b>📋 Тарифные планы:</b>

<b>1️⃣ 1 месяц</b> - {config.PRICES['1']}
   • Неограниченные прокси
   • Доступ на 30 дней

<b>2️⃣ 3 месяца</b> - {config.PRICES['3']}
   • Неограниченные прокси
   • Доступ на 90 дней
   • <b>🎁 Экономия 25%</b>

<b>3️⃣ 6 месяцев</b> - {config.PRICES['6']}
   • Неограниченные прокси
   • Доступ на 180 дней
   • <b>🎁 Экономия 40%</b>

<b>💳 Способы оплаты:</b>
/buy_1 - Купить 1 месяц
/buy_3 - Купить 3 месяца
/buy_6 - Купить 6 месяцев

<b>📞 Поддержка:</b> @admin
{config.FOOTER}
"""
    
    await message.answer(buy_message, parse_mode=ParseMode.HTML)


@router.message(Command("buy_1", "buy_3", "buy_6"))
async def buy_plan_handler(message: Message):
    """Обработчик покупки тарифа"""
    command = message.text.split()[0]
    months_map = {
        "/buy_1": (1, config.PRICES['1']),
        "/buy_3": (3, config.PRICES['3']),
        "/buy_6": (6, config.PRICES['6'])
    }
    
    months, price = months_map.get(command, (1, config.PRICES['1']))
    
    # Рассчитываем экономию
    base_price = months * 5
    savings = base_price - int(price.replace('$', ''))
    save_percent = int((savings / base_price) * 100) if base_price > 0 else 0
    
    payment_message = f"""
╔═══════════════════════════════════════════════════════════════╗
║                  💳 Оплата Premium Доступа 💳                        ║
╚═══════════════════════════════════════════════════════════════╝

<b>📦 Тариф:</b> {months} месяц{'а' if months in [2,3,4] else 'ев' if months >=5 else ''}
<b>💰 Цена:</b> {price}
<b>🎁 Экономия:</b> {save_percent}%

<b>💳 Реквизиты для оплаты:</b>

<b>🪙 Криптовалюта:</b>
• Bitcoin (BTC): <code>bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh</code>
• USDT (TRC20): <code>TW9J5xPvj7m5Xj9P6Z2x9D8x7N1p2P4t5L</code>
• Ethereum (ETH): <code>0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb</code>

<b>⚠️ ВАЖНО:</b>
• Укажите ваш <b>Telegram ID: {message.from_user.id}</b>
• Отправьте чек об оплате боту или @admin
• Доступ будет активирован в течение <b>24 часов</b>

<b>📞 Альтернативные способы:</b>
Напишите @admin для других вариантов оплаты
{config.FOOTER}
"""
    
    await message.answer(payment_message, parse_mode=ParseMode.HTML)
    logger.info(f"💳 User {message.from_user.id} requested payment for {months} months")


@router.message(Command("proxy"))
async def proxy_handler(message: Message, command: CommandObject):
    """Обработчик команды /proxy"""
    user_id = message.from_user.id
    
    # Парсим количество
    args = command.args or ""
    count = 1
    if args and args.isdigit():
        count = max(1, min(int(args), config.MAX_PROXY_REQUEST))
    
    # Проверяем лимит
    can_get, reason = db.can_get_proxy(user_id, count)
    
    if not can_get:
        stats = db.get_stats(user_id)
        remaining = config.FREE_LIMIT - stats.get('free_count', 0)
        
        limit_message = f"""
╔═══════════════════════════════════════════════════════════════╗
║                     ❌ Лимит превышен! ❌                           ║
╚═══════════════════════════════════════════════════════════════╝

<b>📊 Текущий статус:</b>
Вы использовали: <b>{stats.get('free_count', 0)}/{config.FREE_LIMIT}</b> прокси
Осталось: <b>{remaining}</b>

<b>💡 Решение:</b>
Купите Premium доступ для неограниченного количества прокси:
/buy - Посмотреть тарифы

{config.FOOTER}
"""
        await message.answer(limit_message, parse_mode=ParseMode.HTML)
        return
    
    # Получаем прокси
    await message.answer("⏳ <b>Ищем доступные прокси...</b>", parse_mode=ParseMode.HTML)
    logger.info(f"🔍 User {user_id} requested {count} proxies")
    
    try:
        proxies = await proxy_scraper.get_proxies()
        
        if not proxies:
            await message.answer("❌ <b>Не удалось получить прокси</b>\nПопробуйте позже", parse_mode=ParseMode.HTML)
            return
        
        # Выбираем случайные прокси
        selected = random.sample(proxies, min(count, len(proxies)))
        
        # Обновляем счетчик для бесплатных
        if reason == "free":
            db.update_request_count(user_id, count)
        
        # Формируем ответ
        proxy_list = "\n".join([f"{i}. <code>{p}</code>" for i, p in enumerate(selected, 1)])
        
        # Получаем статистику
        stats = db.get_stats(user_id)
        is_premium = db.is_premium_active(user_id)
        
        if is_premium:
            status_line = "✅ <b>Premium - без ограничений!</b>"
        else:
            remaining = config.FREE_LIMIT - stats.get('free_count', 0)
            status_line = f"📊 Осталось: <b>{remaining}/5</b>"
        
        proxy_message = f"""
╔═══════════════════════════════════════════════════════════════╗
║                     🔥 Свежие прокси 🔥                              ║
╚═══════════════════════════════════════════════════════════════╝

<b>📋 Вы получили {len(selected)} прокси:</b>

{proxy_list}

<b>📊 Статус:</b> {status_line}
<b>🌐 Всего доступно:</b> {len(proxies)} прокси

<b>💡 Совет:</b> Проверьте прокси командой /check
{config.FOOTER}
"""
        
        await message.answer(proxy_message, parse_mode=ParseMode.HTML)
        logger.info(f"✅ User {user_id} received {len(selected)} proxies")
        
    except Exception as e:
        logger.error(f"❌ Error getting proxies for user {user_id}: {e}")
        await message.answer(f"❌ <b>Ошибка:</b> {e}", parse_mode=ParseMode.HTML)


@router.message(Command("check"))
async def check_handler(message: Message):
    """Обработчик команды /check"""
    await message.answer("⏳ <b>Проверяем прокси на работоспособность...</b>", parse_mode=ParseMode.HTML)
    logger.info(f"🔍 User {message.from_user.id} checking proxies")
    
    try:
        working = await proxy_scraper.get_working_proxies(10)
        
        if working:
            working_list = "\n".join([f"{i}. <code>{p}</code>" for i, p in enumerate(working, 1)])
            
            check_message = f"""
╔═══════════════════════════════════════════════════════════════╗
║                  ✅ Рабочие прокси ✅                               ║
╚═══════════════════════════════════════════════════════════════╝

<b>🎯 Найдено {len(working)} рабочих прокси из 10:</b>

{working_list}

<b>💡 Совет:</b> Используйте эти прокси для надежной работы
{config.FOOTER}
"""
            await message.answer(check_message, parse_mode=ParseMode.HTML)
        else:
            await message.answer("❌ <b>К сожалению, ни один прокси не работает</b>\nПопробуйте позже", parse_mode=ParseMode.HTML)
            
    except Exception as e:
        logger.error(f"❌ Error checking proxies: {e}")
        await message.answer(f"❌ <b>Ошибка:</b> {e}", parse_mode=ParseMode.HTML)


@router.message()
async def echo_handler(message: Message):
    """Обработчик остальных сообщений"""
    help_text = f"""
╔═══════════════════════════════════════════════════════════════╗
║                  🤖 Я бот для прокси! 🤖                           ║
╚═══════════════════════════════════════════════════════════════╝

<b>📋 Используйте команды:</b>
/start - Начать
/proxy - Получить прокси
/buy - Тарифы
/help - Справка
{config.FOOTER}
"""
    await message.answer(help_text, parse_mode=ParseMode.HTML)


# ============================================================================
# 🤖 BOT SETUP - Настройка и запуск бота
# ============================================================================

@asynccontextmanager
async def lifespan(bot: Bot):
    """Lifespan manager для бота"""
    # Настраиваем команды бота
    commands = [
        BotCommand(command="start", description="🚀 Начать"),
        BotCommand(command="help", description="📖 Справка"),
        BotCommand(command="proxy", description="🔥 Получить прокси"),
        BotCommand(command="check", description="✅ Проверить прокси"),
        BotCommand(command="buy", description="💰 Купить премиум"),
        BotCommand(command="my_stats", description="📊 Статистика"),
        BotCommand(command="leaderboard", description="🏆 Топ пользователей"),
    ]
    
    await bot.set_my_commands(commands)
    logger.info("✅ Bot commands configured")
    
    yield
    
    logger.info("🛑 Bot shutdown")


async def main():
    """Главная функция запуска"""
    if config.BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("❌ BOT_TOKEN not configured! Please set your bot token.")
        print("\n" + "="*60)
        print("ERROR: BOT_TOKEN not configured!")
        print("Please edit bot.py and set your Telegram bot token")
        print("="*60 + "\n")
        return
    
    # Создаем бота
    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    
    # Запускаем
    logger.info("="*60)
    logger.info(f"🚀 Starting {config.BOT_NAME}")
    logger.info(f"🤖 Bot token: {'*' * len(config.BOT_TOKEN) if config.BOT_TOKEN != 'YOUR_BOT_TOKEN_HERE' else 'NOT SET'}")
    logger.info(f"📊 Free limit: {config.FREE_LIMIT} proxies/day")
    logger.info(f"🌐 Proxy sources: {len(config.PROXY_SOURCES)}")
    logger.info("="*60)
    
    async with lifespan(bot):
        await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        print(f"\n❌ Error: {e}\n")
