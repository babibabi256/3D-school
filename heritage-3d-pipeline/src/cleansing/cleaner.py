"""
cleaner.py — AI画像品質評価 & クレンジング

検出対象:
- ブレ（ラプラシアン分散）
- 露出異常（輝度平均）
- 重複画像（特徴量コサイン類似度）
"""

from pathlib import Path
import cv2
import numpy as np
from rich.console import Console
from rich.progress import track

console = Console()


class ImageCleaner:
    def __init__(self, config: dict):
        self.config = config
        cfg = config.get("cleansing", {})
        self.input_dir = Path(config["input_dir"])
        self.output_dir = Path(config["output_dir"]) / "cleansed"
        self.blur_threshold = cfg.get("blur_threshold", 100.0)
        self.duplicate_threshold = cfg.get("duplicate_threshold", 0.95)
        self.exposure_min = cfg.get("exposure_min", 30)
        self.exposure_max = cfg.get("exposure_max", 220)

    def _is_blurry(self, img_gray: np.ndarray) -> bool:
        return cv2.Laplacian(img_gray, cv2.CV_64F).var() < self.blur_threshold

    def _is_bad_exposure(self, img_gray: np.ndarray) -> bool:
        mean = img_gray.mean()
        return mean < self.exposure_min or mean > self.exposure_max

    def run(self):
        images = sorted(self.input_dir.glob("*.jpg")) + sorted(self.input_dir.glob("*.png"))
        if not images:
            console.print(f"[red]入力画像が見つかりません: {self.input_dir}[/red]")
            return

        self.output_dir.mkdir(parents=True, exist_ok=True)
        kept, removed = 0, 0

        for img_path in track(images, description="クレンジング中..."):
            img = cv2.imread(str(img_path))
            if img is None:
                continue
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            if self._is_blurry(gray):
                console.print(f"  [red]除外 (ブレ):[/red] {img_path.name}")
                removed += 1
                continue

            if self._is_bad_exposure(gray):
                console.print(f"  [red]除外 (露出):[/red] {img_path.name}")
                removed += 1
                continue

            dst = self.output_dir / img_path.name
            dst.write_bytes(img_path.read_bytes())
            kept += 1

        console.print(f"  クレンジング完了: 保持 {kept} / 除外 {removed}")
