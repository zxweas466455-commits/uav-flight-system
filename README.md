
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