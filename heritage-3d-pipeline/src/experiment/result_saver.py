"""
result_saver.py — 実験メタデータを収集して JSON に保存する

保存内容:
{
  "project_name": "",
  "image_count": 0,
  "processing_time": 0,        # 秒
  "point_count": 0,            # COLMAP point3D 数
  "gaussian_size_mb": 0,       # .ply ファイルサイズ
  "gpu_name": "",
  "gpu_memory_mb": 0
}
"""

import json
import subprocess
import time
from pathlib import Path

from rich.console import Console

console = Console()


def _get_gpu_info() -> tuple[str, int]:
    """nvidia-smi から GPU名とVRAM(MB)を取得する"""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        lines = result.stdout.strip().splitlines()
        if lines:
            parts = lines[0].split(", ")
            gpu_name = parts[0].strip()
            gpu_memory_mb = int(parts[1].strip())
            return gpu_name, gpu_memory_mb
    except Exception:
        pass
    return "unknown", 0


def _count_images(image_dir: Path) -> int:
    if not image_dir.exists():
        return 0
    count = 0
    for ext in ("*.jpg", "*.jpeg", "*.png", "*.JPG", "*.JPEG", "*.PNG"):
        count += len(list(image_dir.glob(ext)))
    return count


def _count_colmap_points(colmap_dir: Path) -> int:
    """COLMAP sparse/0/points3D.txt の行数（点群数）を返す"""
    points_file = colmap_dir / "sparse" / "0" / "points3D.txt"
    if not points_file.exists():
        # バイナリ形式を試みる
        points_file = colmap_dir / "sparse" / "0" / "points3D.bin"
        if not points_file.exists():
            return 0
        return points_file.stat().st_size // 43  # 概算: 43 bytes / point
    with open(points_file) as f:
        lines = [l for l in f if not l.startswith("#") and l.strip()]
    return len(lines)


def _gaussian_size_mb(gaussian_dir: Path) -> float:
    """output gaussian の .ply ファイル合計サイズ (MB)"""
    total = sum(f.stat().st_size for f in gaussian_dir.rglob("*.ply") if f.is_file())
    return round(total / (1024 * 1024), 2)


class ResultSaver:
    def __init__(self, config: dict, start_time: float):
        self.config = config
        self.start_time = start_time
        self.output_dir = Path(config["output_dir"])
        self.results_dir = Path("results")

    def save(self, experiment_id: str | None = None) -> Path:
        elapsed = round(time.time() - self.start_time, 1)
        gpu_name, gpu_memory_mb = _get_gpu_info()

        image_dir = self.output_dir / "cleansed"
        if not image_dir.exists():
            image_dir = Path(self.config["input_dir"])

        result = {
            "project_name":    self.config.get("project_name", ""),
            "image_count":     _count_images(image_dir),
            "processing_time": elapsed,
            "point_count":     _count_colmap_points(self.output_dir / "colmap"),
            "gaussian_size_mb": _gaussian_size_mb(self.output_dir / "gaussian"),
            "gpu_name":        gpu_name,
            "gpu_memory_mb":   gpu_memory_mb,
        }

        self.results_dir.mkdir(parents=True, exist_ok=True)

        if experiment_id:
            out_path = self.results_dir / f"{experiment_id}.json"
        else:
            # experiment_NNN.json の連番を自動付番
            existing = sorted(self.results_dir.glob("experiment_*.json"))
            next_num = len(existing) + 1
            out_path = self.results_dir / f"experiment_{next_num:03d}.json"

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        console.print(f"  実験結果保存: [cyan]{out_path}[/cyan]")
        console.print(
            f"    処理時間={elapsed}s  画像数={result['image_count']}"
            f"  点群数={result['point_count']}  GPU={gpu_name}"
        )
        return out_path
