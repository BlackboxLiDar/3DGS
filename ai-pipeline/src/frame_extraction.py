import subprocess
import os
import shutil

def process_video_for_3dgs(video_path, base_output_dir):
    # 1. 경로 설정
    colmap_dir = os.path.join(base_output_dir, "OUT_A_COLMAP")
    tdgs_dir = os.path.join(base_output_dir, "OUT_B_3DGS")

    # 폴더가 없으면 생성
    for d in [colmap_dir, tdgs_dir]:
        if not os.path.exists(d):
            os.makedirs(d)

    print(f"--- 단계 1: COLMAP용 프레임 추출 시작 (15fps) ---")
    # 처리 A: FFmpeg을 사용하여 15fps로 추출
    # -vf "fps=15": 초당 15프레임 추출
    # -q:v 2: 고화질 유지 (1~31 중 낮을수록 고화질)
    colmap_cmd = [
        'ffmpeg', 
        '-i', video_path, 
        '-vf', 'fps=15', 
        '-q:v', '2', 
        os.path.join(colmap_dir, 'frame_%04d.jpg')
    ]
    
    try:
        subprocess.run(colmap_cmd, check=True)
        print(f"COLMAP용 이미지 추출 완료: {colmap_dir}")
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg 실행 중 오류 발생: {e}")
        return

    print(f"\n--- 단계 2: 3DGS용 서브샘플링 시작 (약 5fps) ---")
    # 처리 B: 이미 추출된 15fps 이미지 중 3개당 1개씩 골라내면 5fps가 됨
    colmap_files = sorted([f for f in os.listdir(colmap_dir) if f.endswith('.jpg')])
    
    count = 0
    for i in range(0, len(colmap_files), 3):  # 3프레임 간격으로 복사 (15 / 3 = 5)
        src = os.path.join(colmap_dir, colmap_files[i])
        dst = os.path.join(tdgs_dir, colmap_files[i])
        shutil.copy(src, dst)
        count += 1
    
    print(f"3DGS용 이미지 서브샘플링 완료: {count}개 파일이 {tdgs_dir}에 저장됨")

# --- 실행부 ---
if __name__ == "__main__":
    # 본인의 영상 파일명으로 수정하세요
    target_video = "test_video.mp4" 
    output_root = "./processed_data"
    
    process_video_for_3dgs(target_video, output_root)