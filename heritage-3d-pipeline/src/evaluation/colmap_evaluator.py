"""
colmap_evaluator.py — COLMAP再構成結果の研究用指標を算出する

出力: evaluation/colmap_metrics.json

指標:
  total_images       : 入力画像の総数
  registered_images  : COLMAPが登録した画像数
  registration_rate  : 登録率 (%)
  point_count        : 3D点群の総数
  reprojection_error : 平均再投影誤差 (px)  — points3D の ERROR フィールドの平均

COLMAP 出力形式の両方に対応:
  sparse/0/images.bin     / images.txt
  sparse/0/points3D.bin   / points3D.txt

binary フォーマット仕様 (COLMAP 公式):
  images.bin:
    uint64 num_reg_images
    per image: uint32 id, double[4] qvec, double[3] tvec, uint32 camera_id,
               char[] name (null-terminated),
               uint64 num_points2D, (double x, double y, int64 point3D_id)*

  points3D.bin:
    uint64 num_points3D
    per point: uint64 id, double[3] xyz, uint8[3] rgb, double error,
               uint64 track_length, (uint32 image_id, uint32 point2D_idx)*
"""

import json
import struct
from pathlib import Path

import numpy as np
from rich.console import Console
from rich.table import Table

console = Console()


# ------------------------------------------------------------------
# バイナリパーサー
# ------------------------------------------------------------------

def _parse_images_bin(path: Path) -> int:
    """images.bin から登録画像数を返す"""
    with open(path, "rb") as f:
        num_images = struct.unpack("<Q", f.read(8))[0]
        for _ in range(num_images):
            f.read(4)                      # image_id (uint32)
            f.read(8 * 4)                  # qvec (4 doubles)
            f.read(8 * 3)                  # tvec (3 doubles)
            f.read(4)                      # camera_id (uint32)
            # name: null-terminated string
            name_bytes = b""
            while True:
                c = f.read(1)
                if c == b"\x00":
                    break
                name_bytes += c
            num_points2D = struct.unpack("<Q", f.read(8))[0]
            f.read(num_points2D * (8 + 8 + 8))  # x, y (double), point3D_id (int64)
    return num_images


def _parse_points3D_bin(path: Path) -> tuple[int, float]:
    """
    points3D.bin から (点群数, 平均再投影誤差) を返す。
    """
    errors = []
    with open(path, "rb") as f:
        num_points = struct.unpack("<Q", f.read(8))[0]
        for _ in range(num_points):
            f.read(8)               # point3D_id (uint64)
            f.read(8 * 3)           # xyz (3 doubles)
            f.read(3)               # rgb (3 uint8)
            error = struct.unpack("<d", f.read(8))[0]
            errors.append(error)
            track_length = struct.unpack("<Q", f.read(8))[0]
            f.read(track_length * (4 + 4))  # (image_id, point2D_idx)
    mean_error = float(np.mean(errors)) if errors else 0.0
    return len(errors), mean_error


# ------------------------------------------------------------------
# テキストパーサー
# ------------------------------------------------------------------

def _parse_images_txt(path: Path) -> int:
    """images.txt から登録画像数を返す"""
    count = 0
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # 画像ヘッダー行: IMAGE_ID QW QX QY QZ TX TY TZ CAMERA_ID NAME
            # 2行ペアのうち奇数行目が画像ヘッダー
            count += 1
    # 画像ヘッダー行は全データ行の半数
    return count // 2


def _parse_points3D_txt(path: Path) -> tuple[int, float]:
    """
    points3D.txt から (点群数, 平均再投影誤差) を返す。
    フォーマット: POINT3D_ID X Y Z R G B ERROR TRACK[]
    """
    errors = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 8:
                try:
                    errors.append(float(parts[7]))
                except ValueError:
                    pass
    mean_error = float(np.mean(errors)) if errors else 0.0
    return len(errors), mean_error


# ------------------------------------------------------------------
# COLMAPEvaluator
# ------------------------------------------------------------------

class COLMAPEvaluator:
    def __init__(self, config: dict):
        self.config = config
        output_dir = Path(config["output_dir"])
        self.sparse0      = output_dir / "colmap" / "sparse" / "0"
        self.input_dir    = output_dir / "cleansed"
        if not self.input_dir.exists():
            self.input_dir = Path(config.get("input_dir", "input"))
        self.eval_dir = output_dir / "evaluation"

    def _count_input_images(self) -> int:
        total = 0
        for ext in ("*.jpg", "*.jpeg", "*.png", "*.JPG", "*.JPEG", "*.PNG"):
            total += len(list(self.input_dir.glob(ext)))
        return total

    def _load_registered_images(self) -> int:
        bin_path = self.sparse0 / "images.bin"
        txt_path = self.sparse0 / "images.txt"
        if bin_path.exists():
            return _parse_images_bin(bin_path)
        if txt_path.exists():
            return _parse_images_txt(txt_path)
        return 0

    def _load_points3D(self) -> tuple[int, float]:
        bin_path = self.sparse0 / "points3D.bin"
        txt_path = self.sparse0 / "points3D.txt"
        if bin_path.exists() and bin_path.stat().st_size > 8:
            return _parse_points3D_bin(bin_path)
        if txt_path.exists():
            return _parse_points3D_txt(txt_path)
        return 0, 0.0

    def run(self) -> dict:
        self.eval_dir.mkdir(parents=True, exist_ok=True)

        if not self.sparse0.exists():
            console.print(f"  [yellow]sparse/0/ が存在しません: {self.sparse0}[/yellow]")
            metrics = {
                "total_images": self._count_input_images(),
                "registered_images": 0,
                "registration_rate": 0.0,
                "point_count": 0,
                "reprojection_error": 0.0,
                "status": "sparse not found",
            }
            self._save(metrics)
            return metrics

        total      = self._count_input_images()
        registered = self._load_registered_images()
        reg_rate   = round(registered / total * 100, 1) if total > 0 else 0.0
        points, reproj_err = self._load_points3D()

        metrics = {
            "total_images":       total,
            "registered_images":  registered,
            "registration_rate":  reg_rate,
            "point_count":        points,
            "reprojection_error": round(reproj_err, 4),
        }
        self._save(metrics)
        self._print_table(metrics)
        return metrics

    def _save(self, metrics: dict):
        out = self.eval_dir / "colmap_metrics.json"
        with open(out, "w") as f:
            json.dump(metrics, f, indent=2)
        console.print(f"  COLMAP評価保存: {out}")

    def _print_table(self, m: dict):
        t = Table(title="COLMAP評価")
        t.add_column("指標")
        t.add_column("値", justify="right")
        t.add_row("総画像数",         str(m["total_images"]))
        t.add_row("登録画像数",       str(m["registered_images"]))
        t.add_row("登録率",           f"{m['registration_rate']} %")
        t.add_row("3D点群数",         f"{m['point_count']:,}")
        t.add_row("再投影誤差",       f"{m['reprojection_error']} px")
        console.print(t)
