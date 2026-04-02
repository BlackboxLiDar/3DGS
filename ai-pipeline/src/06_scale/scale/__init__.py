"""Stage 06: Scale Alignment — relative depth maps → absolute metres.

Two-pass algorithm:
  1. Linear regression between COLMAP sparse PC depths and relative depth values.
  2. Ground plane prior correction so camera height ≈ 1.5 m.
"""

import json
import logging
from pathlib import Path

import cv2
import numpy as np

from .align import (
    ScaleAlignmentError,
    backproject_pixels,
    collect_depth_pairs,
    compute_ground_correction,
    fit_ground_plane,
    fit_scale_shift,
    load_sparse_points,
    orient_normal_toward_cameras,
    road_pixel_coords,
)

logger = logging.getLogger(__name__)


def run(context):
    """Stage 06 entry point.

    Reads:
        context["artifacts"]["depth_maps"]         — dir of .npy (0-1)
        context["artifacts"]["sparse_ply"]         — sparse.ply
        context["artifacts"]["poses"]              — poses.npy (M,4,4) c2w
        context["artifacts"]["intrinsics"]         — intrinsics.json
        context["artifacts"]["registered_frames"]  — registered_frames.json

    Writes:
        context["artifacts"]["scaled_depth_maps"]  — dir of .npy (metres)
    """
    # ── paths ──────────────────────────────────────────────────────────
    depth_dir = Path(context["artifacts"]["depth_maps"])
    sparse_ply = Path(context["artifacts"]["sparse_ply"])
    poses_path = Path(context["artifacts"]["poses"])
    intrinsics_path = Path(context["artifacts"]["intrinsics"])
    reg_path = Path(context["artifacts"]["registered_frames"])

    out_root = Path(context["out_root"])
    workspace = out_root / "06_scale"
    scaled_dir = workspace / "scaled_depth_maps"
    scaled_dir.mkdir(parents=True, exist_ok=True)

    # ── load inputs ────────────────────────────────────────────────────
    poses = np.load(poses_path)                       # (M, 4, 4)
    with open(intrinsics_path) as f:
        intrinsics = json.load(f)
    with open(reg_path) as f:
        reg_frames = json.load(f)["frames"]
    points_world = load_sparse_points(sparse_ply)

    logger.info(
        "Stage 06 starting: %d sparse pts, %d registered frames, depth from %s",
        len(points_world), len(reg_frames), depth_dir,
    )

    # ── Pass 1: linear regression ──────────────────────────────────────
    rel_depths, colmap_depths = collect_depth_pairs(
        points_world, depth_dir, poses, reg_frames, intrinsics,
    )
    logger.info("Collected %d depth pairs for regression.", len(rel_depths))

    scale, shift = fit_scale_shift(rel_depths, colmap_depths)

    # ── Pass 2: ground plane prior ─────────────────────────────────────
    fx, fy = intrinsics["fx"], intrinsics["fy"]
    cx, cy = intrinsics["cx"], intrinsics["cy"]
    h, w = intrinsics["height"], intrinsics["width"]

    road_vu = road_pixel_coords(h, w)
    road_pts_list = []
    step = max(1, len(reg_frames) // 20)  # use ~20 frames
    for i in range(0, len(reg_frames), step):
        stem = Path(reg_frames[i]).stem
        npy = depth_dir / f"{stem}.npy"
        if not npy.exists():
            continue
        rel = np.load(npy)
        scaled = scale * rel + shift
        pts = backproject_pixels(road_vu, scaled, poses[i], fx, fy, cx, cy)
        road_pts_list.append(pts)

    correction = 1.0
    if road_pts_list:
        road_pts = np.concatenate(road_pts_list)
        try:
            normal, d = fit_ground_plane(road_pts)
            normal, d = orient_normal_toward_cameras(normal, d, poses)
            correction = compute_ground_correction(poses, normal, d)
        except ScaleAlignmentError as e:
            logger.warning("Ground plane fit failed — skipping Pass 2: %s", e)

    # ── Apply to all depth maps ────────────────────────────────────────
    all_npys = sorted(depth_dir.glob("*.npy"))
    vis_dir = workspace / "scaled_depth_vis"
    vis_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Scaling %d depth maps (scale=%.4f shift=%.4f k=%.4f) ...",
                len(all_npys), scale, shift, correction)

    MAX_VIS_DEPTH = 50.0  # metres — colormap ceiling
    all_medians = []

    for idx, npy in enumerate(all_npys):
        rel = np.load(npy)
        absolute = correction * (scale * rel + shift)
        absolute = np.clip(absolute, 0, None).astype(np.float32)
        np.save(scaled_dir / npy.name, absolute)

        # visualisation: 0-50 m → 0-255, TURBO colormap
        vis_u8 = (absolute / MAX_VIS_DEPTH * 255).clip(0, 255).astype(np.uint8)
        colored = cv2.applyColorMap(vis_u8, cv2.COLORMAP_TURBO)
        cv2.imwrite(str(vis_dir / (npy.stem + ".png")), colored)

        positive = absolute[absolute > 0]
        if len(positive) > 0:
            all_medians.append(float(np.median(positive)))

        if (idx + 1) % 50 == 0 or (idx + 1) == len(all_npys):
            logger.info("  scaled %d / %d", idx + 1, len(all_npys))

    # ── summary statistics ─────────────────────────────────────────────
    if all_medians:
        med_arr = np.array(all_medians)
        logger.info(
            "Depth statistics (metres): "
            "median=%.2f  min_frame_median=%.2f  max_frame_median=%.2f",
            float(np.median(med_arr)), float(med_arr.min()), float(med_arr.max()),
        )

    # ── artifacts ──────────────────────────────────────────────────────
    context["artifacts"]["scaled_depth_maps"] = str(scaled_dir)
    context["artifacts"]["scaled_depth_vis"] = str(vis_dir)

    logger.info("Stage 06 complete: scaled depth maps -> %s, vis -> %s",
                scaled_dir, vis_dir)
    return context
