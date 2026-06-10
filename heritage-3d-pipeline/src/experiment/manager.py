"""
manager.py — 複数実験を results/experiment_NNN/ 形式で管理する

各実験ディレクトリ構成:
  results/
  └─ experiment_001/
      ├─ config.yaml
      ├─ metrics.json
      ├─ experiment.json      (処理時間・GPU情報など)
      ├─ report.md
      └─ model/              (gaussian output のシンボリックリンクまたはコピー)
"""

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

import yaml
from rich.console import Console

console = Console()

RESULTS_DIR = Path("results")


class ExperimentManager:
    def __init__(self, config: dict):
        self.config = config
        self.results_dir = RESULTS_DIR
        self.experiment_dir: Path | None = None

    def _next_experiment_id(self) -> str:
        """results/ 内の最大番号 + 1 を 3桁ゼロ埋めで返す"""
        self.results_dir.mkdir(parents=True, exist_ok=True)
        existing = [
            d for d in self.results_dir.iterdir()
            if d.is_dir() and re.match(r"experiment_\d{3}", d.name)
        ]
        if not existing:
            return "001"
        nums = [int(d.name.split("_")[1]) for d in existing]
        return f"{max(nums) + 1:03d}"

    def setup(self) -> Path:
        """実験ディレクトリを作成し config.yaml を保存する"""
        exp_id = self._next_experiment_id()
        self.experiment_dir = self.results_dir / f"experiment_{exp_id}"
        self.experiment_dir.mkdir(parents=True, exist_ok=True)

        # config を保存
        with open(self.experiment_dir / "config.yaml", "w", encoding="utf-8") as f:
            yaml.dump(self.config, f, allow_unicode=True, default_flow_style=False)

        console.print(f"  実験ディレクトリ: [cyan]{self.experiment_dir}[/cyan]")
        return self.experiment_dir

    def save_results(self, experiment_json: dict, output_dir: Path):
        """
        実験終了後に各成果物を実験ディレクトリへ収集する。

        - experiment.json (処理時間・GPU情報など)
        - metrics.json    (PSNR/SSIM)
        - report.md
        - model/          (gaussian出力)
        """
        if self.experiment_dir is None:
            raise RuntimeError("setup() を先に呼び出してください")

        # experiment.json
        experiment_json["experiment_id"] = self.experiment_dir.name
        experiment_json["timestamp"] = datetime.now().isoformat()
        with open(self.experiment_dir / "experiment.json", "w") as f:
            json.dump(experiment_json, f, indent=2, ensure_ascii=False)

        # metrics.json (PSNR/SSIM)
        eval_dir = output_dir / "evaluation"
        for fname in ("metrics.json", "colmap_metrics.json", "gaussian_metrics.json"):
            src = eval_dir / fname
            if src.exists():
                shutil.copy2(src, self.experiment_dir / fname)

        # report.md
        report_src = output_dir / self.config.get("report", {}).get("output_file", "report.md")
        if report_src.exists():
            shutil.copy2(report_src, self.experiment_dir / "report.md")

        # model (gaussian output をコピー)
        model_src = output_dir / "gaussian"
        model_dst = self.experiment_dir / "model"
        if model_src.exists() and not model_dst.exists():
            console.print(f"  モデルをコピー中 (大容量の場合は時間がかかります)...")
            shutil.copytree(model_src, model_dst)

        console.print(f"  実験結果保存完了: {self.experiment_dir}")

    def list_experiments(self) -> list[dict]:
        """全実験の概要を返す"""
        experiments = []
        if not self.results_dir.exists():
            return experiments

        for exp_dir in sorted(self.results_dir.iterdir()):
            if not (exp_dir.is_dir() and re.match(r"experiment_\d{3}", exp_dir.name)):
                continue
            entry = {"id": exp_dir.name, "path": str(exp_dir)}

            exp_json = exp_dir / "experiment.json"
            if exp_json.exists():
                with open(exp_json) as f:
                    entry.update(json.load(f))

            metrics_json = exp_dir / "metrics.json"
            if metrics_json.exists():
                with open(metrics_json) as f:
                    data = json.load(f)
                    summary = data.get("summary", {})
                    entry["psnr_mean"] = summary.get("psnr_mean")
                    entry["ssim_mean"] = summary.get("ssim_mean")

            experiments.append(entry)

        return experiments
