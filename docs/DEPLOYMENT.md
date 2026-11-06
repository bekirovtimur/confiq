# Руководство по развёртыванию Confiq

## 🚀 Быстрый старт

```bash
# 1. Клонирование репозитория
git clone https://github.com/bekirovtimur/confiq.git
cd confiq

# 2. Настройка переменных окружения
cp .env.example .env
# Отредактируйте .env, укажите CADDY_DOMAIN и CADDY_EMAIL

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
- **Docker Compose V2** (команда `docker compose`)

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
CADDY_DOMAIN=your-domain.com
CADDY_EMAIL=admin@your-domain.com
ADMIN_PASSWORD=your_secure_password_here
SECRET_KEY=replace_with_random_hex_value
```

Сгенерируйте секрет отдельно и вставьте полученное значение в `.env` (подстановка `$(...)` внутри `.env` не выполняется):

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
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
| `CADDY_DOMAIN` | Домен для SSL | ✅ |
| `CADDY_EMAIL` | Email для Let's Encrypt | ✅ |
| `ADMIN_PASSWORD` | Пароль администратора | ✅ |
| `SECRET_KEY` | Секретный ключ для сессий | ✅ |
| `ADMIN_LOGIN` | Логин администратора | ❌ (по умолчанию: admin) |

Количество worker процессов (`4`) и таймаут (`120` секунд) сейчас заданы аргументами Gunicorn в `Dockerfile`. Переменные `WORKERS` и `TIMEOUT` не подключены к команде запуска.

---

## 🔄 Обновление приложения

Перед обновлением сохраните резервную копию SQLite-базы. Для работающей базы используйте согласованный способ резервного копирования SQLite, например CLI `sqlite3` на хосте:

```bash
sqlite3 data/warp_manager.db ".backup 'data/warp_manager.db.backup'"
```

Пример использует фиксированное имя: выберите новое имя для каждого бэкапа, чтобы не перезаписать предыдущий. Если `sqlite3` не установлен, сначала остановите сервис приложения и только затем копируйте файл БД.

После получения новой версии исходников пересоберите и пересоздайте приложение:

```bash
docker compose up -d --build app
docker compose ps
docker compose logs --tail=100 app
```

Обычный `docker compose restart` не обновляет код, скопированный в образ на этапе сборки. Для локального варианта без Caddy используйте ту же команду с `-f docker-compose-local.yml`:

```bash
docker compose -f docker-compose-local.yml up -d --build app
```

### Проверка административных конфигураций

Для общего списка и смены типа конфигурации миграция актуальной схемы не нужна. Исторические миграции для более старых установок описаны в [README](../README.md#-миграция-с-предыдущих-версий-до-появления-групп).

После обновления войдите администратором, откройте **Все конфигурации** (`/admin/configs`), проверьте просмотр и скачивание конфига другого владельца. Для смены типа у его endpoint должно быть не менее одного другого активного поддерживаемого типа. После изменения скачайте файл заново; уже импортированные файлы не обновляются автоматически.

Подробный сценарий проверки и ограничения: [управление конфигурациями](ADMIN_CONFIGS.md#проверка-после-обновления).

---

## 🔐 SSL сертификаты

SSL-сертификаты получаются и обновляются **автоматически** через Let's Encrypt с помощью Caddy.

Проверка логов:
```bash
docker compose logs caddy
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
3. Переменные CADDY_DOMAIN и CADDY_EMAIL указаны в .env

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
