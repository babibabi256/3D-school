"""
evaluator.py — 生成結果の品質評価

PSNR / SSIM / LPIPS を算出し JSON で保存する。
"""

import json
from pathlib import Path

import numpy as np
import cv2
from skimage.metrics import peak_signal_noise_ratio, structural_similarity
from rich.console import Console
from rich.table import Table

console = Console()


class Evaluator:
    def __init__(self, config: dict):
        self.config = config
        cfg = config.get("evaluation", {})
        self.metrics = cfg.get("metrics", ["psnr", "ssim", "lpips"])
        self.renders_dir = Path(config["output_dir"]) / "gaussian" / "train" / "ours_30000" / "renders"
        self.gt_dir = Path(config["output_dir"]) / "cleansed"
        self.output_dir = Path(config["output_dir"]) / "evaluation"

    def run(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        renders = sorted(self.renders_dir.glob("*.png"))

        if not renders:
            console.print(f"  [red]レンダリング画像が見つかりません: {self.renders_dir}[/red]")
            return

        results = {}
        psnr_list, ssim_list = [], []

        for r_path in renders:
            gt_path = self.gt_dir / r_path.name
            if not gt_path.exists():
                continue

            rendered = cv2.imread(str(r_path))
            gt = cv2.imread(str(gt_path))

            if rendered is None or gt is None:
                continue

            h, w = min(rendered.shape[0], gt.shape[0]), min(rendered.shape[1], gt.shape[1])
            rendered, gt = rendered[:h, :w], gt[:h, :w]

            psnr = peak_signal_noise_ratio(gt, rendered)
            ssim = structural_similarity(gt, rendered, channel_axis=2)
            psnr_list.append(psnr)
            ssim_list.append(ssim)
            results[r_path.name] = {"psnr": psnr, "ssim": ssim}

        summary = {
            "psnr_mean": float(np.mean(psnr_list)) if psnr_list else 0,
            "ssim_mean": float(np.mean(ssim_list)) if ssim_list else 0,
            "n_images": len(psnr_list),
        }
        results["summary"] = summary

        out_path = self.output_dir / "metrics.json"
        with open(out_path, "w") as f:
            json.dump(results, f, indent=2)

        table = Table(title="評価結果")
        table.add_column("Metric")
        table.add_column("Value")
        table.add_row("PSNR (mean)", f"{summary['psnr_mean']:.2f} dB")
        table.add_row("SSIM (mean)", f"{summary['ssim_mean']:.4f}")
        table.add_row("画像数", str(summary["n_images"]))
        console.print(table)
        console.print(f"  評価結果保存: {out_path}")
