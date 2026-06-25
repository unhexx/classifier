# SPRINTPLAN.md — unhexx-classifier

> Current sprint goals and iteration plan.  
> Maintained by Orchestrator / Reviewer.  
> Source of truth for next work after initial implementation.

## Sprint Goal

Complete 10 targeted iterations to mature the unified fault classification service from "working prototype" to production-grade, well-documented, extensible local service.

**Target outcome:** DONE — v0.2.0 released.

## Current State (post Cycle 2)

- 4 catalogs: servers (28), network (25), automotive (14), industrial (14) — 81 total faults
- Hybrid scorer: keyword + fuzzy + trigram
- Classification history, Admin CRUD API, structured context
- 39 tests, 92% coverage
- Docs: USAGE, ARCHITECTURE, DEPLOYMENT
- Docker multi-stage, Makefile, CI workflow
- Version 0.2.0

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

- sentence-transformers as first-class optional matcher
- Web UI demo (HTMX or Streamlit)
- Export/import catalogs (JSONL or zip)
- Integration examples (monitoring, ticketing)

## Tracking

**Sprint completed:** 2026-06-25
**Version:** 0.2.0