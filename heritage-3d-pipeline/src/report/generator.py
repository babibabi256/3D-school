"""
generator.py — 実験レポートを自動生成する
"""

import json
from datetime import datetime
from pathlib import Path
from rich.console import Console

console = Console()


class ReportGenerator:
    def __init__(self, config: dict):
        self.config = config
        cfg = config.get("report", {})
        self.output_dir = Path(config["output_dir"])
        self.report_file = self.output_dir / cfg.get("output_file", "report.md")
        self.metrics_path = self.output_dir / "evaluation" / "metrics.json"

    def _load_metrics(self) -> dict:
        if self.metrics_path.exists():
            with open(self.metrics_path) as f:
                return json.load(f)
        return {}

    def run(self):
        metrics = self._load_metrics()
        summary = metrics.get("summary", {})
        cfg = self.config

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        gaussian_cfg = cfg.get("gaussian", {})
        colmap_cfg = cfg.get("colmap", {})

        lines = [
            f"# 実験レポート: {cfg['project_name']}",
            f"",
            f"**生成日時:** {now}",
            f"",
            f"---",
            f"",
            f"## 実験概要",
            f"",
            f"| 項目 | 値 |",
            f"|---|---|",
            f"| プロジェクト名 | {cfg['project_name']} |",
            f"| 説明 | {cfg.get('description', '-')} |",
            f"| COLMAPクオリティ | {colmap_cfg.get('quality', '-')} |",
            f"| Gaussian反復数 | {gaussian_cfg.get('iterations', '-')} |",
            f"| SH次数 | {gaussian_cfg.get('sh_degree', '-')} |",
            f"",
            f"---",
            f"",
            f"## 評価結果",
            f"",
            f"| Metric | 値 |",
            f"|---|---|",
            f"| PSNR (mean) | {summary.get('psnr_mean', 'N/A'):.2f} dB |",
            f"| SSIM (mean) | {summary.get('ssim_mean', 'N/A'):.4f} |",
            f"| 評価画像数 | {summary.get('n_images', 'N/A')} |",
            f"",
            f"---",
            f"",
            f"## 考察",
            f"",
            f"（ここに考察を記入）",
            f"",
        ]

        self.report_file.write_text("\n".join(lines), encoding="utf-8")
        console.print(f"  レポート生成完了: {self.report_file}")
