# 🔥 Free Proxy Bot

Telegram бот для получения бесплатных HTTP/HTTPS прокси из различных источников.

## ⚡ Возможности

- 📥 Получение списка бесплатных прокси из нескольких API
- 🎲 Выдача случайных прокси по запросу
- 🔍 Проверка работоспособности прокси
- 📊 Отображение количества доступных прокси
- 💬 Простой и удобный интерфейс

## 📋 Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Начать работу с ботом |
| `/help` | Показать справку |
| `/proxy` | Получить 1 случайный прокси |
| `/proxy N` | Получить N прокси (максимум 20) |
| `/check` | Проверить работоспособность первых 10 прокси |

## 🚀 Установка и запуск

### 1. Клонируйте репозиторий

```bash
git clone https://github.com/maleshovivan23-creator/bot-.git
cd bot-
```

### 2. Установите зависимости

```bash
pip install -r requirements.txt
```

### 3. Создайте бота в Telegram

1. Откройте [@BotFather](https://t.me/BotFather) в Telegram
2. Отправьте команду `/newbot`
3. Следуйте инструкциям и получите токен бота

### 4. Настройте бота

Откройте файл `bot.py` и замените строку:
```python
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
```
на ваш токен:
```python
BOT_TOKEN = "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
```

### 5. Запустите бота

```bash
python bot.py
```

## 📦 Источники прокси

Бот получает прокси из следующих источников:

- [ProxyScrape](https://proxyscrape.com/free-proxy-list)
- [SSLProxies](https://www.sslproxies.org/)
- [Free Proxy List](https://free-proxy-list.net/)
- [jundymek/free-proxy](https://github.com/jundymek/free-proxy)
- [TheSpeedX/PROXY-List](https://github.com/TheSpeedX/PROXY-List)
- [jetkai/proxy-list](https://github.com/jetkai/proxy-list)

## ⚠️ Важно

- ✅ Бесплатные прокси могут быть нестабильными
- ✅ Проверяйте прокси перед использованием
- ✅ Используйте на свой страх и риск
- ❌ Не используйте для противозаконных целей
- ❌ Не нарушайте права других пользователей

## 🤝 Вклад в проект

Приветствуются pull request'ы! Если вы хотите добавить:

- Новые источники прокси
- Улучшить парсинг
- Добавить новые функции

Создайте fork, внесите изменения и отправьте pull request.

## 📜 Лицензия

MIT License
