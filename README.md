
# Веб-система планирования, верификации и мониторинга полётных задач парка БВС

![Python](https://img.shields.io/badge/Python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-18-336791)
![License](https://img.shields.io/badge/license-MIT-green)

Автоматизированная система для операторов коммерческой авиации БВС.
Позволяет планировать маршруты на карте, автоматически проверять их
на пересечение с зонами ограничения воздушного пространства РФ,
отслеживать состояние парка в реальном времени и вести журнал полётов
с фильтрацией и экспортом.

---

## Содержание
- [Скриншоты](#скриншоты)
- [Возможности](#возможности)
- [Архитектура](#архитектура)
- [Требования](#требования)
- [Установка](#установка)
- [Настройка базы данных](#настройка-базы-данных)
- [Конфигурация](#конфигурация)
- [Запуск](#запуск)
- [API Reference](#api-reference)
- [Алгоритм верификации маршрутов](#алгоритм-верификации-маршрутов)
- [Структура проекта](#структура-проекта)
- [Тестирование](#тестирование)
- [Документация для разработчиков](#документация-для-разработчиков)

---

## Скриншоты

### Планирование маршрута
![Планирование](docs/screenshots/planning.png)

### Мониторинг
![Мониторинг](docs/screenshots/monitoring.png)

### Журнал полётов
![Журнал](docs/screenshots/journal.png)

## Возможности


### 📍 Планирование маршрута
- Интерактивная карта (OpenStreetMap / Leaflet)
- Добавление путевых точек кликом, перетаскивание маркеров
- Задание высоты полёта
- Отображение зон ограничения полётов в реальном времени

### ✅ Автоматическая верификация
- Проверка пересечения маршрута с зонами ограничения
- Учёт высотных границ каждой зоны (нижняя/верхняя)
- Классификация конфликтов: **критические** / **информационные**
- Оценка длины маршрута
- Автоматическое отклонение полётного задания при критических конфликтах

### 📡 Мониторинг парка БВС
- Отображение текущих координат всех БВС в полёте
- Обновление через WebSocket в реальном времени
- Панель со сводной статистикой (всего / в полёте / на базе / обслуживание)
- Лента событий с автообновлением

### 📖 Журнал полётов
- Хранение всех полётных заданий с полной историей событий
- Фильтрация: по статусу, БВС, датам, поиск по примечаниям
- Детальный просмотр каждого полёта (маршрут, верификация, телеметрия)
- Экспорт в **Excel (.xlsx)** и **CSV**
- Ручной импорт зон ограничения из GeoJSON-файлов

---

## Архитектура

```mermaid
flowchart TB
    subgraph Client["🖥 Браузер (клиент)"]
        direction LR
        Map["🗺 Leaflet карта"]
        WS["🔌 WebSocket"]
        API["📡 REST API calls"]
    end

    subgraph Server["⚙️ FastAPI (Uvicorn)"]
        direction TB
        subgraph Routes["HTTP-роутеры"]
            direction LR
            D["/drones"]
            F["/flights"]
            Z["/zones"]
            M["/monitoring"]
        end
        subgraph Extra["Дополнительно"]
            direction LR
            H["HTML / Jinja2"]
            S["static"]
            SW["Swagger /docs"]
        end
        subgraph Services["Сервисы"]
            direction LR
            V["RouteVerifier<br/>(Shapely)"]
            E["JournalExporter"]
            Sim["FlightSimulator"]
        end
    end

    DB[("🗄 PostgreSQL 18 + PostGIS<br/>drones · flights ·<br/>restricted_zones · flight_logs")]

    Map --> API
    WS -.-> WS
    API --> Routes
    WS --> Routes
    Routes --> Services
    Services -->|SQLAlchemy async<br/>asyncpg| DB

    classDef clientBox fill:#e3f2fd,stroke:#1976d2,color:#000
    classDef serverBox fill:#fff3e0,stroke:#f57c00,color:#000
    classDef dbBox fill:#e8f5e9,stroke:#388e3c,color:#000
    classDef svcBox fill:#f3e5f5,stroke:#7b1fa2,color:#000

    class Map,WS,API clientBox
    class D,F,Z,M,H,S,SW serverBox
    class V,E,Sim svcBox
    class DB dbBox
```

**Поток данных:**
1. Оператор задаёт маршрут на карте Leaflet и отправляет его через REST API.
2. FastAPI принимает запрос, вызывает `RouteVerifier` (Shapely) для проверки пересечений с зонами.
3. Результат верификации и само полётное задание сохраняются в PostgreSQL через SQLAlchemy (async).
4. `FlightSimulator` в фоне двигает БВС по маршрутам и рассылает обновления через WebSocket всем подключённым клиентам.
5. Журнал полётов доступен с фильтрами и выгрузкой в Excel/CSV через `JournalExporter`.

### Стек технологий

| Слой       | Технология                                            |
|------------|-------------------------------------------------------|
| Backend    | Python 3.12.9, FastAPI, Uvicorn                       |
| ORM        | SQLAlchemy 2.0 (async), Alembic                       |
| БД         | PostgreSQL 18 + PostGIS                               |
| Геометрия  | Shapely 2.0, GeoAlchemy2, pyproj                      |
| Frontend   | Jinja2, Leaflet 1.9, Bootstrap 5, Vanilla JS          |
| Realtime   | WebSocket (встроен в FastAPI)                         |
| Экспорт    | pandas, openpyxl                                      |
| Логи       | Loguru                                                |

---

## Требования

- **Windows / Linux / macOS**
- **Python 3.12.9** — [python.org](https://www.python.org/downloads/)
- **PostgreSQL 18** с расширением **PostGIS** — [postgresql.org](https://www.postgresql.org/download/)
- **Git** — [git-scm.com](https://git-scm.com/)
- **VS Code** (рекомендуется) с расширениями:
  - Python
  - Pylance
  - SQLTools + PostgreSQL driver (для работы с БД из редактора)

---

## Установка

### 1. Клонирование проекта

```powershell
git clone <URL_РЕПОЗИТОРИЯ> uav-flight-system
cd uav-flight-system
```

### 2. Виртуальное окружение

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

> Если PowerShell блокирует запуск скриптов:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

### 3. Зависимости

```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

---

## Настройка базы данных

### 1. Создание БД

Откройте **pgAdmin** или **SQL Shell (psql)** и выполните:

```sql
CREATE DATABASE uav_flight_db;
\c uav_flight_db
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;
```

Проверка:

```sql
SELECT PostGIS_Version();
```

### 2. Миграции Alembic

```powershell
# Первый запуск (создаёт папку alembic и alembic.ini)
alembic init alembic

# Укажите в alembic.ini:
#   sqlalchemy.url = postgresql://postgres:ПАРОЛЬ@localhost:5432/uav_flight_db

# Сгенерировать первую миграцию
alembic revision --autogenerate -m "Initial tables"

# Применить
alembic upgrade head
```

### 3. Тестовые данные

Скрипт создаёт 10 БВС, 4 зоны ограничения и 5 демонстрационных полётов:

```powershell
python -m scripts.seed_data
```

Ожидаемый вывод:

```
✅ Добавлено БВС: 10
✅ Добавлено зон: 4
=======================================================
📊 Итог наполнения:
   БВС:           10
   Зон:           4
   Полётов:       5
   Событий в лог: 13
=======================================================
```

Для пересоздания с нуля:

```sql
TRUNCATE flight_logs, flights, restricted_zones, drones RESTART IDENTITY CASCADE;
```

---

## Конфигурация

Создайте файл `.env` в корне проекта (скопируйте из `.env.example`):

```env
# ==== Database ====
DATABASE_URL=postgresql+asyncpg://postgres:ВАШ_ПАРОЛЬ@localhost:5432/uav_flight_db
DATABASE_URL_SYNC=postgresql://postgres:ВАШ_ПАРОЛЬ@localhost:5432/uav_flight_db

# ==== App ====
APP_NAME=UAV Flight Management System
DEBUG=False
SQL_ECHO=False
SECRET_KEY=change-me-in-production

# ==== External API (опционально) ====
AIRSPACE_API_URL=
AIRSPACE_API_KEY=

# ==== Monitoring ====
TELEMETRY_INTERVAL_SECONDS=5
```

> ⚠️ Файл `.env` **не коммитится** в Git (см. `.gitignore`).
> Пароли не храните в репозитории.

---

## Запуск

### Локально

```powershell
# Активировать venv
.\.venv\Scripts\Activate.ps1

# Запустить сервер
python run.py
```

### Из VS Code

1. Откройте проект
2. Установите точку останова (F9) в нужном месте
3. Нажмите **F5** — выберите конфигурацию **Python: FastAPI**

### Доступ

| URL                              | Назначение                             |
|----------------------------------|----------------------------------------|
| http://127.0.0.1:8000/           | Планирование маршрута                  |
| http://127.0.0.1:8000/monitoring | Мониторинг парка в реальном времени    |
| http://127.0.0.1:8000/journal    | Журнал полётов с фильтрами             |
| http://127.0.0.1:8000/docs       | Swagger UI (OpenAPI 3.0)               |
| http://127.0.0.1:8000/redoc      | ReDoc                                  |
| ws://127.0.0.1:8000/ws/monitoring | WebSocket-канал телеметрии            |

При запуске в консоли должно появиться:

```
[Simulator] запущен, интервал 2.0s
Приложение запущено
INFO:     Application startup complete.
```

Симулятор начинает двигать БВС, у которых есть активный полёт
(`in_progress`). В логах раз в 2 секунды — координаты, а при достижении
точки маршрута:

```
[Simulator] БВС-01 «Орлан»: точка №2
[Simulator] БВС-01 «Орлан»: полёт завершён
```

---

## API Reference

Базовый префикс: `/api`. Полная спецификация — в `/docs`.

### 🛩 Дроны (`/api/drones`)

| Метод  | Путь                          | Описание                          |
|--------|-------------------------------|-----------------------------------|
| GET    | `/api/drones`                 | Список БВС (фильтр `?status=`)    |
| POST   | `/api/drones`                 | Создать БВС                       |
| GET    | `/api/drones/{id}`            | Получить БВС                      |
| PATCH  | `/api/drones/{id}`            | Обновить данные                   |
| POST   | `/api/drones/{id}/telemetry`  | Приём телеметрии                  |
| DELETE | `/api/drones/{id}`            | Удалить БВС (только без полётов)  |

**Создание БВС:**

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/drones `
  -H "Content-Type: application/json" `
  -d "{\"name\":\"БВС-1 Орлан\",\"serial_number\":\"ORL-001\",\"model\":\"Орлан-10\"}"
```

### ✈️ Полёты (`/api/flights`)

| Метод  | Путь                              | Описание                          |
|--------|-----------------------------------|-----------------------------------|
| POST   | `/api/flights/verify`             | Верификация маршрута (без сохранения) |
| POST   | `/api/flights`                    | Создать полётное задание          |
| GET    | `/api/flights`                    | Список с фильтрами                |
| GET    | `/api/flights/{id}`               | Детали полёта                     |
| PATCH  | `/api/flights/{id}/status`        | Изменить статус                   |
| GET    | `/api/flights/{id}/logs`          | Журнал событий полёта             |
| GET    | `/api/flights/export/excel`       | Экспорт в Excel                   |
| GET    | `/api/flights/export/csv`         | Экспорт в CSV                     |

**Фильтры GET `/api/flights`:**

- `status` — `planned / approved / in_progress / completed / rejected / cancelled`
- `drone_id` — UUID
- `date_from`, `date_to` — ISO 8601 (`2026-01-15T00:00:00`)
- `search` — поиск по примечаниям

**Пример верификации маршрута:**

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/flights/verify `
  -H "Content-Type: application/json" `
  -d "{\"waypoints\":[{\"lat\":55.755,\"lon\":37.600,\"alt\":150},{\"lat\":55.760,\"lon\":37.640,\"alt\":150}],\"altitude_m\":150}"
```

Ответ:

```json
{
  "is_valid": false,
  "critical_count": 1,
  "total_zones_checked": 4,
  "route_length_m": 3480.2,
  "flight_altitude_m": 150,
  "conflicts": [
    {
      "zone_id": "...",
      "zone_name": "Зона №2 — центр Москвы (Кремль)",
      "zone_type": "permanent",
      "severity": "critical",
      "message": "Маршрут пересекает зону «Кремль» на высоте 150 м (разрешённый диапазон: 0–2000 м)"
    }
  ]
}
```

### 🗺 Зоны ограничения (`/api/zones`)

| Метод  | Путь                                | Описание                     |
|--------|-------------------------------------|------------------------------|
| GET    | `/api/zones`                        | Список зон                   |
| GET    | `/api/zones/geojson`                | FeatureCollection для Leaflet |
| POST   | `/api/zones`                        | Создать зону вручную         |
| POST   | `/api/zones/import/geojson`         | Импорт из GeoJSON-файла      |
| GET    | `/api/zones/{id}`                   | Получить зону                |
| DELETE | `/api/zones/{id}`                   | Удалить зону                 |

**Импорт из GeoJSON:**

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/zones/import/geojson `
  -F "file=@data/zones/sample_zones.geojson"
```

Ответ:

```json
{"imported": 2}
```

### 📡 Мониторинг (`/api/monitoring`)

| Метод  | Путь                          | Описание                          |
|--------|-------------------------------|-----------------------------------|
| GET    | `/api/monitoring/status`      | Сводная статистика парка          |
| GET    | `/api/monitoring/live`        | Текущие координаты БВС в полёте   |
| GET    | `/api/monitoring/events`      | Последние N событий               |
| GET    | `/api/monitoring/health`      | Проверка живости сервиса          |

### 🔌 WebSocket

**Подключение:** `ws://127.0.0.1:8000/ws/monitoring`

При подключении сервер сразу отправляет снимок текущего состояния,
далее — рассылает обновления при каждом тике симулятора:

```json
{
  "type": "telemetry",
  "data": [
    {
      "drone_id": "9fb1f5e2-...",
      "drone_name": "БВС-01 «Орлан»",
      "lat": 55.7558,
      "lon": 37.6173,
      "altitude": 340.0,
      "status": "in_flight"
    }
  ]
}
```

Клиент периодически отправляет `ping` (простое текстовое сообщение),
чтобы сервер держал соединение открытым.

---

## Алгоритм верификации маршрутов

Модуль расположен в `app/services/verification.py`. Это **ключевой
компонент** системы (40% оценочного веса).

### Схема работы

```
1. Вход: список waypoints + высота полёта + список зон ограничения
   │
   ▼
2. Построение LineString из waypoints (Shapely)
   │
   ▼
3. Для каждой зоны:
   ├── Построение Polygon из geometry
   ├── Проверка line.intersects(polygon)
   │   ├── НЕТ  → пропускаем зону
   │   └── ДА   → проверяем вертикаль:
   │            ├── lower ≤ altitude ≤ upper  → критический конфликт
   │            └── иначе                       → информационный конфликт
   │
   ▼
4. Формирование результата:
   {is_valid, conflicts[], critical_count, route_length_m, ...}
```

### Классификация конфликтов

| Тип            | Условие                                              | Последствие                        |
|----------------|------------------------------------------------------|------------------------------------|
| **critical**   | Пересечение по горизонтали **И** высота в границах   | Полётное задание → `rejected`      |
| **info**       | Пересечение по горизонтали, но высота вне границ    | Задание сохраняется, запись в лог  |
| —              | Нет пересечения по горизонтали                       | Конфликта нет                      |

### Краевые случаи (покрыты тестами)

- Маршрут касается границы зоны → считается **критическим**
  (Shapely `intersects` включает касание)
- Маршрут проходит над зоной (выше `upper_limit_m`) → **info**
- Маршрут проходит под зоной (ниже `lower_limit_m`) → **info**
- Менее 2 путевых точек → ошибка валидации
- Пустой список зон → маршрут всегда валиден

### Расширение под реальные API

В `.env` предусмотрены переменные `AIRSPACE_API_URL` и `AIRSPACE_API_KEY`.
Для интеграции с внешним источником зон (например, НОТАМ-сервисом) —
добавьте в `_load_zones()` в `flights.py` запрос через `httpx.AsyncClient`
и синхронизацию зон в таблицу `restricted_zones` (например, по cron).

---

## Структура проекта

```
uav-flight-system/
├── app/
│   ├── main.py                    # FastAPI: роутеры, WebSocket, страницы
│   ├── api/routes/
│   │   ├── drones.py              # /api/drones
│   │   ├── flights.py             # /api/flights
│   │   ├── zones.py               # /api/zones
│   │   └── monitoring.py          # /api/monitoring
│   ├── core/
│   │   ├── config.py              # Pydantic Settings из .env
│   │   └── database.py            # Async SQLAlchemy
│   ├── models/models.py           # ORM: Drone, Flight, Zone, FlightLog
│   ├── schemas/schemas.py         # Pydantic-схемы
│   ├── services/
│   │   ├── verification.py        # 🎯 Верификация маршрутов (Shapely)
│   │   ├── simulator.py           # 🛰 Симулятор движения БВС
│   │   └── export.py              # Экспорт в Excel/CSV
│   ├── utils/geo.py               # Haversine, интерполяция, bbox
│   ├── static/
│   │   ├── css/style.css
│   │   └── js/
│   │       ├── map.js             # Карта планирования
│   │       ├── monitoring.js      # WebSocket-мониторинг
│   │       └── journal.js         # Журнал + фильтры
│   └── templates/
│       ├── base.html
│       ├── index.html
│       ├── monitoring.html
│       └── journal.html
├── alembic/                       # Миграции БД
│   └── versions/
├── scripts/
│   └── seed_data.py               # Тестовые данные (10 БВС + 4 зоны)
├── data/zones/                    # GeoJSON-файлы зон
│   ├── sample_zones.geojson
│   └── README.md
├── tests/
│   └── test_verification.py       # Юнит-тесты верификатора
├── logs/                          # Логи приложения
├── .env                           # (не в Git)
├── .env.example
├── .gitignore
├── alembic.ini
├── requirements.txt
├── run.py                         # Точка входа
└── README.md
```

---

## Тестирование

### Все тесты

```powershell
pytest tests/ -v
```

### Только верификация

```powershell
pytest tests/test_verification.py -v
```

### С покрытием

```powershell
pip install pytest-cov
pytest tests/ --cov=app --cov-report=html
```

Отчёт откроется в `htmlcov/index.html`.

### Что проверяется

Файл `tests/test_verification.py` содержит 12 тестов:

- Маршрут полностью вне зоны
- Маршрут насквозь зоны на запрещённой высоте
- Полёт над зоной (выше верхней границы)
- Полёт под зоной (ниже нижней границы)
- Касание границы зоны
- Пустой / одноточечный маршрут
- Отсутствие зон
- Несколько зон одновременно
- Расчёт длины маршрута
- Генерация рекомендаций по обходу

---

## Документация для разработчиков

### Добавление нового эндпоинта

1. Создайте функцию в соответствующем модуле `app/api/routes/*.py`
2. Определите Pydantic-схему в `app/schemas/schemas.py`
3. Подключите роутер в `app/main.py` (если новый модуль)

### Работа с геометрией

- Все координаты хранятся в **WGS84 (SRID 4326)**
- Порядок в WKT: `(lon lat)` — как в GeoJSON
- Для расчёта расстояний в метрах используйте `app.utils.geo.haversine_m`
- Для проверки пересечений — Shapely (`LineString.intersects(Polygon)`)

### Симулятор движения

Файл `app/services/simulator.py`. Работает в фоне (asyncio-задача,
запускается в `lifespan` FastAPI).

Параметры:

- `interval` — период тика, секунды (по умолчанию 2)
- `STEP_DEG` — шаг движения в градусах (0.0003 ≈ 33 м по широте)
- `ALT_SMOOTHING` — коэффициент плавности изменения высоты

Симулятор двигает дронов по маршруту, при достижении точки пишет
событие в `flight_logs`, при завершении — меняет статус полёта на
`completed`, а дрона — на `idle`.

### Миграции БД

```powershell
# Изменили модель в models.py →
alembic revision --autogenerate -m "add new field"
alembic upgrade head

# Откатить последнюю
alembic downgrade -1

# История
alembic history
```

### Логи

Логи пишутся через **Loguru**. По умолчанию выводятся в консоль.
Для записи в файл добавьте в `main.py`:

```python
from loguru import logger
logger.add("logs/app_{time}.log", rotation="10 MB", retention="7 days")
```

### Стиль кода

```powershell
# Установка линтеров
pip install ruff black isort

# Форматирование
black app/
isort app/

# Проверка
ruff check app/
```

---

## Лицензия

Учебный проект. Свободное использование в образовательных целях.

## Контакты

- **Разработчик:** zxweas466455-commits
- **Индустриальный партнёр:** операторы коммерческой авиации БВС
- **Год:** 2026
