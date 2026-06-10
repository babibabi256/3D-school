"""
comparison.py — results/ 配下の全実験を集計して comparison_report.md を生成する

集計列:
  experiment_id / project_name / timestamp
  image_count / registered_images / registration_rate / point_count / reprojection_error
  training_time / model_size_mb / psnr_mean / ssim_mean

出力: results/comparison_report.md
"""

import json
import re
from datetime import datetime
from pathlib import Path

from rich.console import Console

console = Console()

RESULTS_DIR = Path("results")


def _load_json(path: Path) -> dict:
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def _fmt(val, fmt=None, fallback="—"):
    """None / 0 を "—" で表示、それ以外は fmt で整形"""
    if val is None:
        return fallback
    if isinstance(val, float) and val == 0.0:
        return fallback
    if fmt:
        try:
            return format(val, fmt)
        except Exception:
            return str(val)
    return str(val)


def _hms(sec) -> str:
    if not sec:
        return "—"
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    if h > 0:
        return f"{h}h{m:02d}m"
    return f"{m}m{s:02d}s"


class ComparisonReportGenerator:
    def __init__(self, results_dir: Path = RESULTS_DIR):
        self.results_dir = results_dir
        self.output_path = results_dir / "comparison_report.md"

    def _collect(self) -> list[dict]:
        rows = []
        if not self.results_dir.exists():
            return rows

        for exp_dir in sorted(self.results_dir.iterdir()):
            if not (exp_dir.is_dir() and re.match(r"experiment_\d+", exp_dir.name)):
                continue

            exp   = _load_json(exp_dir / "experiment.json")
            col   = _load_json(exp_dir / "colmap_metrics.json")
            gs    = _load_json(exp_dir / "gaussian_metrics.json")
            metr  = _load_json(exp_dir / "metrics.json")

            summary = metr.get("summary", {})

            rows.append({
                "experiment_id":     exp_dir.name,
                "project_name":      exp.get("project_name", "—"),
                "timestamp":         (exp.get("timestamp", "")[:16]
                                      .replace("T", " ") or "—"),
                # COLMAP
                "image_count":       col.get("total_images")
                                     or exp.get("image_count"),
                "registered_images": col.get("registered_images"),
                "registration_rate": col.get("registration_rate"),
                "point_count":       col.get("point_count"),
                "reprojection_error":col.get("reprojection_error"),
                # Gaussian
                "training_time_sec": gs.get("training_time_sec"),
                "training_time_hms": gs.get("training_time_hms"),
                "model_size_mb":     gs.get("model_size_mb"),
                # レンダリング品質
                "psnr_mean":         summary.get("psnr_mean"),
                "ssim_mean":         summary.get("ssim_mean"),
            })

        return rows

    def _build_markdown(self, rows: list[dict]) -> str:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        lines = [
            "# 実験比較レポート",
            "",
            f"**生成日時:** {now}  ",
            f"**実験数:** {len(rows)}",
            "",
            "---",
            "",
            "## 実験一覧",
            "",
        ]

        # ---- 主要比較表 ----
        header = (
            "| experiment_id | project | timestamp | "
            "image_count | registered | reg_rate | "
            "point_count | reproj_err | "
            "train_time | model_size_mb |"
        )
        sep = (
            "|---|---|---|"
            "---:|---:|---:|"
            "---:|---:|"
            "---:|---:|"
        )
        lines += [header, sep]

        for r in rows:
            reg_rate = (f"{r['registration_rate']:.1f}%" if r["registration_rate"] is not None else "—")
            reproj   = (f"{r['reprojection_error']:.3f} px" if r["reprojection_error"] else "—")
            pt_cnt   = (f"{r['point_count']:,}" if r["point_count"] else "—")
            img_cnt  = (str(r["image_count"]) if r["image_count"] else "—")
            reg      = (str(r["registered_images"]) if r["registered_images"] is not None else "—")
            train    = r.get("training_time_hms") or "—"
            model_mb = (f"{r['model_size_mb']:.1f}" if r["model_size_mb"] else "—")

            lines.append(
                f"| {r['experiment_id']} | {r['project_name']} | {r['timestamp']} | "
                f"{img_cnt} | {reg} | {reg_rate} | "
                f"{pt_cnt} | {reproj} | "
                f"{train} | {model_mb} |"
            )

        lines += [""]

        # ---- レンダリング品質表（GS実行済みの実験のみ） ----
        quality_rows = [r for r in rows if r.get("psnr_mean") is not None]
        if quality_rows:
            lines += [
                "## レンダリング品質",
                "",
                "| experiment_id | PSNR (dB) | SSIM |",
                "|---|---:|---:|",
            ]
            for r in quality_rows:
                psnr = f"{r['psnr_mean']:.2f}" if r["psnr_mean"] else "—"
                ssim = f"{r['ssim_mean']:.4f}" if r["ssim_mean"] else "—"
                lines.append(f"| {r['experiment_id']} | {psnr} | {ssim} |")
            lines += [""]

        # ---- ベスト実験 ----
        lines += ["## ベスト実験", ""]

        def best(key, fn=max, label=None):
            valid = [(r[key], r["experiment_id"]) for r in rows if r.get(key) is not None]
            if not valid:
                return f"**{label or key}:** データなし"
            val, eid = fn(valid, key=lambda x: x[0])
            return f"**{label or key}:** {eid}  (`{val}`)"

        lines.append(best("registration_rate", max, "登録率 最高"))
        lines.append(best("reprojection_error", min, "再投影誤差 最小"))
        lines.append(best("point_count", max, "点群数 最多"))
        lines.append(best("psnr_mean", max, "PSNR 最高"))
        lines.append(best("model_size_mb", min, "モデルサイズ 最小"))
        lines += [""]

        return "\n".join(lines)

    def run(self) -> Path:
        rows = self._collect()
        if not rows:
            console.print("  [yellow]比較対象の実験がありません[/yellow]")
            return self.output_path

        md = self._build_markdown(rows)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.output_path.write_text(md, encoding="utf-8")

        console.print(f"  比較レポート生成: [cyan]{self.output_path}[/cyan]  ({len(rows)} 実験)")
        return self.output_path
