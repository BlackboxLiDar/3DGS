"""Prepare COLMAP-compatible directory structure for gaussian-splatting training."""

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


def prepare_scene_dir(
    scene_dir: Path,
    images_dir: Path,
    masks_dir: Path,
    colmap_model_dir: Path,
    filtered_ply: Path,
) -> Path:
    """Create directory structure expected by gaussian-splatting.

    Layout::

        scene_dir/
        ├── images/          → symlink to images_dir
        ├── masks/           → symlink to masks_dir
        └── sparse/0/
            ├── cameras.bin  (from COLMAP)
            ├── images.bin   (from COLMAP)
            └── points3D.ply (our filtered dense PC)
    """
    scene_dir.mkdir(parents=True, exist_ok=True)

    # Symlink images
    img_link = scene_dir / "images"
    if img_link.exists():
        img_link.unlink() if img_link.is_symlink() else shutil.rmtree(img_link)
    img_link.symlink_to(images_dir.resolve())
    logger.info("  images -> %s", images_dir)

    # Symlink masks
    mask_link = scene_dir / "masks"
    if mask_link.exists():
        mask_link.unlink() if mask_link.is_symlink() else shutil.rmtree(mask_link)
    mask_link.symlink_to(masks_dir.resolve())
    logger.info("  masks -> %s", masks_dir)

    # Copy COLMAP model (cameras + images only) and add our point cloud
    sparse_dir = scene_dir / "sparse" / "0"
    sparse_dir.mkdir(parents=True, exist_ok=True)

    for name in ["cameras.bin", "cameras.txt", "images.bin", "images.txt"]:
        src = colmap_model_dir / name
        if src.exists():
            shutil.copy2(src, sparse_dir / name)
            logger.info("  copied %s", name)

    # Use our filtered dense PC as the initial point cloud
    dst_ply = sparse_dir / "points3D.ply"
    shutil.copy2(filtered_ply, dst_ply)
    logger.info("  points3D.ply <- %s", filtered_ply)

    # Remove points3D.bin/.txt if present (force PLY loading)
    for ext in [".bin", ".txt"]:
        p = sparse_dir / f"points3D{ext}"
        if p.exists():
            p.unlink()

    logger.info("Scene directory ready: %s", scene_dir)
    return scene_dir
