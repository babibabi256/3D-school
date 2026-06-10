#!/usr/bin/env python3
"""
run_pipeline.py — パイプライン全体のエントリーポイント

Usage:
    python scripts/run_pipeline.py --config configs/experiment.yaml
"""

import argparse
import sys
from pathlib import Path

import yaml
from rich.console import Console
from rich.panel import Panel

# src を import パスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cleansing.cleaner import ImageCleaner
from colmap.runner import ColmapRunner
from gaussian.trainer import GaussianTrainer
from evaluation.evaluator import Evaluator
from report.generator import ReportGenerator

console = Console()


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser(description="文化財3D生成パイプライン")
    parser.add_argument("--config", required=True, help="実験設定ファイルのパス")
    args = parser.parse_args()

    config = load_config(args.config)
    project = config["project_name"]

    console.print(Panel(f"[bold cyan]プロジェクト: {project}[/bold cyan]", expand=False))

    # 1. クレンジング
    if config.get("cleansing", {}).get("enabled", False):
        console.print("\n[bold yellow]Step 1: 画像クレンジング[/bold yellow]")
        cleaner = ImageCleaner(config)
        cleaner.run()

    # 2. COLMAP
    console.print("\n[bold yellow]Step 2: COLMAP[/bold yellow]")
    colmap = ColmapRunner(config)
    colmap.run()

    # 3. Gaussian Splatting
    console.print("\n[bold yellow]Step 3: Gaussian Splatting[/bold yellow]")
    trainer = GaussianTrainer(config)
    trainer.run()

    # 4. 評価
    if config.get("evaluation", {}).get("enabled", False):
        console.print("\n[bold yellow]Step 4: 評価[/bold yellow]")
        evaluator = Evaluator(config)
        evaluator.run()

    # 5. レポート生成
    if config.get("report", {}).get("enabled", False):
        console.print("\n[bold yellow]Step 5: レポート生成[/bold yellow]")
        reporter = ReportGenerator(config)
        reporter.run()

    console.print(Panel("[bold green]パイプライン完了[/bold green]", expand=False))


if __name__ == "__main__":
    main()
