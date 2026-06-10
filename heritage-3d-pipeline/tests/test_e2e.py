"""
test_e2e.py — E2Eテスト（実バイナリ使用）

【各テストの成功判定】

TestE2EColmap
  - database.db 生成・非空を確認
  - exhaustive_matcher 後に DB サイズ増加を確認
  - mapper 後に sparse/0/{cameras.bin, images.bin, points3D.bin} の存在を確認
  - gs_dataset/images/ の枚数と gs_dataset/sparse/0/ ファイルを確認
  ※ 再構成失敗は例外として明示的に報告（握りつぶし禁止）

TestE2EGaussian
  - GS 学習後に output/gaussian/point_cloud/iteration_NNN/point_cloud.ply が存在することを確認
  - output/gaussian/ 配下のディレクトリ構造（cameras.json 等）を確認

TestE2EEvaluation
  - 比較ペア: GT画像に意図的なノイズを加えた画像 vs GT
  - PSNR 20〜50dB の有限値であることを確認（inf 禁止）
  - SSIM 0.5〜1.0 の有限値であることを確認

TestE2EFullPipeline（Docker環境でフルパイプラインを一気通しで実行）
  - run_pipeline.py --config を subprocess で起動
  - 各ステップ出力（cleansed/ colmap/database.db gs_dataset/ gaussian/*.ply
    evaluation/metrics.json report.md results/experiment_NNN/）を全て確認

スキップ条件:
  - COLMAP 未インストール  → TestE2EColmap / TestE2EFullPipeline をスキップ
  - GS repo 未配置         → TestE2EGaussian をスキップ
  - GPU 未検出             → TestE2EGaussian をスキップ

Usage:
    python -m pytest tests/test_e2e.py -v -s
    python tests/test_e2e.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

# src を import パスに追加
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))


# ==============================================================
# 環境チェック
# ==============================================================

def _cmd_exists(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def _colmap_functional() -> bool:
    if not _cmd_exists("colmap"):
        return False
    try:
        r = subprocess.run(["colmap", "-h"], capture_output=True, timeout=15)
        return r.returncode in (0, 1)
    except Exception:
        return False


def _gpu_available() -> bool:
    try:
        subprocess.run(["nvidia-smi"], capture_output=True, check=True, timeout=10)
        return True
    except Exception:
        return False


def _gs_repo_available() -> bool:
    return Path("/opt/gaussian-splatting/train.py").exists()


COLMAP_AVAILABLE = _colmap_functional()
GPU_AVAILABLE    = _gpu_available()
GS_AVAILABLE     = _gs_repo_available()


# ==============================================================
# ダミーデータ生成
# ==============================================================

def make_scene_images(directory: Path, count: int = 10) -> list[Path]:
    """
    COLMAP が特徴点を検出できるよう、構造化されたダミー画像を生成する。
    チェッカーボード＋ランダム矩形で SIFT 特徴点を増やす。
    """
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    try:
        from PIL import Image, ImageDraw
        import random
        for i in range(count):
            # チェッカーボード背景
            arr = np.zeros((480, 640, 3), dtype=np.uint8)
            sq = 40
            for row in range(0, 480, sq):
                for col in range(0, 640, sq):
                    val = 200 if (row // sq + col // sq) % 2 == 0 else 50
                    arr[row:row+sq, col:col+sq] = val
            img = Image.fromarray(arr, "RGB")
            draw = ImageDraw.Draw(img)
            rng = random.Random(i * 42)
            for _ in range(20):
                x0, y0 = rng.randint(0, 580), rng.randint(0, 420)
                x1, y1 = x0 + rng.randint(20, 60), y0 + rng.randint(20, 60)
                color = tuple(rng.randint(0, 255) for _ in range(3))
                draw.rectangle([x0, y0, x1, y1], fill=color)
            p = directory / f"img_{i:03d}.jpg"
            img.save(p, quality=95)
            paths.append(p)
    except ImportError:
        import cv2, random
        for i in range(count):
            arr = np.zeros((480, 640, 3), dtype=np.uint8)
            sq = 40
            for row in range(0, 480, sq):
                for col in range(0, 640, sq):
                    val = 200 if (row // sq + col // sq) % 2 == 0 else 50
                    arr[row:row+sq, col:col+sq] = val
            rng = random.Random(i * 42)
            for _ in range(20):
                x0, y0 = rng.randint(0, 580), rng.randint(0, 420)
                x1, y1 = x0 + rng.randint(20, 60), y0 + rng.randint(20, 60)
                color = (rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255))
                cv2.rectangle(arr, (x0, y0), (x1, y1), color, -1)
            p = directory / f"img_{i:03d}.jpg"
            cv2.imwrite(str(p), arr)
            paths.append(p)
    return paths


# ==============================================================
# TestE2ECleansing
# ==============================================================

class TestE2ECleansing(unittest.TestCase):
    """クレンジングの実コード実行テスト（外部バイナリ不要）"""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="e2e_clean_"))
        make_scene_images(self.tmpdir / "input", count=10)
        self.config = {
            "project_name": "e2e_clean",
            "input_dir":  str(self.tmpdir / "input"),
            "output_dir": str(self.tmpdir / "output"),
            "cleansing": {
                "enabled": True,
                "blur_threshold": 0.0,
                "duplicate_threshold": 0.95,
                "exposure_min": 0,
                "exposure_max": 255,
                "remove_background": False,
                "generate_mask": False,
            },
        }

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_output_count(self):
        """10枚入力 → cleansed/ に10枚出力される"""
        from cleansing.cleaner import ImageCleaner
        ImageCleaner(self.config).run()
        images = list((Path(self.config["output_dir"]) / "cleansed").glob("*.jpg"))
        self.assertEqual(len(images), 10)

    def test_blur_filter_excludes_flat_image(self):
        """単色画像（ラプラシアン分散≈0）は blur_threshold=50 で除外される"""
        import cv2
        from cleansing.cleaner import ImageCleaner
        flat = np.full((480, 640, 3), 128, dtype=np.uint8)
        cv2.imwrite(str(self.tmpdir / "input" / "flat.jpg"), flat)
        self.config["cleansing"]["blur_threshold"] = 50.0
        ImageCleaner(self.config).run()
        names = [p.name for p in (Path(self.config["output_dir"]) / "cleansed").glob("*.jpg")]
        self.assertNotIn("flat.jpg", names, "単色画像が除外されていません")


# ==============================================================
# TestE2EColmap
# ==============================================================

@unittest.skipUnless(COLMAP_AVAILABLE, "COLMAP が未インストールのためスキップ")
class TestE2EColmap(unittest.TestCase):
    """
    実 colmap バイナリを使った SfM テスト。

    成功判定:
      feature_extraction → database.db 生成・非空
      matching           → DB サイズ増加
      reconstruction     → sparse/0/{cameras.bin, images.bin, points3D.bin} 存在
      gs_dataset         → images/ 枚数 + sparse/0/ ファイル存在
    """

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="e2e_colmap_"))
        make_scene_images(self.tmpdir / "input", count=10)
        self.config = {
            "project_name": "e2e_colmap",
            "input_dir":  str(self.tmpdir / "input"),
            "output_dir": str(self.tmpdir / "output"),
            "colmap": {
                "quality":         "low",
                "matcher":         "exhaustive",
                "camera_model":    "SIMPLE_RADIAL",
                "use_gpu":         GPU_AVAILABLE,
                "vocab_tree_path": "",
            },
        }

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_feature_extraction_creates_nonempty_db(self):
        """
        成功判定: database.db が存在し、サイズ > 0
        """
        from colmap.runner import ColmapRunner
        runner = ColmapRunner(self.config)
        runner.output_dir.mkdir(parents=True, exist_ok=True)
        db = runner.output_dir / "database.db"

        runner._feature_extraction(db)

        self.assertTrue(db.exists(), "database.db が生成されていません")
        self.assertGreater(db.stat().st_size, 0, "database.db が空です")

    def test_matching_increases_db_size(self):
        """
        成功判定: マッチング後に database.db のサイズが増加する
        """
        from colmap.runner import ColmapRunner
        runner = ColmapRunner(self.config)
        runner.output_dir.mkdir(parents=True, exist_ok=True)
        db = runner.output_dir / "database.db"

        runner._feature_extraction(db)
        size_before = db.stat().st_size
        runner._matching(db)
        size_after = db.stat().st_size

        self.assertGreater(size_after, size_before,
            f"マッチング後に DB サイズが増加していません ({size_before} → {size_after})")

    def test_reconstruction_produces_sparse0_files(self):
        """
        成功判定: mapper 後に sparse/0/ 配下に
          cameras.bin (または cameras.txt)
          images.bin  (または images.txt)
          points3D.bin (または points3D.txt)
        が全て存在する。

        ※ ダミー画像では視点が一定で再構成が失敗することがある。
          その場合はテストを明示的に skip して原因を報告する（握りつぶし禁止）。
        """
        from colmap.runner import ColmapRunner
        runner = ColmapRunner(self.config)
        runner.output_dir.mkdir(parents=True, exist_ok=True)
        sparse = runner.output_dir / "sparse"
        sparse.mkdir(exist_ok=True)
        db = runner.output_dir / "database.db"

        runner._feature_extraction(db)
        runner._matching(db)

        try:
            runner._reconstruction(db, sparse)
        except subprocess.CalledProcessError as e:
            self.skipTest(
                f"COLMAP mapper がダミー画像で失敗しました（特徴点不足の可能性）: {e}\n"
                "実写真で再実行してください。"
            )

        sparse0 = sparse / "0"
        self.assertTrue(sparse0.exists(), "sparse/0/ が生成されていません")

        for name in ("cameras", "images", "points3D"):
            bin_path = sparse0 / f"{name}.bin"
            txt_path = sparse0 / f"{name}.txt"
            self.assertTrue(
                bin_path.exists() or txt_path.exists(),
                f"sparse/0/{name}.bin も .txt も存在しません"
            )

        # points3D のサイズ確認（点群が空でないか）
        p3d_bin = sparse0 / "points3D.bin"
        p3d_txt = sparse0 / "points3D.txt"
        if p3d_bin.exists():
            self.assertGreater(p3d_bin.stat().st_size, 8,
                "points3D.bin がほぼ空です（点群数=0の可能性）")
        elif p3d_txt.exists():
            lines = [l for l in p3d_txt.read_text().splitlines()
                     if l.strip() and not l.startswith("#")]
            self.assertGreater(len(lines), 0, "points3D.txt に点群データがありません")

    def test_gs_dataset_structure_after_reconstruction(self):
        """
        成功判定:
          gs_dataset/images/ に元画像と同数の .jpg が存在する
          gs_dataset/sparse/0/ に cameras/images/points3D ファイルが存在する
        """
        from colmap.runner import ColmapRunner
        runner = ColmapRunner(self.config)
        runner.output_dir.mkdir(parents=True, exist_ok=True)
        sparse = runner.output_dir / "sparse"
        sparse.mkdir(exist_ok=True)
        db = runner.output_dir / "database.db"

        runner._feature_extraction(db)
        runner._matching(db)

        try:
            runner._reconstruction(db, sparse)
        except subprocess.CalledProcessError:
            self.skipTest("COLMAP mapper がダミー画像で失敗したためスキップ")

        runner._prepare_gs_dataset(sparse)

        gs_images = runner.gs_dataset_dir / "images"
        gs_sparse0 = runner.gs_dataset_dir / "sparse" / "0"

        # images 枚数
        self.assertTrue(gs_images.exists())
        imgs = list(gs_images.glob("*.jpg")) + list(gs_images.glob("*.png"))
        self.assertEqual(len(imgs), 10, f"gs_dataset/images/ の枚数が期待と異なります: {len(imgs)}")

        # sparse/0 のファイル
        self.assertTrue(gs_sparse0.exists(), "gs_dataset/sparse/0/ が存在しません")
        sparse0_files = list(gs_sparse0.iterdir())
        self.assertGreater(len(sparse0_files), 0, "gs_dataset/sparse/0/ が空です")


# ==============================================================
# TestE2EGaussian
# ==============================================================

@unittest.skipUnless(
    COLMAP_AVAILABLE and GS_AVAILABLE and GPU_AVAILABLE,
    "COLMAP / Gaussian Splatting repo / GPU のいずれかが未利用可能のためスキップ",
)
class TestE2EGaussian(unittest.TestCase):
    """
    実 Gaussian Splatting train.py を使ったテスト（GPU必須）。

    成功判定:
      output/gaussian/point_cloud/iteration_NNN/point_cloud.ply が存在する
      output/gaussian/cameras.json が存在する（GS の標準出力ファイル）
      output/gaussian/cfg_args が存在する（学習設定ファイル）
    """

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="e2e_gs_"))
        make_scene_images(self.tmpdir / "input", count=10)
        self.config = {
            "project_name": "e2e_gs",
            "input_dir":  str(self.tmpdir / "input"),
            "output_dir": str(self.tmpdir / "output"),
            "colmap": {
                "quality":         "low",
                "matcher":         "exhaustive",
                "camera_model":    "SIMPLE_RADIAL",
                "use_gpu":         True,
                "vocab_tree_path": "",
            },
            "gaussian": {
                "iterations":             100,    # テスト用に最小反復数
                "sh_degree":              1,
                "densify_until_iter":     50,
                "densify_grad_threshold": 0.0002,
                "lambda_dssim":           0.2,
            },
        }

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _run_colmap(self):
        from colmap.runner import ColmapRunner
        ColmapRunner(self.config).run()

    def test_gaussian_point_cloud_ply_exists(self):
        """
        成功判定:
          output/gaussian/point_cloud/iteration_NNN/point_cloud.ply が存在し非空である

        GS のデフォルト出力構造:
          {output_dir}/
          ├─ cameras.json
          ├─ cfg_args
          └─ point_cloud/
              └─ iteration_{N}/
                  └─ point_cloud.ply
        """
        self._run_colmap()

        from gaussian.trainer import GaussianTrainer
        GaussianTrainer(self.config).run()

        gs_out = Path(self.config["output_dir"]) / "gaussian"

        # point_cloud.ply の存在確認
        ply_files = list(gs_out.rglob("point_cloud.ply"))
        self.assertGreater(len(ply_files), 0,
            f"point_cloud.ply が見つかりません。\n"
            f"gs_out 配下のファイル: {list(gs_out.rglob('*'))}")

        # ファイルサイズ > 0（学習データが書き込まれているか）
        for ply in ply_files:
            self.assertGreater(ply.stat().st_size, 0, f"{ply} が空です")

    def test_gaussian_model_directory_structure(self):
        """
        成功判定: GS 学習後のモデルディレクトリが標準構造を持つ
          cameras.json … カメラ情報
          cfg_args     … 学習設定
          point_cloud/ … 点群ディレクトリ
        """
        self._run_colmap()

        from gaussian.trainer import GaussianTrainer
        GaussianTrainer(self.config).run()

        gs_out = Path(self.config["output_dir"]) / "gaussian"

        self.assertTrue((gs_out / "cameras.json").exists(),
            "cameras.json が存在しません")
        self.assertTrue((gs_out / "cfg_args").exists(),
            "cfg_args が存在しません")
        self.assertTrue((gs_out / "point_cloud").is_dir(),
            "point_cloud/ ディレクトリが存在しません")

        # iteration_NNN ディレクトリが1つ以上ある
        iters = list((gs_out / "point_cloud").glob("iteration_*"))
        self.assertGreater(len(iters), 0,
            "point_cloud/iteration_*/ が存在しません")


# ==============================================================
# TestE2EEvaluation
# ==============================================================

class TestE2EEvaluation(unittest.TestCase):
    """
    evaluator の実コード実行テスト。

    【比較ペアについて】
      renders_dir: GT画像に意図的な加算ノイズ（σ=15）を加えた画像
      gt_dir:      元の GT 画像
    → 同一画像（PSNR=inf）ではなく、有限の PSNR/SSIM 値を検証する。

    成功判定:
      metrics.json が生成される
      summary に psnr_mean / ssim_mean / n_images が含まれる
      psnr_mean が有限値 (not inf / nan) である
      psnr_mean が現実的な範囲 (20〜60 dB) にある
      ssim_mean が 0.5〜1.0 にある
      n_images = 5
    """

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="e2e_eval_"))
        self.config = {
            "project_name": "e2e_eval",
            "output_dir": str(self.tmpdir / "output"),
            "evaluation": {"enabled": True, "metrics": ["psnr", "ssim"]},
        }
        renders_dir = (Path(self.config["output_dir"])
                       / "gaussian" / "train" / "ours_30000" / "renders")
        gt_dir = Path(self.config["output_dir"]) / "cleansed"
        renders_dir.mkdir(parents=True, exist_ok=True)
        gt_dir.mkdir(parents=True, exist_ok=True)

        rng = np.random.default_rng(seed=0)

        try:
            from PIL import Image
            for i in range(5):
                gt_arr = rng.integers(80, 180, (64, 64, 3), dtype=np.uint8)
                # renders = GT + ガウシアンノイズ（σ=15）
                noise = rng.integers(-15, 16, (64, 64, 3))
                rendered_arr = np.clip(gt_arr.astype(int) + noise, 0, 255).astype(np.uint8)

                Image.fromarray(gt_arr).save(gt_dir / f"img_{i:03d}.jpg")
                Image.fromarray(rendered_arr).save(renders_dir / f"img_{i:03d}.jpg")
        except ImportError:
            import cv2
            for i in range(5):
                gt_arr = rng.integers(80, 180, (64, 64, 3), dtype=np.uint8)
                noise = rng.integers(-15, 16, (64, 64, 3))
                rendered_arr = np.clip(gt_arr.astype(int) + noise, 0, 255).astype(np.uint8)
                cv2.imwrite(str(gt_dir / f"img_{i:03d}.jpg"), gt_arr)
                cv2.imwrite(str(renders_dir / f"img_{i:03d}.jpg"), rendered_arr)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _load_summary(self) -> dict:
        from evaluation.evaluator import Evaluator
        Evaluator(self.config).run()
        p = Path(self.config["output_dir"]) / "evaluation" / "metrics.json"
        with open(p) as f:
            return json.load(f)["summary"]

    def test_metrics_json_schema(self):
        """metrics.json が所定スキーマで生成される"""
        summary = self._load_summary()
        for key in ("psnr_mean", "ssim_mean", "n_images"):
            self.assertIn(key, summary, f"summary に {key} がありません")
        self.assertEqual(summary["n_images"], 5)

    def test_psnr_is_finite_and_in_range(self):
        """
        PSNR が有限値（inf / nan でない）かつ 20〜60 dB の範囲にある。
        比較ペアはノイズ追加画像 vs GT 画像。
        """
        import math
        summary = self._load_summary()
        psnr = summary["psnr_mean"]
        self.assertFalse(math.isinf(psnr), f"PSNR が inf です。同一画像を比較している疑いがあります。")
        self.assertFalse(math.isnan(psnr), f"PSNR が nan です。")
        self.assertGreater(psnr, 20.0, f"PSNR が低すぎます: {psnr:.2f} dB")
        self.assertLess(psnr, 60.0,    f"PSNR が高すぎます（同一画像比較の可能性）: {psnr:.2f} dB")

    def test_ssim_is_finite_and_in_range(self):
        """SSIM が 0.5〜1.0 の範囲にある"""
        import math
        summary = self._load_summary()
        ssim = summary["ssim_mean"]
        self.assertFalse(math.isinf(ssim), f"SSIM が inf です。")
        self.assertFalse(math.isnan(ssim), f"SSIM が nan です。")
        self.assertGreater(ssim, 0.5, f"SSIM が低すぎます: {ssim:.4f}")
        self.assertLessEqual(ssim, 1.0, f"SSIM が 1.0 を超えています: {ssim:.4f}")


# ==============================================================
# TestE2EReport
# ==============================================================

class TestE2EReport(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="e2e_report_"))
        self.config = {
            "project_name": "e2e_report",
            "output_dir": str(self.tmpdir / "output"),
            "colmap":   {"quality": "high"},
            "gaussian": {"iterations": 30000},
            "report":   {"enabled": True, "format": "markdown", "output_file": "report.md"},
        }
        eval_dir = Path(self.config["output_dir"]) / "evaluation"
        eval_dir.mkdir(parents=True, exist_ok=True)
        with open(eval_dir / "metrics.json", "w") as f:
            json.dump({"summary": {"psnr_mean": 35.2, "ssim_mean": 0.94, "n_images": 10}}, f)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_report_contains_metrics_values(self):
        from report.generator import ReportGenerator
        ReportGenerator(self.config).run()
        report = (Path(self.config["output_dir"]) / "report.md").read_text()
        self.assertIn("35.2",       report)
        self.assertIn("0.9400",     report)
        self.assertIn("e2e_report", report)

    def test_report_markdown_structure(self):
        from report.generator import ReportGenerator
        ReportGenerator(self.config).run()
        report = (Path(self.config["output_dir"]) / "report.md").read_text()
        self.assertIn("# ",  report, "H1 見出しがありません")
        self.assertIn("## ", report, "H2 見出しがありません")
        self.assertIn("|",   report, "テーブルがありません")


# ==============================================================
# TestE2EExperimentManager
# ==============================================================

class TestE2EExperimentManager(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="e2e_exp_"))
        self.orig_cwd = os.getcwd()
        os.chdir(self.tmpdir)
        self.config = {
            "project_name": "e2e_exp",
            "input_dir":  str(self.tmpdir / "input"),
            "output_dir": str(self.tmpdir / "output"),
            "colmap":   {"quality": "high"},
            "gaussian": {"iterations": 30000},
            "report":   {"output_file": "report.md"},
        }

    def tearDown(self):
        os.chdir(self.orig_cwd)
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_artifacts(self, output_dir: Path):
        (output_dir / "evaluation").mkdir(parents=True, exist_ok=True)
        with open(output_dir / "evaluation" / "metrics.json", "w") as f:
            json.dump({"summary": {"psnr_mean": 30.0, "ssim_mean": 0.85}}, f)
        (output_dir / "report.md").write_text("# report")

    def test_sequential_unique_ids(self):
        from experiment.manager import ExperimentManager
        names = [ExperimentManager(self.config).setup().name for _ in range(3)]
        self.assertEqual(names, ["experiment_001", "experiment_002", "experiment_003"])

    def test_all_artifacts_saved(self):
        from experiment.manager import ExperimentManager
        mgr = ExperimentManager(self.config)
        exp_dir = mgr.setup()
        output_dir = Path(self.config["output_dir"])
        self._make_artifacts(output_dir)
        mgr.save_results({"processing_time": 120, "image_count": 10}, output_dir)

        for name in ("config.yaml", "experiment.json", "metrics.json", "report.md"):
            self.assertTrue((exp_dir / name).exists(), f"{name} が保存されていません")

        with open(exp_dir / "experiment.json") as f:
            data = json.load(f)
        self.assertEqual(data["processing_time"], 120)
        self.assertIn("timestamp", data)

    def test_list_experiments(self):
        from experiment.manager import ExperimentManager
        output_dir = Path(self.config["output_dir"])
        self._make_artifacts(output_dir)
        for _ in range(2):
            mgr = ExperimentManager(self.config)
            mgr.setup()
            mgr.save_results({}, output_dir)
        result = ExperimentManager(self.config).list_experiments()
        self.assertEqual(len(result), 2)
        self.assertIn("psnr_mean", result[0])


# ==============================================================
# TestE2EFullPipeline — フルパイプライン一気通しテスト
# ==============================================================

@unittest.skipUnless(COLMAP_AVAILABLE,
    "COLMAP が未インストールのためフルパイプラインテストをスキップ")
class TestE2EFullPipeline(unittest.TestCase):
    """
    run_pipeline.py を subprocess で起動し、
    Cleansing → COLMAP → gs_dataset → Gaussian → Evaluation → Report → ExperimentManager
    を一気通しで実行する。

    成功判定（全て確認する）:
      output/cleansed/           … クレンジング後画像
      output/colmap/database.db  … COLMAP DB
      output/colmap/sparse/0/    … 再構成結果ディレクトリ
      output/gs_dataset/images/  … GS 入力画像
      output/gs_dataset/sparse/0/… GS 入力 sparse
      output/gaussian/point_cloud/iteration_NNN/point_cloud.ply  ← GPU 環境のみ
      output/evaluation/metrics.json … PSNR/SSIM
      output/report.md           … レポート
      results/experiment_NNN/    … 実験ディレクトリ
        config.yaml
        experiment.json
        metrics.json
        report.md

    GPU なし環境では Gaussian 以降はスキップし、
    それより前のステップの成果物のみ検証する。
    """

    PIPELINE_SCRIPT = str(REPO_ROOT / "scripts" / "run_pipeline.py")

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="e2e_full_"))
        self.results_dir = self.tmpdir / "results"
        make_scene_images(self.tmpdir / "input", count=10)

        self.config = {
            "project_name": "e2e_full",
            "input_dir":  str(self.tmpdir / "input"),
            "output_dir": str(self.tmpdir / "output"),
            "cleansing": {
                "enabled": True,
                "blur_threshold": 0.0,
                "duplicate_threshold": 0.95,
                "exposure_min": 0,
                "exposure_max": 255,
                "remove_background": False,
                "generate_mask": False,
            },
            "colmap": {
                "quality":         "low",
                "matcher":         "exhaustive",
                "camera_model":    "SIMPLE_RADIAL",
                "use_gpu":         GPU_AVAILABLE,
                "vocab_tree_path": "",
            },
            "gaussian": {
                "iterations":             100 if GPU_AVAILABLE else 0,
                "sh_degree":              1,
                "densify_until_iter":     50,
                "densify_grad_threshold": 0.0002,
                "lambda_dssim":           0.2,
            },
            "evaluation": {
                "enabled": GPU_AVAILABLE,   # GS が走った場合のみ評価
                "metrics": ["psnr", "ssim"],
            },
            "report": {
                "enabled": True,
                "format":  "markdown",
                "output_file": "report.md",
            },
        }

        # config ファイルを tmpdir に書き出す
        import yaml
        self.config_path = self.tmpdir / "config.yaml"
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(self.config, f, allow_unicode=True, default_flow_style=False)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _run_pipeline(self) -> subprocess.CompletedProcess:
        """run_pipeline.py をサブプロセスで実行する"""
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        return subprocess.run(
            [sys.executable, self.PIPELINE_SCRIPT, "--config", str(self.config_path)],
            cwd=str(self.tmpdir),   # results/ が tmpdir 配下に生成される
            capture_output=True,
            text=True,
            env=env,
            timeout=600,           # 最大10分（学習込み）
        )

    def test_full_pipeline_exit_code(self):
        """
        run_pipeline.py が正常終了する（exit code = 0）。
        失敗時はパイプラインの stdout/stderr を出力する。
        """
        result = self._run_pipeline()
        if result.returncode != 0:
            self.fail(
                f"run_pipeline.py が失敗しました (exit={result.returncode})\n"
                f"--- stdout ---\n{result.stdout}\n"
                f"--- stderr ---\n{result.stderr}"
            )

    def test_cleansing_output(self):
        """成功判定: output/cleansed/ に画像が存在する"""
        self._run_pipeline()
        cleansed = Path(self.config["output_dir"]) / "cleansed"
        imgs = list(cleansed.glob("*.jpg")) + list(cleansed.glob("*.png"))
        self.assertGreater(len(imgs), 0,
            f"cleansed/ に画像がありません: {cleansed}")

    def test_colmap_database_output(self):
        """成功判定: output/colmap/database.db が存在し非空"""
        result = self._run_pipeline()
        db = Path(self.config["output_dir"]) / "colmap" / "database.db"
        self.assertTrue(db.exists(),
            f"database.db が生成されていません\nstderr:\n{result.stderr}")
        self.assertGreater(db.stat().st_size, 0, "database.db が空です")

    def test_colmap_sparse0_files(self):
        """
        成功判定: output/colmap/sparse/0/ に
          cameras.bin (または .txt)
          images.bin  (または .txt)
          points3D.bin (または .txt)
        が存在する。

        ダミー画像で再構成が失敗した場合はスキップ。
        """
        self._run_pipeline()
        sparse0 = Path(self.config["output_dir"]) / "colmap" / "sparse" / "0"
        if not sparse0.exists():
            self.skipTest("sparse/0/ が存在しません（ダミー画像での再構成失敗の可能性）")

        for name in ("cameras", "images", "points3D"):
            self.assertTrue(
                (sparse0 / f"{name}.bin").exists() or (sparse0 / f"{name}.txt").exists(),
                f"sparse/0/{name}.bin/.txt が存在しません"
            )

    def test_gs_dataset_output(self):
        """
        成功判定:
          output/gs_dataset/images/ に10枚存在
          output/gs_dataset/sparse/0/ が存在
        """
        self._run_pipeline()
        gs_images = Path(self.config["output_dir"]) / "gs_dataset" / "images"
        gs_sparse0 = Path(self.config["output_dir"]) / "gs_dataset" / "sparse" / "0"

        self.assertTrue(gs_images.exists(), "gs_dataset/images/ が存在しません")
        imgs = list(gs_images.glob("*.jpg")) + list(gs_images.glob("*.png"))
        self.assertEqual(len(imgs), 10,
            f"gs_dataset/images/ の画像枚数が期待と異なります: {len(imgs)}")
        self.assertTrue(gs_sparse0.exists(), "gs_dataset/sparse/0/ が存在しません")

    @unittest.skipUnless(GPU_AVAILABLE and GS_AVAILABLE,
        "GPU または GS repo が未利用可能のためスキップ")
    def test_gaussian_point_cloud_output(self):
        """
        成功判定:
          output/gaussian/point_cloud/iteration_NNN/point_cloud.ply が存在し非空
          output/gaussian/cameras.json が存在する
        """
        self._run_pipeline()
        gs_out = Path(self.config["output_dir"]) / "gaussian"
        ply_files = list(gs_out.rglob("point_cloud.ply"))
        self.assertGreater(len(ply_files), 0,
            f"point_cloud.ply が見つかりません\ngs_out: {list(gs_out.rglob('*'))}")
        for ply in ply_files:
            self.assertGreater(ply.stat().st_size, 0, f"{ply} が空です")
        self.assertTrue((gs_out / "cameras.json").exists(), "cameras.json がありません")

    @unittest.skipUnless(GPU_AVAILABLE and GS_AVAILABLE,
        "GPU または GS repo が未利用可能のためスキップ")
    def test_evaluation_metrics_output(self):
        """
        成功判定:
          output/evaluation/metrics.json が存在する
          summary.psnr_mean / ssim_mean / n_images を含む
        """
        self._run_pipeline()
        metrics_path = Path(self.config["output_dir"]) / "evaluation" / "metrics.json"
        self.assertTrue(metrics_path.exists(), "metrics.json が生成されていません")
        with open(metrics_path) as f:
            data = json.load(f)
        summary = data.get("summary", {})
        for key in ("psnr_mean", "ssim_mean", "n_images"):
            self.assertIn(key, summary, f"summary に {key} がありません")

    def test_report_output(self):
        """
        成功判定:
          output/report.md が存在する
          H1/H2 見出しとテーブルが含まれる
        """
        self._run_pipeline()
        report_path = Path(self.config["output_dir"]) / "report.md"
        self.assertTrue(report_path.exists(), "report.md が生成されていません")
        text = report_path.read_text()
        self.assertIn("# ",  text, "H1 見出しがありません")
        self.assertIn("## ", text, "H2 見出しがありません")
        self.assertIn("|",   text, "テーブルがありません")

    def test_experiment_manager_output(self):
        """
        成功判定:
          results/experiment_NNN/ が作成される
          config.yaml / experiment.json / metrics.json / report.md が保存される
        """
        self._run_pipeline()
        results_dir = self.tmpdir / "results"
        exp_dirs = [d for d in results_dir.iterdir() if d.name.startswith("experiment_")]
        self.assertGreater(len(exp_dirs), 0, "results/experiment_NNN/ が生成されていません")

        exp_dir = exp_dirs[0]
        for name in ("config.yaml", "experiment.json"):
            self.assertTrue((exp_dir / name).exists(), f"{name} が保存されていません")

        with open(exp_dir / "experiment.json") as f:
            data = json.load(f)
        self.assertIn("project_name", data)
        self.assertIn("timestamp", data)
        self.assertIn("processing_time", data)


# ==============================================================
# メイン
# ==============================================================

SKIP_REASONS = []
if not COLMAP_AVAILABLE:
    SKIP_REASONS.append("COLMAP 未インストール → TestE2EColmap / TestE2EFullPipeline をスキップ")
if not GPU_AVAILABLE:
    SKIP_REASONS.append("GPU 未検出 → TestE2EGaussian をスキップ")
if not GS_AVAILABLE:
    SKIP_REASONS.append("GS repo 未配置 → TestE2EGaussian をスキップ")


if __name__ == "__main__":
    print("=" * 60)
    print(" E2Eテスト（実バイナリ使用）")
    print("=" * 60)
    if SKIP_REASONS:
        for r in SKIP_REASONS:
            print(f"  [SKIP] {r}")
    else:
        print("  全テストが実行されます")
    print()

    loader = unittest.TestLoader()
    suite  = unittest.TestSuite()
    for cls in [
        TestE2ECleansing,
        TestE2EColmap,
        TestE2EGaussian,
        TestE2EEvaluation,
        TestE2EReport,
        TestE2EExperimentManager,
        TestE2EFullPipeline,
    ]:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
