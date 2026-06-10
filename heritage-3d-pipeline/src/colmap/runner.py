"""
runner.py — COLMAPを呼び出してSfMを実行し、Gaussian Splatting用データセットを生成する

quality → max_image_size マッピング:
  high   → 4000
  medium → 2500
  low    → 1500

matcher:
  exhaustive  → 小〜中規模（〜500枚）
  sequential  → 動画・連続フレーム
  vocab_tree  → 大規模（500枚〜）
"""

import shutil
import subprocess
from pathlib import Path

from rich.console import Console

console = Console()

QUALITY_TO_MAX_IMAGE_SIZE = {
    "high":   4000,
    "medium": 2500,
    "low":    1500,
}

MATCHER_COMMANDS = {
    "exhaustive": "exhaustive_matcher",
    "sequential": "sequential_matcher",
    "vocab_tree": "vocab_tree_matcher",
}


class ColmapRunner:
    def __init__(self, config: dict):
        self.config = config
        cfg = config.get("colmap", {})
        # 入力画像: cleansing後、またはそのままの入力
        cleansed = Path(config["output_dir"]) / "cleansed"
        self.input_dir = cleansed if cleansed.exists() else Path(config["input_dir"])
        self.output_dir = Path(config["output_dir"]) / "colmap"
        self.gs_dataset_dir = Path(config["output_dir"]) / "gs_dataset"

        self.quality = cfg.get("quality", "high")
        self.max_image_size = QUALITY_TO_MAX_IMAGE_SIZE.get(self.quality, 4000)
        self.camera_model = cfg.get("camera_model", "SIMPLE_RADIAL")
        self.use_gpu = cfg.get("use_gpu", True)
        self.matcher = cfg.get("matcher", "exhaustive")
        self.vocab_tree_path = cfg.get("vocab_tree_path", "")

    def _run(self, cmd: list[str]):
        console.print(f"  [dim]$ {' '.join(cmd)}[/dim]")
        subprocess.run(cmd, check=True)

    def _feature_extraction(self, db: Path):
        self._run([
            "colmap", "feature_extractor",
            "--database_path", str(db),
            "--image_path", str(self.input_dir),
            "--ImageReader.camera_model", self.camera_model,
            "--ImageReader.single_camera", "1",
            "--SiftExtraction.use_gpu", "1" if self.use_gpu else "0",
            "--ImageReader.max_image_size", str(self.max_image_size),
        ])

    def _matching(self, db: Path):
        matcher_cmd = MATCHER_COMMANDS.get(self.matcher, "exhaustive_matcher")
        console.print(f"  マッチャー: [cyan]{self.matcher}[/cyan] ({matcher_cmd})")

        cmd = [
            "colmap", matcher_cmd,
            "--database_path", str(db),
            "--SiftMatching.use_gpu", "1" if self.use_gpu else "0",
        ]

        if self.matcher == "vocab_tree":
            if not self.vocab_tree_path:
                raise ValueError("vocab_tree matcher を使用する場合は vocab_tree_path を指定してください")
            cmd += ["--VocabTreeMatching.vocab_tree_path", self.vocab_tree_path]

        self._run(cmd)

    def _reconstruction(self, db: Path, sparse: Path):
        self._run([
            "colmap", "mapper",
            "--database_path", str(db),
            "--image_path", str(self.input_dir),
            "--output_path", str(sparse),
        ])

    def _prepare_gs_dataset(self, sparse: Path):
        """
        Gaussian Splatting が期待するデータセット構造を生成する。

        gs_dataset/
        ├─ images/          (入力画像のコピー)
        └─ sparse/
            └─ 0/           (COLMAP sparse/0/ のコピー)
        """
        gs_images = self.gs_dataset_dir / "images"
        gs_sparse0 = self.gs_dataset_dir / "sparse" / "0"

        gs_images.mkdir(parents=True, exist_ok=True)
        gs_sparse0.mkdir(parents=True, exist_ok=True)

        # 画像をコピー
        copied = 0
        for ext in ("*.jpg", "*.jpeg", "*.png", "*.JPG", "*.JPEG", "*.PNG"):
            for img in self.input_dir.glob(ext):
                shutil.copy2(img, gs_images / img.name)
                copied += 1
        console.print(f"  gs_dataset/images/ にコピー: {copied} 枚")

        # sparse/0 をコピー
        src_sparse0 = sparse / "0"
        if src_sparse0.exists():
            for f in src_sparse0.iterdir():
                shutil.copy2(f, gs_sparse0 / f.name)
            console.print(f"  gs_dataset/sparse/0/ にコピー完了")
        else:
            console.print(f"  [yellow]警告: {src_sparse0} が見つかりません[/yellow]")

        console.print(f"  gs_dataset 生成完了: {self.gs_dataset_dir}")

    def run(self):
        db = self.output_dir / "database.db"
        sparse = self.output_dir / "sparse"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        sparse.mkdir(exist_ok=True)

        console.print(f"  quality=[cyan]{self.quality}[/cyan]  max_image_size={self.max_image_size}")

        self._feature_extraction(db)
        self._matching(db)
        self._reconstruction(db, sparse)
        self._prepare_gs_dataset(sparse)

        console.print(f"  COLMAP完了: {sparse}")
