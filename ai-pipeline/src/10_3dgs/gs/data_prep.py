"""Prepare COLMAP-compatible directory structure for gaussian-splatting training."""

import logging
import shutil
import struct
from pathlib import Path

logger = logging.getLogger(__name__)


# COLMAP camera model IDs (from colmap/src/base/camera_models.h)
_CAMERA_MODEL_IDS = {
    "SIMPLE_PINHOLE": 0,
    "PINHOLE": 1,
    "SIMPLE_RADIAL": 2,
    "RADIAL": 3,
    "OPENCV": 4,
}
_CAMERA_MODEL_NAMES = {v: k for k, v in _CAMERA_MODEL_IDS.items()}


def _convert_cameras_txt_to_pinhole(src: Path, dst: Path):
    """Rewrite cameras.txt, converting OPENCV → PINHOLE (drop distortion)."""
    lines_out = []
    converted = False
    with open(src) as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                lines_out.append(line)
                continue
            parts = line.strip().split()
            cam_id, model = parts[0], parts[1]
            if model == "OPENCV":
                w, h = parts[2], parts[3]
                fx, fy, cx, cy = parts[4], parts[5], parts[6], parts[7]
                # Drop k1, k2, p1, p2 (params[4:8])
                lines_out.append(
                    f"{cam_id} PINHOLE {w} {h} {fx} {fy} {cx} {cy}\n"
                )
                converted = True
                logger.info("  cameras.txt: OPENCV -> PINHOLE (dropped distortion)")
            else:
                lines_out.append(line)
    with open(dst, "w") as f:
        f.writelines(lines_out)
    return converted


def _convert_cameras_bin_to_pinhole(src: Path, dst: Path):
    """Rewrite cameras.bin, converting OPENCV → PINHOLE (drop distortion)."""
    with open(src, "rb") as f:
        num_cameras = struct.unpack("<Q", f.read(8))[0]
        cameras = []
        for _ in range(num_cameras):
            cam_id = struct.unpack("<I", f.read(4))[0]
            model_id = struct.unpack("<i", f.read(4))[0]
            width = struct.unpack("<Q", f.read(8))[0]
            height = struct.unpack("<Q", f.read(8))[0]
            model_name = _CAMERA_MODEL_NAMES.get(model_id, f"UNKNOWN({model_id})")

            # Read params based on model
            if model_name == "OPENCV":
                params = struct.unpack("<8d", f.read(64))  # fx,fy,cx,cy,k1,k2,p1,p2
                # Convert to PINHOLE: keep only fx,fy,cx,cy
                cameras.append((cam_id, _CAMERA_MODEL_IDS["PINHOLE"],
                                width, height, params[:4]))
                logger.info("  cameras.bin: OPENCV -> PINHOLE (dropped distortion)")
            elif model_name == "PINHOLE":
                params = struct.unpack("<4d", f.read(32))
                cameras.append((cam_id, model_id, width, height, params))
            elif model_name == "SIMPLE_PINHOLE":
                params = struct.unpack("<3d", f.read(24))
                cameras.append((cam_id, model_id, width, height, params))
            else:
                raise ValueError(f"Unsupported camera model in bin: {model_name}")

    with open(dst, "wb") as f:
        f.write(struct.pack("<Q", num_cameras))
        for cam_id, model_id, width, height, params in cameras:
            f.write(struct.pack("<I", cam_id))
            f.write(struct.pack("<i", model_id))
            f.write(struct.pack("<Q", width))
            f.write(struct.pack("<Q", height))
            for p in params:
                f.write(struct.pack("<d", p))


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
            ├── cameras.bin  (PINHOLE, converted from OPENCV if needed)
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

    # Copy COLMAP model — convert OPENCV → PINHOLE for gaussian-splatting
    sparse_dir = scene_dir / "sparse" / "0"
    sparse_dir.mkdir(parents=True, exist_ok=True)

    # cameras: convert OPENCV → PINHOLE (gaussian-splatting only supports PINHOLE)
    for name, converter in [
        ("cameras.txt", _convert_cameras_txt_to_pinhole),
        ("cameras.bin", _convert_cameras_bin_to_pinhole),
    ]:
        src = colmap_model_dir / name
        if src.exists():
            converter(src, sparse_dir / name)

    # images: copy as-is
    for name in ["images.bin", "images.txt"]:
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
