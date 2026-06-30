import json
from pathlib import Path

from app.services.eval_service import run_eval_cli


def test_eval_cli_runs(tmp_path):
    dataset_file = tmp_path / "test_dataset.jsonl"
    report_file = tmp_path / "test_report.md"

    record = {
        "context": "сервер не включается красный индикатор PSU",
        "correct_fault_code": "SRV-PSU-001",
        "catalog": "servers",
    }
    with open(dataset_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    run_eval_cli(
        dataset_path=dataset_file,
        catalog="servers",
        top_k=2,
        output_path=report_file,
    )

    assert report_file.exists()
    report_content = report_file.read_text(encoding="utf-8")
    assert "Baseline Evaluation Report" in report_content
    assert "Total cases**: 1" in report_content