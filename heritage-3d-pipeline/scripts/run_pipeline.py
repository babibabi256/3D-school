#!/usr/bin/env python3
"""
run_pipeline.py — 文化財3D生成パイプライン エントリーポイント

Usage:
    python scripts/run_pipeline.py --config configs/experiment.yaml
"""

import argparse
import json
import math
import sys
import time
from pathlib import Path

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cleansing.cleaner          import ImageCleaner
from colmap.runner              import ColmapRunner
from gaussian.trainer           import GaussianTrainer
from evaluation.evaluator       import Evaluator
from evaluation.colmap_evaluator   import COLMAPEvaluator
from evaluation.gaussian_evaluator import GaussianEvaluator
from report.generator           import ReportGenerator
from experiment.manager         import ExperimentManager
from experiment.result_saver    import ResultSaver
from experiment.comparison      import ComparisonReportGenerator

console = Console()


# ------------------------------------------------------------------
# ユーティリティ
# ------------------------------------------------------------------

def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _hms(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    if h > 0:
        return f"{h}h{m:02d}m{s:02d}s"
    return f"{m}m{s:02d}s"


def _fmt_size(mb: float) -> str:
    if mb >= 1024:
        return f"{mb/1024:.1f} GB"
    return f"{mb:.0f} MB"


def _print_research_summary(
    colmap_m: dict,
    gs_m:     dict,
    image_m:  dict,
    elapsed:  float,
):
    """
    研究用サマリーを rich.Panel で表示する。

    例:
    ┌─ 研究用サマリー ──────────────────────────────────────────────┐
    │ Images: 532  Registered: 519 (97.6%)                         │
    │ Points: 1,820,331  Reprojection Error: 0.62 px               │
    │ Training Time: 2h14m  Model Size: 1.8 GB                     │
    │ PSNR: 28.4 dB  SSIM: 0.842   Total: 2h31m                   │
    └──────────────────────────────────────────────────────────────┘
    """
    total_img  = colmap_m.get("total_images", 0)
    reg_img    = colmap_m.get("registered_images", 0)
    reg_rate   = colmap_m.get("registration_rate", 0.0)
    pt_count   = colmap_m.get("point_count", 0)
    reproj_err = colmap_m.get("reprojection_error", 0.0)

    train_sec  = gs_m.get("training_time_sec", 0)
    model_mb   = gs_m.get("model_size_mb", 0)

    psnr       = image_m.get("psnr_mean")
    ssim       = image_m.get("ssim_mean")

    psnr_str = f"{psnr:.2f} dB" if psnr and not math.isinf(psnr) else "—"
    ssim_str = f"{ssim:.3f}"    if ssim else "—"

    lines = [
        f"[bold]Images:[/bold] {total_img:,}  "
        f"[bold]Registered:[/bold] {reg_img:,} ({reg_rate:.1f}%)",

        f"[bold]Points:[/bold] {pt_count:,}  "
        f"[bold]Reprojection Error:[/bold] {reproj_err:.2f} px",

        f"[bold]Training Time:[/bold] {_hms(train_sec)}  "
        f"[bold]Model Size:[/bold] {_fmt_size(model_mb)}",

        f"[bold]PSNR:[/bold] {psnr_str}  "
        f"[bold]SSIM:[/bold] {ssim_str}  "
        f"[bold]Total:[/bold] {_hms(elapsed)}",
    ]

    console.print(Panel(
        "\n".join(lines),
        title="[bold cyan]研究用サマリー[/bold cyan]",
        border_style="cyan",
        expand=False,
    ))


# ------------------------------------------------------------------
# メイン
# ------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="文化財3D生成パイプライン")
    parser.add_argument("--config", required=True, help="実験設定ファイルのパス")
    parser.add_argument("--no-experiment-manager", action="store_true",
                        help="実験管理を無効化（results/ に保存しない）")
    args = parser.parse_args()

    config     = load_config(args.config)
    project    = config["project_name"]
    start_time = time.time()
    output_dir = Path(config["output_dir"])

    console.print(Panel(f"[bold cyan]プロジェクト: {project}[/bold cyan]", expand=False))

    # 実験管理セットアップ
    exp_manager = None
    if not args.no_experiment_manager:
        exp_manager = ExperimentManager(config)
        exp_manager.setup()

    # ------------------------------------------------------------------
    # Step 1: クレンジング
    # ------------------------------------------------------------------
    if config.get("cleansing", {}).get("enabled", False):
        console.print("\n[bold yellow]Step 1: 画像クレンジング[/bold yellow]")
        ImageCleaner(config).run()
    else:
        console.print("\n[dim]Step 1: クレンジング（スキップ）[/dim]")

    # ------------------------------------------------------------------
    # Step 2: COLMAP + gs_dataset 生成
    # ------------------------------------------------------------------
    console.print("\n[bold yellow]Step 2: COLMAP & gs_dataset 生成[/bold yellow]")
    ColmapRunner(config).run()

    # ------------------------------------------------------------------
    # Step 2b: COLMAP評価
    # ------------------------------------------------------------------
    console.print("\n[bold yellow]Step 2b: COLMAP評価[/bold yellow]")
    colmap_metrics = COLMAPEvaluator(config).run()

    # ------------------------------------------------------------------
    # Step 3: Gaussian Splatting
    # ------------------------------------------------------------------
    console.print("\n[bold yellow]Step 3: Gaussian Splatting[/bold yellow]")
    GaussianTrainer(config).run()

    # ------------------------------------------------------------------
    # Step 3b: Gaussian評価
    # ------------------------------------------------------------------
    console.print("\n[bold yellow]Step 3b: Gaussian Splatting評価[/bold yellow]")
    gaussian_metrics = GaussianEvaluator(config).run()

    # ------------------------------------------------------------------
    # Step 4: レンダリング品質評価 (PSNR/SSIM)
    # ------------------------------------------------------------------
    image_metrics = {}
    if config.get("evaluation", {}).get("enabled", False):
        console.print("\n[bold yellow]Step 4: レンダリング品質評価[/bold yellow]")
        Evaluator(config).run()
        metrics_json = output_dir / "evaluation" / "metrics.json"
        if metrics_json.exists():
            with open(metrics_json) as f:
                image_metrics = json.load(f).get("summary", {})
    else:
        console.print("\n[dim]Step 4: レンダリング品質評価（スキップ）[/dim]")

    # ------------------------------------------------------------------
    # Step 5: レポート生成
    # ------------------------------------------------------------------
    if config.get("report", {}).get("enabled", False):
        console.print("\n[bold yellow]Step 5: レポート生成[/bold yellow]")
        ReportGenerator(config).run()
    else:
        console.print("\n[dim]Step 5: レポート生成（スキップ）[/dim]")

    # ------------------------------------------------------------------
    # Step 6: 実験結果保存
    # ------------------------------------------------------------------
    console.print("\n[bold yellow]Step 6: 実験結果保存[/bold yellow]")
    saver       = ResultSaver(config, start_time)
    result_path = saver.save()

    if exp_manager is not None:
        with open(result_path) as f:
            experiment_json = json.load(f)
        exp_manager.save_results(experiment_json, output_dir)

        # ------------------------------------------------------------------
        # Step 7: 実験比較レポート更新
        # ------------------------------------------------------------------
        console.print("\n[bold yellow]Step 7: 実験比較レポート更新[/bold yellow]")
        ComparisonReportGenerator().run()

    # ------------------------------------------------------------------
    # 研究用サマリー表示
    # ------------------------------------------------------------------
    elapsed = time.time() - start_time
    console.print()
    _print_research_summary(colmap_metrics, gaussian_metrics, image_metrics, elapsed)


if __name__ == "__main__":
    main()
