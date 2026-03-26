"""COLMAP CLI wrapper for Structure-from-Motion reconstruction."""

import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def check_colmap_available():
    """Raise RuntimeError if colmap binary is not found in PATH."""
    if shutil.which("colmap") is None:
        raise RuntimeError(
            "colmap not found in PATH. "
            "Install: brew install colmap (macOS) or sudo apt install colmap (Linux)"
        )


def _run_colmap_cmd(cmd, log_path=None):
    """Run a COLMAP command, log output, raise on failure."""
    logger.info("Running: %s", " ".join(str(c) for c in cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)

    if log_path:
        with open(log_path, "a") as f:
            f.write(f"\n=== {' '.join(str(c) for c in cmd)} ===\n")
            f.write(result.stdout)
            if result.stderr:
                f.write(result.stderr)

    if result.returncode != 0:
        logger.error("COLMAP failed (exit %d):\n%s", result.returncode, result.stderr[-2000:])
        raise subprocess.CalledProcessError(result.returncode, cmd)


def prepare_masks_for_colmap(source_masks_dir, colmap_masks_dir, images_dir):
    """Create symlinks with COLMAP naming convention.

    COLMAP expects mask files named {image_filename}.png
    (e.g., frame_000001.jpg.png), but Stage 03 outputs frame_000001.png.
    """
    colmap_masks_dir = Path(colmap_masks_dir)
    colmap_masks_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for img_path in sorted(Path(images_dir).glob("*.jpg")):
        src_mask = Path(source_masks_dir) / f"{img_path.stem}.png"
        if src_mask.exists():
            dst = colmap_masks_dir / f"{img_path.name}.png"
            if dst.exists() or dst.is_symlink():
                dst.unlink()
            dst.symlink_to(src_mask.resolve())
            count += 1

    logger.info("Prepared %d mask symlinks in %s", count, colmap_masks_dir)


def run_feature_extractor(db_path, image_path, mask_path, use_gpu=False, log_path=None):
    """Run colmap feature_extractor with mask support."""
    cmd = [
        "colmap", "feature_extractor",
        "--database_path", str(db_path),
        "--image_path", str(image_path),
        "--ImageReader.mask_path", str(mask_path),
        "--ImageReader.single_camera", "1",
        "--ImageReader.camera_model", "PINHOLE",
        "--SiftExtraction.use_gpu", "1" if use_gpu else "0",
        "--SiftExtraction.max_num_features", "8192",
    ]

    try:
        _run_colmap_cmd(cmd, log_path)
    except subprocess.CalledProcessError:
        if use_gpu:
            logger.warning("GPU feature extraction failed, retrying with CPU")
            gpu_idx = cmd.index("--SiftExtraction.use_gpu")
            cmd[gpu_idx + 1] = "0"
            _run_colmap_cmd(cmd, log_path)
        else:
            raise


def run_sequential_matcher(db_path, use_gpu=False, log_path=None):
    """Run colmap sequential_matcher."""
    cmd = [
        "colmap", "sequential_matcher",
        "--database_path", str(db_path),
        "--SequentialMatching.overlap", "10",
        "--SequentialMatching.loop_detection", "0",
        "--SiftMatching.use_gpu", "1" if use_gpu else "0",
    ]

    try:
        _run_colmap_cmd(cmd, log_path)
    except subprocess.CalledProcessError:
        if use_gpu:
            logger.warning("GPU matching failed, retrying with CPU")
            gpu_idx = cmd.index("--SiftMatching.use_gpu")
            cmd[gpu_idx + 1] = "0"
            _run_colmap_cmd(cmd, log_path)
        else:
            raise


def run_mapper(db_path, image_path, output_path, log_path=None):
    """Run colmap mapper (incremental SfM)."""
    output_path = Path(output_path)
    output_path.mkdir(parents=True, exist_ok=True)

    cmd = [
        "colmap", "mapper",
        "--database_path", str(db_path),
        "--image_path", str(image_path),
        "--output_path", str(output_path),
    ]
    _run_colmap_cmd(cmd, log_path)


def run_model_converter_to_text(input_path, output_path, log_path=None):
    """Convert COLMAP binary model to text format."""
    output_path = Path(output_path)
    output_path.mkdir(parents=True, exist_ok=True)

    cmd = [
        "colmap", "model_converter",
        "--input_path", str(input_path),
        "--output_path", str(output_path),
        "--output_type", "TXT",
    ]
    _run_colmap_cmd(cmd, log_path)


def run_model_converter_to_ply(input_path, output_path, log_path=None):
    """Export COLMAP sparse model as PLY point cloud."""
    cmd = [
        "colmap", "model_converter",
        "--input_path", str(input_path),
        "--output_path", str(output_path),
        "--output_type", "PLY",
    ]
    _run_colmap_cmd(cmd, log_path)


def run_colmap_pipeline(images_dir, masks_dir, workspace, use_gpu=False):
    """Run the full COLMAP SfM pipeline.

    Returns path to the best reconstruction directory (sparse/0/).
    """
    workspace = Path(workspace)
    db_path = workspace / "database.db"
    sparse_dir = workspace / "sparse"
    log_path = workspace / "colmap.log"

    # Clear previous database if exists
    if db_path.exists():
        db_path.unlink()

    logger.info("Step 1/5: Feature extraction...")
    run_feature_extractor(db_path, images_dir, masks_dir, use_gpu, log_path)

    logger.info("Step 2/5: Sequential matching...")
    run_sequential_matcher(db_path, use_gpu, log_path)

    logger.info("Step 3/5: Mapper (incremental SfM)...")
    run_mapper(db_path, images_dir, sparse_dir, log_path)

    # Find the best reconstruction (sparse/0 is typically the largest)
    recon_dirs = sorted(sparse_dir.iterdir()) if sparse_dir.exists() else []
    if not recon_dirs:
        raise RuntimeError(
            "COLMAP mapper produced no reconstruction. "
            "Check image quality, feature matches, and mask coverage."
        )

    model_dir = recon_dirs[0]
    if len(recon_dirs) > 1:
        logger.warning(
            "COLMAP produced %d reconstructions. Using %s (largest).",
            len(recon_dirs),
            model_dir,
        )

    logger.info("Step 4/5: Converting model to text...")
    text_dir = workspace / "sparse_text"
    run_model_converter_to_text(model_dir, text_dir, log_path)

    logger.info("Step 5/5: Exporting sparse PLY...")
    sparse_ply = workspace / "sparse.ply"
    run_model_converter_to_ply(model_dir, sparse_ply, log_path)

    return model_dir
