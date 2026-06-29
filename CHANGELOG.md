# Changelog

## [0.3.0] — 2026-06-25

### Added
- Локальная CPU-модель очистки персональных данных (`pd-cpu-v1`)
- API: `/api/v1/pd/clean`, `/api/v1/feedback`, дообучение, экспорт JSONL
- Интерфейс контролёра: `/ui` (очистка ПД, классификация, обратная связь)
- Таблицы: `pd_cleaning_logs`, `controller_feedback`, `learned_pd_patterns`
- Интеграция очистки ПД в пайплайн классификации

### Changed
- Документация переписана под новое описание сервиса
- Версия 0.2.0 → 0.3.0

## [0.2.0] — 2026-06-25

### Added
- 4 справочника: `servers` (28), `network` (25), `automotive` (14), `industrial` (14)
- Триграммный сигнал в гибридном скорере
- Структурированный контекст (description, symptoms, device, observed)
- Журнал классификаций (`/api/v1/history`, CLI `history`)
- Admin API: CRUD неисправностей (`/api/v1/admin/...`)
- CLI: `add-fault`, `history`
- Эндпоинт `/api/v1/config`
- Документация: `docs/USAGE.md`, `docs/ARCHITECTURE.md`, `docs/DEPLOYMENT.md`
- Makefile, CI workflow, multi-stage Dockerfile
- Расширенные тесты (coverage, performance benchmark)

### Changed
- Версия 0.1.0 → 0.2.0
- Веса скорера: keyword 0.35, fuzzy 0.40, trigram 0.25
- Идемпотентная загрузка сидов при каждом старте

## [0.1.0] — 2026-06-24

### Added
- Базовый сервис классификации с 2 справочниками
- FastAPI + CLI + Docker
- Гибридный скорер (keyword + fuzzy)