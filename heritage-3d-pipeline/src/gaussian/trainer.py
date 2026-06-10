"""
trainer.py — Gaussian Splattingの学習を実行する

入力: output/gs_dataset/  (COLMAP runner が生成)
出力: output/gaussian/

quality → 解像度設定:
  high   → resolution=-1 (フル解像度)
  medium → resolution=2  (1/2)
  low    → resolution=4  (1/4)

学習終了後に output/gaussian/training_metadata.json を書き出す:
  {
    "start_time": "2024-...",
    "end_time":   "2024-...",
    "elapsed_seconds": 8040.2,
    "iterations": 30000
  }
"""

import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

from rich.console import Console

console = Console()

GS_REPO = Path("/opt/gaussian-splatting")

QUALITY_TO_RESOLUTION = {
    "high":   -1,
    "medium":  2,
    "low":     4,
}


class GaussianTrainer:
    def __init__(self, config: dict):
        self.config   = config
        cfg           = config.get("gaussian", {})
        colmap_cfg    = config.get("colmap", {})

        self.source_dir = Path(config["output_dir"]) / "gs_dataset"
        self.output_dir = Path(config["output_dir"]) / "gaussian"

        self.iterations             = cfg.get("iterations", 30000)
        self.sh_degree              = cfg.get("sh_degree", 3)
        self.densify_until          = cfg.get("densify_until_iter", 15000)
        self.densify_grad_threshold = cfg.get("densify_grad_threshold", 0.0002)
        self.lambda_dssim           = cfg.get("lambda_dssim", 0.2)

        quality            = colmap_cfg.get("quality", "high")
        self.resolution    = QUALITY_TO_RESOLUTION.get(quality, -1)
        self._quality_label = quality

    def run(self) -> float:
        """学習を実行し、経過秒数を返す"""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        if not self.source_dir.exists():
            raise FileNotFoundError(
                f"gs_dataset が見つかりません: {self.source_dir}\n"
                "COLMAP を先に実行してください。"
            )

        console.print(
            f"  quality=[cyan]{self._quality_label}[/cyan]  resolution={self.resolution}"
        )

        cmd = [
            "python", str(GS_REPO / "train.py"),
            "-s", str(self.source_dir),
            "-m", str(self.output_dir),
            "--iterations",             str(self.iterations),
            "--sh_degree",              str(self.sh_degree),
            "--densify_until_iter",     str(self.densify_until),
            "--densify_grad_threshold", str(self.densify_grad_threshold),
            "--lambda_dssim",           str(self.lambda_dssim),
            "--resolution",             str(self.resolution),
        ]

        console.print(f"  [dim]$ {' '.join(cmd)}[/dim]")

        t_start = time.time()
        start_dt = datetime.now().isoformat()
        subprocess.run(cmd, check=True)
        elapsed = time.time() - t_start
        end_dt  = datetime.now().isoformat()

        # 学習メタデータを保存
        metadata = {
            "start_time":       start_dt,
            "end_time":         end_dt,
            "elapsed_seconds":  round(elapsed, 1),
            "iterations":       self.iterations,
        }
        meta_path = self.output_dir / "training_metadata.json"
        with open(meta_path, "w") as f:
            json.dump(metadata, f, indent=2)

        console.print(f"  Gaussian Splatting完了: {self.output_dir}  ({elapsed/3600:.2f}h)")
        return elapsed
