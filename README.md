# Keitaro Wrapper (тестовое «Это Легко» / Ad Robot)

Обёртка над [Keitaro Admin API](https://docs.keitaro.io/en/development/admin-api.html):

1. **Создаватор кампаний** — гео-поток на Google + поток на оффер.
2. **Редактор** — локальный черновик, веса, push/cancel, remove/bring back, pin (API).

Кампании в тестовом Keitaro: префикс **`test_krylov_`** (настраивается в `.env`).

## Стек

- Python 3.11+, FastAPI, SQLAlchemy 2, PostgreSQL, Alembic, httpx
- Простой UI: `app/static/index.html`

## Быстрый старт

### Вариант A — без Docker (проще на Windows)

Скопируй путь **с большой буквы П**: `Проект фулстек`, не `проект фулстек`.

```powershell
powershell -ExecutionPolicy Bypass -File "C:\Users\user\Desktop\Проект фулстек\keitaro-wrapper\scripts\start.ps1"
```

Скрипт сам создаст venv, поставит пакеты, создаст SQLite-БД и запустит сервер.

### Вариант B — вручную

```powershell
cd "C:\Users\user\Desktop\Проект фулстек\keitaro-wrapper"
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\init_db.py
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

`.env` уже с SQLite (`keitaro_wrapper.db`). Ключ Keitaro — в `.env`.

### Вариант C — PostgreSQL + Docker (если установлен Docker)

```powershell
docker compose up -d
alembic upgrade head
```

В `.env` тогда: `DATABASE_URL=postgresql+psycopg://keitaro:keitaro@localhost:5432/keitaro_wrapper`

Открой http://127.0.0.1:8000/

## API (кратко)

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/api/campaigns` | Создать кампанию в Keitaro + запись в БД |
| POST | `/api/campaigns/{id}/fetch` | Подтянуть потоки из Keitaro |
| POST | `/api/streams/{id}/offers` | Добавить оффер (черновик) |
| DELETE | `/api/streams/{id}/offers/{link_id}` | Remove |
| POST | `.../bring-back` | Вернуть removed |
| POST | `.../pin` | Закрепить вес |
| POST | `/api/streams/{id}/push` | Опубликовать в Keitaro |
| POST | `/api/streams/{id}/cancel` | Откатить неопубликованное |

## Сдача по ТЗ (чеклист)

### Часть 1 — создаватор

1. `start.cmd` → http://127.0.0.1:8000/
2. Создать кампанию: гео **PE**, оффер **4514**, уникальное имя.
3. В Keitaro: кампания `test_krylov_*`, **2 потока** (Geo → Google + Offer).
4. Скрин: список кампаний (колонка «Потоки: 2») и карточки потоков.

### Часть 2 — редактор (UI)

В блоке «Редактор», на **Offer stream** (жёлтый фон = черновик):

1. **Remove** оффера → **Bring back** (проверка локального черновика).
2. **Add offer** — второй ID оффера (другой, не дубликат).
3. **Pin** — закрепить вес одному офферу (остальным пересчитаются).
4. **Push to KT** — в Keitaro обновятся доли офферов.
5. **Cancel** — сбросить неопубликованные добавления (до Push).

Автопроверка сценария (опционально):  
`.\.venv\Scripts\python.exe scripts\tz_editor_demo.py --local-id 2 --extra-offer 4440`

### Репозиторий

Публичный GitHub, `.env` в `.gitignore`, ключ только локально.

## Важно по Keitaro

Тестовый трекер может отличаться по полям JSON потоков. Если `create_campaign` или `push` падают с 4xx:

1. Создай кампанию вручную в админке.
2. Сравни тело потока в Keitaro Swagger / доке.
3. Подправь payload в `app/services/campaign_creator.py` и `editor.py`.

У части инстансов обновление потока — `POST /streams/{id}`, не `PUT` (см. `keitaro_client.py`).

## GitHub

Перед сдачей: публичный репозиторий, без `.env` и без API-ключа.