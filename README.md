# 교통사고 단안 영상 3DGS 재구성(졸업작품)

## 목표
"LiDAR 없는 단안 영상에서 교통사고 장면을 3DGS로 재구성하는 end-to-end 파이프라인"

## 프로젝트 개요
이 프로젝트는 **블랙박스/스마트폰 단안 영상**만으로 **교통사고 장면을 3D Gaussian Splatting(3DGS)** 으로 재구성하는 것을 목표로 합니다. 기존 연구가 LiDAR와 멀티캠을 전제로 하는 반면, 본 프로젝트는 **단일 영상 입력**만으로 동작하는 파이프라인을 구성합니다.

## 기존 연구와의 차별점 및 기여
1. **입력 단순화**
- 기존: Street Gaussians 등은 LiDAR + 멀티캠 필요
- Ours: 단안 영상 1개만으로 동작

2. **도메인 특화**
- 기존: 실내 정적 장면, 단일 물체 위주
- Ours: 교통사고 장면(다수 동적 객체, 단안 이동 카메라)

3. **동적 객체 마스킹 파이프라인**
- YOLOv8-seg로 픽셀 마스크 생성
- ByteTrack으로 트래킹
- COLMAP에 `--ImageReader.mask_path` 적용 → 포즈 추정 안정화

4. **응용 목적**
- 기존: 3D 재구성 품질 향상 중심
- Ours: 사고 과실 판단을 위한 다각도 장면 재현 시스템
  - 웹 뷰어 + 사고 지점 마킹 포함

## 파이프라인 (Ours)
1. 입력: 블랙박스/스마트폰 영상 (.mp4/.avi)
2. 프레임 추출
3. 객체 segmentation + tracking (YOLOv8-seg + ByteTrack)
4. COLMAP SfM (마스크 적용)
5. Depth Anything V2 (단안 depth)
6. Scale Alignment (COLMAP 스케일 + 카메라 높이 prior)
7. Dense Point Cloud 생성 (역투영)
8. 노이즈 필터링 (Open3D SOR)
9. 3D 궤적 추출 (마스크 영역 depth median)
10. 3D Gaussian Splatting 학습 (마스크 loss 제외)
11. .splat 변환
12. Web Viewer (궤적 오버레이 + 사고 지점 마킹)

## Baseline (GT)
- 입력: Waymo 전방 카메라 + LiDAR
- 처리: Street Gaussians
- 출력: `output.splat` (고품질 기준선)

## 평가 계획
1. **nuScenes (Camera + LiDAR)**
1. Street Gaussians(LiDAR) vs Ours(LiDAR 무시) → PSNR/SSIM 비교
1. **블랙박스 영상 (LiDAR 없음)**
1. Street Gaussians 실행 불가, Ours 실행 가능 → 정성 평가
1. **Vanilla 3DGS 대비**
1. 단안 3DGS 대비 개선, LiDAR 기반 품질에 근접함을 제시

## 데이터
- Waymo (Baseline/Ours)
- YouTube 사고 영상 (Ours)

## 하드웨어
- 메인: NVIDIA GeForce RTX 5060 Ti (VRAM 16GB)
- 테스트: NVIDIA RTX 3060 (VRAM 6GB), Intel i7-12700H, RAM 16GB

## 리포지토리 구조
```text
/Users/kyu216/projects/3DGS
├── ai-pipeline   # 파이프라인
├── backend       # API/DB/작업관리
├── frontend      # 웹 뷰어 및 서비스 UI
└── README.md
```

## 실행 방법

### 의존성 설치

```bash
pip install -r requirements.txt
```

시스템 의존성: `ffmpeg` (프레임 추출), `colmap` (카메라 포즈 추정 — Stage 04)

Waymo 입력 사용 시: `ai-pipeline/third_party/waymo-open-dataset/`에 waymo-open-dataset 클론 후 `PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python` 환경변수 설정

### 파이프라인 실행

```bash
# 전체 파이프라인 실행
python ai-pipeline/scripts/run_pipeline.py --input <video.mp4 or scene.tfrecord>

# 특정 스테이지만 실행
python ai-pipeline/src/pipeline/run_pipeline.py --input <input> --steps 02_ingest,03_seg

# Dry run (실행 계획만 확인)
python ai-pipeline/src/pipeline/run_pipeline.py --input <input> --dry_run
```

### 프레임 추출

```bash
# 일반 영상에서 프레임 추출
python ai-pipeline/scripts/extract_video_frames.py --video <path> [--out_dir <dir>] [--fps 10] [--quality 2]

# Waymo 전방 카메라 프레임 추출
python ai-pipeline/scripts/extract_waymo_front_frames.py --tfrecord <path> [--every_n 1] [--max_frames N]
```

### Docker (GPU 서버)

```bash
# 빌드 (최초 1회, ~20-30분 — COLMAP CUDA 빌드 포함)
docker compose build

# 파이프라인 실행
docker compose run pipeline --input /workspace/ai-pipeline/data/sample.tfrecord

# 특정 스테이지 실행
docker compose run pipeline --input /workspace/ai-pipeline/data/sample.tfrecord --steps 02_ingest,03_seg,04_colmap

# 이전 출력을 이어서 특정 스테이지부터 재개
docker compose run pipeline \
  --input /workspace/ai-pipeline/data/sample.tfrecord \
  --steps 06_scale \
  --out_root /workspace/ai-pipeline/outputs/run_YYYYMMDD_HHMMSS

# GPU 확인
docker compose run --entrypoint python3 pipeline -c "import torch; print('CUDA:', torch.cuda.is_available())"
```

`--out_root`에 기존 출력 디렉토리를 지정하면 이전 스테이지 결과를 그대로 활용하여 이어서 실행할 수 있습니다.

데이터와 출력은 볼륨 마운트(`ai-pipeline/data/`, `ai-pipeline/outputs/`)되어 호스트에 유지됩니다.

## 현재 상태
- 파이프라인 설계 및 문서화 단계
- 코드 구현은 아직 시작하지 않음

## 라이선스 메모
- YOLOv8-seg: AGPL-3.0
- ByteTrack: MIT
- COLMAP: BSD
- Depth Anything V2: Apache-2.0 (Small), CC-BY-NC-4.0 (Large)
- Open3D: MIT
- gaussian-splatting: Inria (non-commercial)
- splat-converter: MIT
- gsplat.js + React: MIT
