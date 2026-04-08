# Pipeline Evaluation Report

**입력 데이터:** `sample3.tfrecord` (Waymo)  
**실행 출력:** `run_20260402_042652`  
**평가 일자:** 2026-04-08

---

## Stage 02 — Ingest (Frame Extraction)

**상태:** ✅ 정상

### 실행 결과
- Waymo TFRecord에서 프론트 카메라 프레임 추출
- 출력: `02_ingest/images_colmap/` (JPG)
- Waymo 캘리브레이션에서 intrinsics 자동 추출 (fx, fy, cx, cy)

### 주요 파라미터
| 파라미터 | 값 | 비고 |
|---------|-----|------|
| every_n | 1 | 모든 프레임 추출 |
| 출력 포맷 | JPG | frame_XXXXXX_MICROSECONDS.jpg |

### 이슈 및 권장사항
| # | 심각도 | 이슈 | 권장 수정 |
|---|--------|------|-----------|
| 1 | Low | 비디오 입력 시 fps=10 하드코딩 | 향후 config로 분리 고려 |
| 2 | Low | 추출된 프레임 수 검증 없음 | 최소 프레임 수 체크 추가 고려 |

---

## Stage 03 — Segmentation & Tracking

**상태:** ✅ 정상

### 실행 결과
- YOLOv8m-seg + ByteTrack으로 차량/보행자 탐지 및 추적
- Farneback optical flow 기반 ego-motion 보상
- State back-propagation으로 동적/정적 분류
- 출력: `03_seg/masks/` (binary PNG), `bbox_sequence.json`

### 주요 파라미터
| 파라미터 | 값 | 비고 |
|---------|-----|------|
| YOLOv8 모델 | yolov8m-seg.pt | Medium 모델 |
| conf_thresh | 0.3 | 탐지 신뢰도 |
| iou_thresh | 0.5 | NMS |
| motion_thresh | 3.0 px | ego-compensated 이동량 |
| frame_gap_tol | 5 | 트랙 간 최대 갭 |
| 대상 클래스 | person, bicycle, car, motorcycle, bus, truck | 6종 |

### 이슈 및 권장사항
| # | 심각도 | 이슈 | 권장 수정 |
|---|--------|------|-----------|
| 1 | Medium | motion_thresh=3.0px가 모든 해상도/속도에 동일 적용 | 해상도 비례 threshold 또는 config 분리 |
| 2 | Low | 클래스별 motion threshold 미분화 | 대형차(bus/truck)와 보행자는 다른 threshold 고려 |
| 3 | Low | 배경 픽셀 < 100일 때 full-image fallback | 극도로 혼잡한 장면에서 정확도 저하 가능 |

---

## Stage 04 — COLMAP (Camera Pose Estimation)

**상태:** ✅ 정상 (주의사항 있음)

### 실행 결과
- 199개 프레임 등록 (registration rate 확인 필요)
- 4,230개 sparse 3D points 생성
- Waymo intrinsics 고정 모드로 실행 (PINHOLE/OPENCV)
- 출력: `04_colmap/` (poses.npy, intrinsics.json, sparse.ply, images_3dgs/)

### 주요 파라미터
| 파라미터 | 값 | 비고 |
|---------|-----|------|
| SIFT features | 8192 | max per image |
| sequential overlap | 20 frames | matcher 범위 |
| loop detection | disabled | 0 |
| 3DGS subsampling | every_n=2 | 등록 프레임 중 절반 |
| GPU | 자동 감지 (CPU fallback) | |

### 이슈 및 권장사항
| # | 심각도 | 이슈 | 권장 수정 |
|---|--------|------|-----------|
| 1 | Medium | loop detection 비활성화 | 긴 시퀀스에서 drift 누적 가능, 필요시 활성화 |
| 2 | Medium | reprojection error 등 품질 메트릭 미출력 | 재구성 품질 로그 추가 |
| 3 | Low | every_n=2 하드코딩 | 시퀀스 길이에 따라 조절 가능하게 |
| 4 | Low | point_filter.py 모듈 존재하나 미사용 | 통합 또는 제거 결정 필요 |

---

## Stage 05 — Depth Estimation

**상태:** ⚠️ 주의

### 실행 결과
- Depth Anything V2-Small로 전 프레임 depth 추정
- Per-frame min-max normalization → [0, 1] 범위
- 출력: `05_depth/depth_maps/` (.npy), `depth_vis/` (.png)

