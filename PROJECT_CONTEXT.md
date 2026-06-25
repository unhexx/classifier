# PROJECT_CONTEXT.md

> **Source of Truth:** `TASK_SPECIFICATION.md`  
> This file is updated by the **Orchestrator** (current status) and the **Reviewer** (self-improvement log).  
> Maximum size: ~3000 tokens. Compress older entries when necessary.  
> All content must be in English.

## Project Identification

| Parameter       | Value                                      |
|-----------------|--------------------------------------------|
| **Project**     | `unhexx-classifier`                        |
| **Goal**        | Unified local-first classification service for typical malfunctions. Accepts context + catalog name via API/CLI and returns ranked list of faults with confidence. Fully self-contained "out of the box". |
| **Tech Stack**  | Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.0, SQLite, rapidfuzz, numpy, pytest, Docker |
| **Current Branch** | `main`                                  |
| **Git User**    | `unhexx <dev@unhexx.example>`              |

---

## Current Status

| Field                  | Value                                      |
|------------------------|--------------------------------------------|
| **Cycle Number**       | `2`                                        |
| **Current Phase**      | `complete — v0.2.0 released`               |
| **Active Role**        | `Orchestrator`                             |
| **Status**             | `DONE`                                     |
| **Confidence**         | `0.95`                                     |
| **Last Commit**        | `v0.2.0: полный цикл 10 итераций`          |
| **Last Updated**       | `2026-06-25`                               |

## Project Summary

Production-ready local classification service:

- **4 catalogs:** servers (28), network (25), automotive (14), industrial (14)
- **Hybrid scorer:** Jaccard keyword + rapidfuzz fuzzy + trigram overlap
- **API:** classify, catalogs, faults, history, config, admin CRUD
- **CLI:** classify, serve, history, add-fault
- **Infrastructure:** Docker multi-stage, docker-compose, Makefile, CI
- **Tests:** 39 passing, 92% coverage, performance benchmark < 100ms
- **Docs:** README, USAGE, ARCHITECTURE, DEPLOYMENT, CHANGELOG

## Cycle History

| Cycle | Role         | Phase          | Status | Key Outcomes |
|-------|--------------|----------------|--------|--------------|
| 0     | bootstrap    | initial dev    | DONE   | Basic service: 2 catalogs, API, CLI, Docker |
| 1     | Orchestrator | planning       | DONE   | SPRINTPLAN with 10 iterations |
| 2     | Orchestrator | implementation | DONE   | All 10 iterations complete, v0.2.0 |

## Key Decisions

- Hybrid lightweight classifier (no heavy model downloads by default)
- SQLite + JSON seeds as source of truth
- In-memory indexes for speed (<1ms per fault scoring)
- Admin API without auth (trusted local environment)
- Russian user-facing content, Russian code comments

## Known Limitations

- No sentence-transformers by default (optional via `[full]` extra)
- No web UI (Swagger only)
- Admin API unauthenticated (local use only)
- CLI not covered in wheel data path (seeds loaded from project dir)

## Next Actions

Project v0.2.0 is complete per TASK_SPECIFICATION.md Definition of Done. Future work in backlog (see SPRINTPLAN.md).

---
*Living context — updated 2026-06-25.*