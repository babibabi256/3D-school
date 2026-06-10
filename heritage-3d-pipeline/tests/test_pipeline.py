"""
test_pipeline.py — ダミー画像10枚でパイプライン全ステップをテストする

各ステップの実際のCOLMAP/GS実行はモック化し、
ファイル入出力・設定解析・データ変換ロジックのみを検証する。

Usage:
    python -m pytest tests/test_pipeline.py -v
    # または
    python tests/test_pipeline.py
"""

import json
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

# src を import パスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def make_dummy_images(directory: Path, count: int = 10, size: tuple = (640, 480)):
    """ダミーのJPEG画像を生成する"""
    directory.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image
    except ImportError:
        # Pillow がなければ OpenCV で代用
        import cv2
        for i in range(count):
            img = np.random.randint(50, 200, (*size[::-1], 3), dtype=np.uint8)
            cv2.imwrite(str(directory / f"image_{i:03d}.jpg"), img)
        return

    for i in range(count):
        arr = np.random.randint(50, 200, (*size[::-1], 3), dtype=np.uint8)
        img = Image.fromarray(arr, "RGB")
        img.save(directory / f"image_{i:03d}.jpg", quality=85)


# ==============================================================
# テストケース
# ==============================================================

class TestCleaning(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.config = {
            "project_name": "test",
            "input_dir": str(self.tmpdir / "input"),
            "output_dir": str(self.tmpdir / "output"),
            "cleansing": {
                "enabled": True,
                "blur_threshold": 0.0,   # ゼロにして全画像を通過させる
                "duplicate_threshold": 0.95,
                "exposure_min": 0,
                "exposure_max": 255,
                "remove_background": False,
                "generate_mask": False,
            },
        }
        make_dummy_images(Path(self.config["input_dir"]), count=10)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_cleansing_runs_and_outputs_images(self):
        from cleansing.cleaner import ImageCleaner
        cleaner = ImageCleaner(self.config)
        cleaner.run()
        output = Path(self.config["output_dir"]) / "cleansed"
        images = list(output.glob("*.jpg"))
        self.assertGreater(len(images), 0, "クレンジング後の画像が0枚です")
        print("  cleansing OK")


class TestColmapRunner(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.config = {
            "project_name": "test",
            "input_dir": str(self.tmpdir / "input"),
            "output_dir": str(self.tmpdir / "output"),
            "colmap": {
                "quality": "medium",
                "matcher": "exhaustive",
                "camera_model": "SIMPLE_RADIAL",
                "use_gpu": False,
                "vocab_tree_path": "",
            },
        }
        make_dummy_images(Path(self.config["input_dir"]), count=10)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("subprocess.run")
    def test_colmap_quality_and_matcher(self, mock_run):
        """quality=medium が max_image_size=2500 に変換されることを確認"""
        mock_run.return_value = MagicMock(returncode=0)
        from colmap.runner import ColmapRunner
        runner = ColmapRunner(self.config)
        self.assertEqual(runner.max_image_size, 2500)
        self.assertEqual(runner.matcher, "exhaustive")
        print("  colmap quality/matcher config OK")

    @patch("subprocess.run")
    def test_gs_dataset_structure(self, mock_run):
        """
        COLMAP 後に gs_dataset/images/ と gs_dataset/sparse/0/ が
        生成されることを確認（sparse/0 ダミーファイルで検証）
        """
        mock_run.return_value = MagicMock(returncode=0)
        from colmap.runner import ColmapRunner

        runner = ColmapRunner(self.config)

        # sparse/0 のダミーファイルを先に作成（COLMAP実行をモック）
        sparse0 = Path(self.config["output_dir"]) / "colmap" / "sparse" / "0"
        sparse0.mkdir(parents=True, exist_ok=True)
        (sparse0 / "cameras.bin").write_bytes(b"\x00" * 8)
        (sparse0 / "images.bin").write_bytes(b"\x00" * 8)
        (sparse0 / "points3D.bin").write_bytes(b"\x00" * 8)

        runner._prepare_gs_dataset(Path(self.config["output_dir"]) / "colmap" / "sparse")

        gs_dataset = Path(self.config["output_dir"]) / "gs_dataset"
        self.assertTrue((gs_dataset / "images").exists())
        self.assertTrue((gs_dataset / "sparse" / "0").exists())
        images = list((gs_dataset / "images").glob("*.jpg"))
        self.assertEqual(len(images), 10)
        print("  colmap gs_dataset OK")


class TestGaussianTrainer(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.config = {
            "project_name": "test",
            "input_dir": str(self.tmpdir / "input"),
            "output_dir": str(self.tmpdir / "output"),
            "colmap": {"quality": "low"},
            "gaussian": {
                "iterations": 1000,
                "sh_degree": 1,
                "densify_until_iter": 500,
                "densify_grad_threshold": 0.0002,
                "lambda_dssim": 0.2,
            },
        }

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("subprocess.run")
    def test_gaussian_uses_gs_dataset_and_quality(self, mock_run):
        """quality=low → resolution=4、ソースが gs_dataset であることを確認"""
        mock_run.return_value = MagicMock(returncode=0)
        from gaussian.trainer import GaussianTrainer

        # gs_dataset を事前作成
        gs_dataset = Path(self.config["output_dir"]) / "gs_dataset"
        gs_dataset.mkdir(parents=True, exist_ok=True)

        trainer = GaussianTrainer(self.config)
        self.assertEqual(trainer.resolution, 4)
        self.assertEqual(trainer.source_dir, gs_dataset)
        print("  gaussian quality/source OK")

    @patch("subprocess.run")
    def test_gaussian_raises_when_no_gs_dataset(self, mock_run):
        """gs_dataset がない場合は FileNotFoundError を送出することを確認"""
        from gaussian.trainer import GaussianTrainer
        trainer = GaussianTrainer(self.config)
        with self.assertRaises(FileNotFoundError):
            trainer.run()
        print("  gaussian error handling OK")


class TestEvaluator(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.config = {
            "project_name": "test",
            "output_dir": str(self.tmpdir / "output"),
            "evaluation": {"enabled": True, "metrics": ["psnr", "ssim"]},
        }
        # ダミーのレンダリング画像と GT 画像を作成
        renders_dir = Path(self.config["output_dir"]) / "gaussian" / "train" / "ours_30000" / "renders"
        gt_dir = Path(self.config["output_dir"]) / "cleansed"
        renders_dir.mkdir(parents=True, exist_ok=True)
        gt_dir.mkdir(parents=True, exist_ok=True)

        try:
            from PIL import Image
            for i in range(5):
                arr = np.full((64, 64, 3), 128, dtype=np.uint8)
                Image.fromarray(arr).save(renders_dir / f"image_{i:03d}.jpg")
                Image.fromarray(arr).save(gt_dir / f"image_{i:03d}.jpg")
        except ImportError:
            import cv2
            for i in range(5):
                arr = np.full((64, 64, 3), 128, dtype=np.uint8)
                cv2.imwrite(str(renders_dir / f"image_{i:03d}.jpg"), arr)
                cv2.imwrite(str(gt_dir / f"image_{i:03d}.jpg"), arr)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_evaluator_produces_metrics_json(self):
        from evaluation.evaluator import Evaluator
        evaluator = Evaluator(self.config)
        evaluator.run()
        metrics_path = Path(self.config["output_dir"]) / "evaluation" / "metrics.json"
        self.assertTrue(metrics_path.exists())
        with open(metrics_path) as f:
            data = json.load(f)
        self.assertIn("summary", data)
        self.assertGreater(data["summary"]["psnr_mean"], 0)
        print("  evaluation OK")


class TestReportGenerator(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.config = {
            "project_name": "test",
            "output_dir": str(self.tmpdir / "output"),
            "colmap": {"quality": "high"},
            "gaussian": {"iterations": 30000},
            "report": {"enabled": True, "format": "markdown", "output_file": "report.md"},
        }
        # ダミー metrics.json
        eval_dir = Path(self.config["output_dir"]) / "evaluation"
        eval_dir.mkdir(parents=True, exist_ok=True)
        with open(eval_dir / "metrics.json", "w") as f:
            json.dump({"summary": {"psnr_mean": 32.5, "ssim_mean": 0.91, "n_images": 5}}, f)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_report_generated(self):
        from report.generator import ReportGenerator
        generator = ReportGenerator(self.config)
        generator.run()
        report_path = Path(self.config["output_dir"]) / "report.md"
        self.assertTrue(report_path.exists())
        content = report_path.read_text()
        self.assertIn("test", content)
        self.assertIn("32.5", content)
        print("  report OK")


class TestExperimentManager(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.config = {
            "project_name": "test",
            "input_dir": str(self.tmpdir / "input"),
            "output_dir": str(self.tmpdir / "output"),
            "report": {"output_file": "report.md"},
        }

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_experiment_manager_setup_and_save(self):
        import os
        orig_cwd = os.getcwd()
        os.chdir(self.tmpdir)  # results/ をtmpdir配下に作成

        try:
            from experiment.manager import ExperimentManager
            mgr = ExperimentManager(self.config)
            exp_dir = mgr.setup()
            self.assertTrue(exp_dir.exists())
            self.assertTrue((exp_dir / "config.yaml").exists())

            # ダミー成果物
            output_dir = Path(self.config["output_dir"])
            (output_dir / "evaluation").mkdir(parents=True, exist_ok=True)
            with open(output_dir / "evaluation" / "metrics.json", "w") as f:
                json.dump({"summary": {"psnr_mean": 30.0, "ssim_mean": 0.88}}, f)
            (output_dir / "report.md").write_text("# report")

            mgr.save_results({"processing_time": 10}, output_dir)
            self.assertTrue((exp_dir / "experiment.json").exists())
            self.assertTrue((exp_dir / "metrics.json").exists())
            print("  experiment manager OK")
        finally:
            os.chdir(orig_cwd)


# ==============================================================
# メイン
# ==============================================================

if __name__ == "__main__":
    print("=" * 50)
    print(" パイプライン自動テスト（ダミー10枚）")
    print("=" * 50)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in [
        TestCleaning,
        TestColmapRunner,
        TestGaussianTrainer,
        TestEvaluator,
        TestReportGenerator,
        TestExperimentManager,
    ]:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 50)
    if result.wasSuccessful():
        print(" 全テスト通過")
    else:
        print(f" 失敗: {len(result.failures)} / エラー: {len(result.errors)}")
    print("=" * 50)
    sys.exit(0 if result.wasSuccessful() else 1)
