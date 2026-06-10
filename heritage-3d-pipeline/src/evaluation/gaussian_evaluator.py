"""
gaussian_evaluator.py — Gaussian Splatting学習結果の研究用指標を算出する

出力: evaluation/gaussian_metrics.json

指標:
  training_time_sec  : 学習時間（秒）  ← training_metadata.json から取得
  training_time_hms  : 学習時間（HH:MM:SS 表記）
  iterations         : 学習反復数（config から取得）
  model_size_mb      : output/gaussian/ ディレクトリの合計サイズ (MB)
  point_cloud_size_mb: output/gaussian/point_cloud/**/*.ply の合計サイズ (MB)
"""

import json
from pathlib import Path

from rich.console import Console
from rich.table import Table

console = Console()


def _dir_size_mb(directory: Path) -> float:
    """ディレクトリ配下の全ファイルサイズ合計を MB で返す"""
    total = sum(f.stat().st_size for f in directory.rglob("*") if f.is_file())
    return round(total / (1024 * 1024), 2)


def _ply_size_mb(gaussian_dir: Path) -> float:
    """point_cloud/**/*.ply の合計サイズを MB で返す"""
    total = sum(
        f.stat().st_size
        for f in gaussian_dir.rglob("*.ply")
        if f.is_file()
    )
    return round(total / (1024 * 1024), 2)


def _seconds_to_hms(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


class GaussianEvaluator:
    def __init__(self, config: dict):
        self.config      = config
        output_dir       = Path(config["output_dir"])
        self.gaussian_dir = output_dir / "gaussian"
        self.eval_dir    = output_dir / "evaluation"
        self.iterations  = config.get("gaussian", {}).get("iterations", 30000)

    def _load_training_time(self) -> float:
        """training_metadata.json から経過秒数を読む。なければ 0 を返す。"""
        meta = self.gaussian_dir / "training_metadata.json"
        if meta.exists():
            with open(meta) as f:
                return float(json.load(f).get("elapsed_seconds", 0))
        return 0.0

    def run(self) -> dict:
        self.eval_dir.mkdir(parents=True, exist_ok=True)

        if not self.gaussian_dir.exists():
            console.print(f"  [yellow]gaussian/ が存在しません: {self.gaussian_dir}[/yellow]")
            metrics = {
                "training_time_sec":   0,
                "training_time_hms":   "00:00:00",
                "iterations":          self.iterations,
                "model_size_mb":       0,
                "point_cloud_size_mb": 0,
                "status":              "gaussian output not found",
            }
            self._save(metrics)
            return metrics

        elapsed  = self._load_training_time()
        model_mb = _dir_size_mb(self.gaussian_dir)
        ply_mb   = _ply_size_mb(self.gaussian_dir)

        metrics = {
            "training_time_sec":   round(elapsed, 1),
            "training_time_hms":   _seconds_to_hms(elapsed),
            "iterations":          self.iterations,
            "model_size_mb":       model_mb,
            "point_cloud_size_mb": ply_mb,
        }
        self._save(metrics)
        self._print_table(metrics)
        return metrics

    def _save(self, metrics: dict):
        out = self.eval_dir / "gaussian_metrics.json"
        with open(out, "w") as f:
            json.dump(metrics, f, indent=2)
        console.print(f"  Gaussian評価保存: {out}")

    def _print_table(self, m: dict):
        t = Table(title="Gaussian Splatting評価")
        t.add_column("指標")
        t.add_column("値", justify="right")
        t.add_row("学習時間",           m["training_time_hms"])
        t.add_row("反復数",             f"{m['iterations']:,}")
        t.add_row("モデルサイズ",       f"{m['model_size_mb']:,.1f} MB")
        t.add_row("点群サイズ (.ply)",  f"{m['point_cloud_size_mb']:,.1f} MB")
        console.print(t)
