"""
runner.py — COLMAPを呼び出してSfMを実行する
"""

import subprocess
from pathlib import Path
from rich.console import Console

console = Console()


class ColmapRunner:
    def __init__(self, config: dict):
        self.config = config
        cfg = config.get("colmap", {})
        self.input_dir = Path(config["output_dir"]) / "cleansed"
        self.output_dir = Path(config["output_dir"]) / "colmap"
        self.quality = cfg.get("quality", "high")
        self.camera_model = cfg.get("camera_model", "SIMPLE_RADIAL")
        self.use_gpu = cfg.get("use_gpu", True)

    def _run(self, cmd: list[str]):
        console.print(f"  [dim]$ {' '.join(cmd)}[/dim]")
        subprocess.run(cmd, check=True)

    def run(self):
        db = self.output_dir / "database.db"
        sparse = self.output_dir / "sparse"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        sparse.mkdir(exist_ok=True)

        # 特徴抽出
        self._run([
            "colmap", "feature_extractor",
            "--database_path", str(db),
            "--image_path", str(self.input_dir),
            "--ImageReader.camera_model", self.camera_model,
            "--SiftExtraction.use_gpu", "1" if self.use_gpu else "0",
        ])

        # マッチング
        self._run([
            "colmap", "exhaustive_matcher",
            "--database_path", str(db),
            "--SiftMatching.use_gpu", "1" if self.use_gpu else "0",
        ])

        # 再構成
        self._run([
            "colmap", "mapper",
            "--database_path", str(db),
            "--image_path", str(self.input_dir),
            "--output_path", str(sparse),
        ])

        console.print(f"  COLMAP完了: {sparse}")
