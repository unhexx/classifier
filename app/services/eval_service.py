"""
Сервис оценки качества классификации (TASK-001).

Запуск baseline-метрик на размеченных датасетах.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from rich.console import Console
from rich.table import Table

from app.core.classifier import engine
from app.core.models import ClassifyRequest

console = Console()


@dataclass
class EvalResult:
    context: str
    predicted_code: str
    correct_code: str
    confidence: float
    rank: int
    latency_ms: float
    signals: dict[str, float]


@dataclass
class EvalReport:
    total: int
    accuracy_at_1: float
    accuracy_at_3: float
    mrr: float
    avg_confidence: float
    latency_p50: float
    latency_p95: float
    top_confusion: list[tuple[str, str, int]]
    per_catalog: dict[str, dict[str, float]]


def load_labeled_dataset(path: Path) -> list[dict[str, Any]]:
    """Загружает jsonl: {"context": str, "correct_fault_code": str, "catalog": str}."""
    data: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    return data


def run_baseline_eval(
    dataset: list[dict[str, Any]],
    top_k: int = 5,
    catalog: str | None = None,
) -> EvalReport:
    results: list[EvalResult] = []
    latencies: list[float] = []
    confusion: dict[tuple[str, str], int] = {}

    for item in dataset:
        ctx = item["context"]
        correct = item["correct_fault_code"]
        cat = item.get("catalog", catalog or "servers")

        start = time.perf_counter()
        try:
            req = ClassifyRequest(
                catalog=cat,
                context=ctx,
                top_k=top_k,
                include_scoring_details=True,
            )
            response = engine.classify(req)
        except Exception as exc:
            console.print(f"[red]Ошибка классификации: {exc}[/red]")
            continue

        latency = (time.perf_counter() - start) * 1000.0
        latencies.append(latency)

        matches = response.matches
        predicted = matches[0].code if matches else "UNKNOWN"
        confidence = matches[0].confidence if matches else 0.0

        rank = 999
        for i, m in enumerate(matches):
            if m.code == correct:
                rank = i + 1
                break

        reasons = matches[0].matched_reasons if matches else []
        signals: dict[str, float] = {}
        if isinstance(reasons, list):
            for r in reasons:
                if "=" in r:
                    k, v = r.split("=", 1)
                    try:
                        signals[k.strip()] = float(v.strip())
                    except ValueError:
                        signals[k.strip()] = 1.0
                elif ":" in r:
                    k, v = r.split(":", 1)
                    try:
                        signals[k.strip()] = float(v.strip())
                    except ValueError:
                        signals[k.strip()] = 1.0
                else:
                    signals[r.strip()] = 1.0
        elif isinstance(reasons, dict):
            signals = reasons

        results.append(
            EvalResult(
                context=ctx[:180] + "..." if len(ctx) > 180 else ctx,
                predicted_code=predicted,
                correct_code=correct,
                confidence=confidence,
                rank=rank,
                latency_ms=latency,
                signals=signals,
            )
        )

        key = (predicted, correct)
        confusion[key] = confusion.get(key, 0) + 1

    total = len(results) or 1
    acc1 = sum(1 for r in results if r.rank == 1) / total
    acc3 = sum(1 for r in results if r.rank <= 3) / total
    mrr = sum(1.0 / r.rank for r in results if r.rank < 999) / total
    avg_conf = float(np.mean([r.confidence for r in results])) if results else 0.0
    p50 = float(np.percentile(latencies, 50)) if latencies else 0.0
    p95 = float(np.percentile(latencies, 95)) if latencies else 0.0

    sorted_conf = sorted(confusion.items(), key=lambda x: -x[1])[:5]
    top_confusion = [(p, c, cnt) for (p, c), cnt in sorted_conf]

    return EvalReport(
        total=len(results),
        accuracy_at_1=round(acc1, 4),
        accuracy_at_3=round(acc3, 4),
        mrr=round(mrr, 4),
        avg_confidence=round(avg_conf, 4),
        latency_p50=round(p50, 1),
        latency_p95=round(p95, 1),
        top_confusion=top_confusion,
        per_catalog={},
    )


def save_report(report: EvalReport, output: Path) -> None:
    md = f"""# Baseline Evaluation Report

**Generated**: {time.strftime('%Y-%m-%d %H:%M')}
**Total cases**: {report.total}

| Metric              | Value     |
|---------------------|-----------|
| Accuracy@1          | {report.accuracy_at_1:.2%} |
| Accuracy@3          | {report.accuracy_at_3:.2%} |
| MRR                 | {report.mrr:.4f} |
| Avg Confidence      | {report.avg_confidence:.3f} |
| Latency p50 / p95   | {report.latency_p50} / {report.latency_p95} ms |

## Top Confusion Pairs (predicted → correct)

"""
    for p, c, cnt in report.top_confusion:
        md += f"- `{p}` → `{c}` : **{cnt}** occurrences\n"

    output.write_text(md, encoding="utf-8")
    console.print(f"[green]Отчёт сохранён в {output}[/green]")


def run_eval_cli(
    dataset_path: Path,
    catalog: str = "servers",
    top_k: int = 5,
    output_path: Path = Path("eval_report.md"),
) -> None:
    """Запускает baseline-оценку на размеченном датасете."""
    from app.core.catalog import catalog_registry
    from app.db.seeds import ensure_catalogs_loaded
    from app.db.session import SessionLocal, init_db

    console.rule("[bold blue]unhexx-classifier eval[/bold blue]")

    init_db()
    with SessionLocal() as db:
        ensure_catalogs_loaded(db)
        catalog_registry.load_from_db(db)

    dataset_path = Path(dataset_path)
    if not dataset_path.exists():
        console.print(f"[red]Ошибка: файл датасета {dataset_path} не найден.[/red]")
        return

    data = load_labeled_dataset(dataset_path)
    console.print(f"Загружено {len(data)} размеченных примеров из {dataset_path}")

    report = run_baseline_eval(data, top_k=top_k, catalog=catalog)

    table = Table(title="Baseline Metrics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="magenta")
    table.add_row("Accuracy@1", f"{report.accuracy_at_1:.2%}")
    table.add_row("Accuracy@3", f"{report.accuracy_at_3:.2%}")
    table.add_row("MRR", f"{report.mrr:.4f}")
    table.add_row("Latency p50 / p95", f"{report.latency_p50} / {report.latency_p95} ms")
    table.add_row("Avg Confidence", f"{report.avg_confidence:.3f}")
    console.print(table)

    save_report(report, Path(output_path))