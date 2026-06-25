# Развёртывание

## Требования

- Python 3.11+
- 512 МБ RAM (без ML-расширений)
- Диск: ~100 МБ (код + справочники + журналы)

## Локальная установка

```bash
pip install -e ".[dev]"
make seed
unhexx-classifier serve --host 0.0.0.0 --port 8000
```

Проверка:

```bash
curl http://localhost:8000/health
# → pd_cleaning_enabled: true, pd_model_version: pd-cpu-v1

curl -o /dev/null -w "%{http_code}" http://localhost:8000/ui
# → 200
```

## Docker (преднастроенный образ)

### Сборка образа

```bash
make docker-build
# или
docker build -t unhexx-classifier:0.3.0 -t unhexx-classifier:latest .
```

Образ включает:
- Python 3.11 + все зависимости
- 4 справочника неисправностей (JSON seeds)
- Локальную CPU-модель очистки ПД (`pd-cpu-v1`)
- Интерфейс контролёра (`/ui`)
- Entrypoint с автоматической инициализацией БД при старте

### Запуск

```bash
make docker-up
# или
docker compose up --build -d
```

### Проверка

```bash
make docker-smoke
```

| URL | Назначение |
|-----|------------|
| http://localhost:8000/ui | Интерфейс контролёра |
| http://localhost:8000/docs | Swagger API |
| http://localhost:8000/health | Статус сервиса |

### Персистентность

Volume `classifier-data` монтируется в `/app/data` и сохраняет:
- SQLite-базу (`classifier.db`)
- Журналы классификаций и очистки ПД
- Дообученные правила и экспорт обратной связи

```bash
# Остановка (данные сохраняются)
make docker-down

# Полный сброс данных
docker compose down -v
```

### Запуск без compose

```bash
docker run -d \
  --name unhexx-classifier \
  -p 8000:8000 \
  -v classifier-data:/app/data \
  unhexx-classifier:0.3.0
```

## Переменные окружения

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `ENABLE_PD_CLEANING` | `true` | Включить очистку ПД перед классификацией |
| `ENABLE_PD_CLEANING_LOG` | `true` | Журналировать операции очистки |
| `PD_MODEL_VERSION` | `pd-cpu-v1` | Версия локальной модели |
| `DATABASE_URL` | `sqlite:///./data/classifier.db` | Путь к БД |
| `ENABLE_CLASSIFICATION_LOGGING` | `true` | Журнал классификаций |
| `DEFAULT_TOP_K` | `5` | Количество результатов |
| `DEFAULT_MIN_CONFIDENCE` | `0.25` | Порог уверенности |

Полный список — в `.env.example`.

## Рабочий процесс контролёра

1. Запустить сервис, открыть `/ui`
2. На вкладке «Очистка ПД» проверить качество маскирования
3. При пропуске ПД — вкладка «Обратная связь» → отправить исправление
4. Нажать «Применить» для дообучения модели
5. Повторно проверить тот же текст — правило должно сработать
6. Периодически экспортировать JSONL для внешнего переобучения

## Производительность

| Операция | Типичное время |
|----------|----------------|
| Очистка ПД | < 5 мс |
| Классификация (28 записей) | < 50 мс |
| Полный пайплайн | < 100 мс |

## Обновление

```bash
git pull
pip install -e ".[dev]"
make seed          # обновить справочники
# перезапустить сервис — таблицы создаются автоматически
```

Дообученные правила и обратная связь сохраняются в SQLite и не сбрасываются при обновлении справочников.

## systemd

```ini
[Unit]
Description=Unhexx Classifier (PD + Classification)
After=network.target

[Service]
Type=simple
User=classifier
WorkingDirectory=/opt/unhexx-classifier
Environment=ENABLE_PD_CLEANING=true
Environment=DATABASE_URL=sqlite:////opt/unhexx-classifier/data/classifier.db
ExecStart=/opt/unhexx-classifier/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=on-failure

[Install]
WantedBy=multi-user.target
```