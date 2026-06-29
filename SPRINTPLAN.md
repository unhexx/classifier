# SPRINTPLAN.md — unhexx-classifier

> Current sprint goals and iteration plan.  
> Maintained by Orchestrator / Reviewer.  
> Source of truth for next work after initial implementation.

## Sprint Goal

Complete 10 targeted iterations to mature the unified fault classification service from "working prototype" to production-grade, well-documented, extensible local service.

**Target outcome:** DONE — v0.2.0 released.

## Current State (post P1-08 implementation)

- 4 каталога высокого качества (servers ~50+, network ~50+, automotive ~40+, industrial ~40+) — построены по принципам FMEA, ITIL и CMMS.
- Гибридный скорер: keyword + fuzzy + trigram
- Полная поддержка PD cleaning + feedback loop
- Улучшенная документация по каталогам (CATALOG_DESIGN.md)
- 92%+ coverage, тесты на качество справочников
- Версия 0.3+ / приближение к v1.0

## 10 Iterations — Status

| # | Iteration | Status |
|---|-----------|--------|
| 1 | Test Hardening & Baseline | **DONE** — 39 tests, 92% cov, perf benchmark |
| 2 | More Reference Catalogs | **DONE** — 4 catalogs, 81 faults |
| 3 | Classification History | **DONE** — table + /history + CLI |
| 4 | Dynamic Catalog Management | **DONE** — Admin API + CLI add-fault |
| 5 | Documentation Overhaul | **DONE** — docs/ + README + CHANGELOG |
| 6 | Packaging & Container Polish | **DONE** — Dockerfile, Makefile, .dockerignore |
| 7 | Scorer & Config Improvements | **DONE** — trigram, structured context, /config |
| 8 | Robustness & Edge Cases | **DONE** — validation, normalization, error handlers |
| 9 | DevEx + Process | **DONE** — ruff, GitHub Actions CI |
| 10 | Release Prep & Meta | **DONE** — v0.2.0, PROJECT_CONTEXT updated |

## Backlog (future sprints)

- sentence-transformers as first-class optional matcher (P0-02)
- Полноценный релиз v1.0 (packaging, CI, docs, release automation)
- Export/import + bulk операции с каталогами
- Расширение количества записей в каталогах до production уровня
- Integration examples (monitoring, ticketing, CMMS)

## Tracking

**Sprint completed:** 2026-06-25
**Version:** 0.2.0