### 주요 파라미터
| 파라미터 | 값 | 비고 |
|---------|-----|------|
| 모델 | Depth-Anything-V2-Small-hf | HuggingFace |
| 정규화 | per-frame min-max | 프레임별 독립 |
| 출력 범위 | [0, 1] float32 | relative depth |
| 시각화 | INFERNO colormap | |

### 이슈 및 권장사항
| # | 심각도 | 이슈 | 권장 수정 |
|---|--------|------|-----------|
| 1 | Medium | Per-frame 정규화로 프레임 간 depth 일관성 없음 | Global normalization 또는 Stage 06에서 보정 (현재 Pass 1이 이를 처리) |
| 2 | Medium | 동적 객체(차량 등)에도 depth 추정 수행 | 마스크 적용하여 동적 영역 제외 또는 Stage 06에서 필터링 |
| 3 | Low | Small 모델 사용 (정확도 vs 속도 trade-off) | 정확도 필요시 Large 모델로 교체 (CC-BY-NC 라이선스 주의) |

---

## Stage 06 — Scale Alignment

**상태:** ❌ 수정 필요

### 실행 결과
```
Pass 1: scale=0.7306 shift=0.6660 (96817/124542 inliers, 77.7%)
         depth inversion 감지 → 자동 반전 후 재fit
Pass 2: ground plane normal=[-0.041,-0.999,0.000] d=0.043
         50000/50000 inliers (100%)
         measured_height=0.046m → k=32.7817
최종:   median=41.14m  range=[39.97, 41.94]m (frame median)
```

### 주요 파라미터
| 파라미터 | 값 | 비고 |
|---------|-----|------|
| RANSAC iters (Pass 1) | 1000 | linear regression |
| inlier_thresh (Pass 1) | 2.0 m | depth pair residual |
| RANSAC iters (Pass 2) | 500 | ground plane |
| inlier_thresh (Pass 2) | 0.15 m | ❌ 고정값, 스케일 미반영 |
| CAMERA_HEIGHT_PRIOR | 1.5 m | ❌ Waymo에 부적합 (실제 ~2.0m) |
| road region | bottom 25% | 이미지 하단 |
| road pixel step | 8 | 샘플링 간격 |
| vis colormap | TURBO, 0-50m | |

### Depth 시각화 분석
- TURBO colormap 기준: 앞 차량(초록) ≈ 5-10m, 도로(주황) ≈ 15-25m, 원거리(빨강) ≈ 35-50m
- Depth ordering 정상 (가까운 곳 → 먼 곳 gradient 올바름)
- 전체 스케일이 다소 과대 추정된 경향

### 이슈 및 권장사항
| # | 심각도 | 이슈 | 상세 | 수정 방안 |
|---|--------|------|------|-----------|
| 1 | **High** | Ground plane inlier threshold 스케일 미반영 | `inlier_thresh=0.15m`가 COLMAP 임의 스케일 데이터에 적용되어 100% inlier → RANSAC 무효화 | MAD(Median Absolute Deviation) 기반 adaptive threshold 도입 |
| 2 | **High** | Camera height prior 하드코딩 | `CAMERA_HEIGHT_PRIOR=1.5m`이나 Waymo 차량은 ~2.0-2.1m | input_type별 height dict로 변경 (video: 1.5m, waymo: 2.05m) |
| 3 | Medium | k=32.78 (큰 보정 계수) | COLMAP 임의 스케일 → 실제 미터 변환이므로 큰 k 자체는 정상이나, #1/#2 수정 후 재검증 필요 | 위 수정 후 재실행하여 확인 |
| 4 | Low | Frame median 편차 ~2m | 39.97~41.94m 범위로 안정적, 양호 | 현재 수준 유지 |

---

## 종합 요약

| Stage | 상태 | 긴급 수정 | 향후 개선 |
|-------|------|-----------|-----------|
| 02 Ingest | ✅ 정상 | 없음 | fps config 분리 |
| 03 Seg | ✅ 정상 | 없음 | motion_thresh 해상도 비례화 |
| 04 COLMAP | ✅ 정상 | 없음 | 품질 메트릭 출력, loop detection |
| 05 Depth | ⚠️ 주의 | 없음 | global normalization, 마스크 적용 |
| 06 Scale | ❌ 수정필요 | adaptive threshold + camera height | 수정 후 재실행 검증 |

### 즉시 수정 대상
1. **`align.py` — `fit_ground_plane()`**: inlier_thresh를 MAD 기반 adaptive로 변경
2. **`align.py` + `__init__.py`**: CAMERA_HEIGHT_PRIOR를 input_type별 딕셔너리로 변경
