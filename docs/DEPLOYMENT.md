# Руководство по развёртыванию Confiq

## 🚀 Быстрый старт

```bash
# 1. Клонирование репозитория
git clone https://github.com/bekirovtimur/confiq
cd confiq

# 2. Настройка переменных окружения
cp .env.example .env
# Отредактируйте .env, укажите CERTBOT_DOMAIN и CERTBOT_EMAIL

# 3. Запуск приложения
docker compose up -d

# Готово! SSL сертификат получится автоматически через несколько минут
```

---

## 📋 Требования

### Системные требования

| Компонент | Минимальные требования |
|-----------|------------------------|
| ОС | Linux (Ubuntu 20.04+, Debian 11+) |
| RAM | 512 MB |
| Диск | 2 GB |
| CPU | 1 ядро |

### Необходимое ПО

- **Docker** (20.10+)
- **Docker Compose** (1.29+)

Установка Docker:
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
newgrp docker
```

### Требования к сети

- **Доменное имя**, указывающее на IP сервера
- **Открытые порты**:
  - `80/tcp` — HTTP (для Let's Encrypt)
  - `443/tcp` — HTTPS

---

## 📖 Пошаговая инструкция

### 1. Настройка .env файла

```bash
cp .env.example .env
nano .env
```

**Обязательные изменения:**

```env
CERTBOT_DOMAIN=your-domain.com
CERTBOT_EMAIL=admin@your-domain.com
ADMIN_PASSWORD=your_secure_password_here
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
```

### 2. Запуск

```bash
docker compose up -d
```

Проверка статуса:
```bash
docker compose ps
docker compose logs -f
```

### 3. Проверка работы

```bash
curl -I https://your-domain.com
```

Вход в приложение:
- **URL:** `https://your-domain.com`
- **Логин:** `admin` (или указанный в `ADMIN_LOGIN`)
- **Пароль:** значение из `ADMIN_PASSWORD`

---

## 🔧 Переменные окружения

| Переменная | Описание | Обязательная |
|------------|----------|--------------|
| `CERTBOT_DOMAIN` | Домен для SSL | ✅ |
| `CERTBOT_EMAIL` | Email для Let's Encrypt | ✅ |
| `ADMIN_PASSWORD` | Пароль администратора | ✅ |
| `SECRET_KEY` | Секретный ключ для сессий | ✅ |
| `ADMIN_LOGIN` | Логин администратора | ❌ (по умолчанию: admin) |
| `WORKERS` | Количество worker процессов Gunicorn | ❌ (по умолчанию: 4) |
| `TIMEOUT` | Таймаут запросов (сек) | ❌ (по умолчанию: 120) |

---

## 🔐 SSL сертификаты

SSL-сертификаты получаются и обновляются **автоматически** через Let's Encrypt.

Проверка логов:
```bash
docker compose logs nginx
```

---

## 🛠️ Устранение неполадок

### Контейнеры не запускаются

```bash
docker compose logs
docker compose down && docker compose up -d
```

### SSL сертификат не получается

Проверьте:
1. Домен указывает на IP сервера: `nslookup your-domain.com`
2. Порт 80 открыт: `sudo ufw allow 80/tcp`
3. Переменные CERTBOT_DOMAIN и CERTBOT_EMAIL указаны в .env

### Приложение недоступно

```bash
docker compose ps
docker compose logs app
```

---

## 📞 Поддержка

При возникновении проблем проверьте логи:
```bash
docker compose logs
```
