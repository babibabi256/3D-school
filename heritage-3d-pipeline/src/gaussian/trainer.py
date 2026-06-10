"""
trainer.py — Gaussian Splattingの学習を実行する

3D Gaussian Splatting (https://github.com/graphdeco-inria/gaussian-splatting) を
サブプロセスで呼び出す想定。
"""

import subprocess
from pathlib import Path
from rich.console import Console

console = Console()

# Gaussian Splatting リポジトリのパス（Dockerfileでクローン済みを想定）
GS_REPO = Path("/opt/gaussian-splatting")


class GaussianTrainer:
    def __init__(self, config: dict):
        self.config = config
        cfg = config.get("gaussian", {})
        self.colmap_dir = Path(config["output_dir"]) / "colmap"
        self.output_dir = Path(config["output_dir"]) / "gaussian"
        self.iterations = cfg.get("iterations", 30000)
        self.sh_degree = cfg.get("sh_degree", 3)
        self.densify_until = cfg.get("densify_until_iter", 15000)

    def run(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            "python", str(GS_REPO / "train.py"),
            "-s", str(self.colmap_dir),
            "-m", str(self.output_dir),
            "--iterations", str(self.iterations),
            "--sh_degree", str(self.sh_degree),
            "--densify_until_iter", str(self.densify_until),
        ]

        console.print(f"  [dim]$ {' '.join(cmd)}[/dim]")
        subprocess.run(cmd, check=True)
        console.print(f"  Gaussian Splatting完了: {self.output_dir}")
