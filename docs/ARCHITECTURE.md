# Архитектура

## Обзор

```
Клиент (CLI / HTTP / Python)
        │
        ▼
┌───────────────────┐
│  FastAPI (main)   │  ← маршруты, валидация, lifespan
└─────────┬─────────┘
          │
    ┌─────┴─────┐
    ▼           ▼
┌─────────┐ ┌──────────────┐
│ classify│ │ catalog_svc  │  ← аудит, CRUD
│ service │ └──────┬───────┘
└────┬────┘        │
     ▼             ▼
┌─────────────┐ ┌──────────┐
│ Classifier  │ │ SQLite   │
│ Engine      │ │ (ORM)    │
└──────┬──────┘ └────┬─────┘
       │             │
       ▼             ▼
┌─────────────┐ ┌──────────────┐
│ Catalog     │ │ JSON seeds   │
│ Registry    │ │ data/catalogs│
│ (in-memory) │ └──────────────┘
└─────────────┘
```

## Компоненты

### `app/core/classifier.py` — HybridScorer

Гибридный скорер комбинирует четыре сигнала:

| Сигнал | Вес по умолчанию | Описание |
|--------|------------------|----------|
| Keyword (Jaccard) | 0.35 | Пересечение токенов контекста и справочника |
| Fuzzy (rapidfuzz) | 0.40 | Нечёткое сравнение с title/description/symptoms |
| Trigram overlap | 0.25 | Лексическое сходство на уровне триграмм |
| Embedding (numpy) | 0.00 | Bag-of-words cosine (опционально) |

Веса нормируются до суммы 1.0. Можно переопределить через ENV или поле `weights` в запросе.

### `app/core/catalog.py` — CatalogRegistry

При старте загружает все неисправности из SQLite в память. Классификация работает только с in-memory индексами — типичное время < 1 мс на запись.

После CRUD-операций вызывается `rebuild_catalog_index()`.

### `app/db/seeds.py`

JSON-файлы в `data/catalogs/` — источник истины. Идемпотентный upsert по `(catalog_name, code)`.

### `app/db/models.py`

- `Catalog` — метаданные справочника
- `Fault` — типовая неисправность
- `ClassificationLog` — журнал аудита

## Поток классификации

1. Запрос приходит с `catalog` + `context` (строка, список или StructuredContext)
2. Контекст нормализуется и обрезается до `max_context_length`
3. Для каждой неисправности каталога вычисляется confidence
4. Фильтрация по `min_confidence`, сортировка, top-k
5. При включённом логировании — запись в `classification_logs`

## Расширяемость

- Новый справочник: добавить `data/catalogs/<name>.json`, перезапустить или `make seed`
- Новый сигнал скорера: расширить `HybridScorer.score()`
- Embeddings: `pip install ".[full]"` + `ENABLE_EMBEDDINGS=true`