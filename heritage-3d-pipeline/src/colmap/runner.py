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
        # 入力画像: cleansing後（画像が1枚以上ある場合のみ）、そうでなければ元の入力
        # ※ 空の cleansed ディレクトリが残っていても元の input_dir を使うようにする
        cleansed = Path(config["output_dir"]) / "cleansed"
        has_cleansed = cleansed.exists() and any(cleansed.glob("*.png")) or (cleansed.exists() and any(cleansed.glob("*.jpg")))
        self.input_dir = cleansed if has_cleansed else Path(config["input_dir"])
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
            "--SiftExtraction.max_image_size", str(self.max_image_size),
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

        公式GS (graphdeco-inria) は PINHOLE / SIMPLE_PINHOLE の
        「歪み補正済み」データセットのみ対応するため、COLMAP の
        image_undistorter で歪みを除去してから渡す。

        gs_dataset/
        ├─ images/          (undistorter が出力する補正済み画像)
        └─ sparse/
            └─ 0/           (PINHOLE モデルの cameras/images/points3D.bin)
        """
        src_sparse0 = sparse / "0"
        if not src_sparse0.exists():
            console.print(f"  [yellow]警告: {src_sparse0} が見つかりません[/yellow]")
            return

        # COLMAP image_undistorter（CPU実行・OpenGL不要）で PINHOLE データセットを生成
        self._run([
            "colmap", "image_undistorter",
            "--image_path", str(self.input_dir),
            "--input_path", str(src_sparse0),
            "--output_path", str(self.gs_dataset_dir),
            "--output_type", "COLMAP",
        ])

        # image_undistorter は sparse/ 直下に .bin を出力するため、
        # GS が期待する sparse/0/ へ移動する。
        gs_sparse = self.gs_dataset_dir / "sparse"
        gs_sparse0 = gs_sparse / "0"
        gs_sparse0.mkdir(parents=True, exist_ok=True)
        for name in ("cameras.bin", "images.bin", "points3D.bin"):
            f = gs_sparse / name
            if f.exists():
                shutil.move(str(f), str(gs_sparse0 / name))

        n_imgs = len(list((self.gs_dataset_dir / "images").glob("*")))
        console.print(f"  gs_dataset 生成完了 (undistorted/PINHOLE): {self.gs_dataset_dir}  画像 {n_imgs} 枚")

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
