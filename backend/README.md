# 3DGS 메인 백엔드 서버 (Spring Boot) 생산(Production) 등급 설계안

## 1. 개요
본 프로젝트는 단안 영상(블랙박스) 기반 3DGS(3D Gaussian Splatting) 시스템의 메인 백엔드 서버입니다. 악의적 클라우드 요금 폭탄(핫링킹, 무제한 업로드) 방어, 대용량 파일 GCS 우회, Message Queue를 이용한 AI 워커(GPU) 분산 처리, 개인정보 Audit 이력을 모두 고려한 클라우드 네이티브 게이트웨이입니다.

## 2. 아키텍처 5대 방어선
1. **업로드 요금 방어선**: 클라이언트에 넘겨주는 GCS URL에 구글 V4 서명의 `x-goog-content-length-range`를 추가해 50MB가 넘어가는 불법 영화/더미 파일의 클라우드 진입을 원천 차단합니다.
2. **트래픽 병목 방어선**: 백엔드 서버의 메모리를 전혀 거치지 않고, 클라이언트가 직접 영상을 GCS로 올리는 Direct Upload를 이용합니다.
3. **다운로드 대역폭 방어선**: AI 연산이 끝난 3D 모델(.splat)은 1회성 5분 만료 서명 URL로 발급하여 다른 사이트에서 크롤링하지 못하게 제한(Hotlinking)합니다.
4. **비동기 장애 전파 방어선**: Redis Stream/RabbitMQ 등의 메시지 큐를 사이에 두어 AI FastAPI 서버 장애 시 메인 서버가 터지는 현상을 막고 재시도(DLQ)를 격리합니다.
5. **법적 컴플라이언스(보안) 방어선**: 블랙박스 등 개인 정보가 담긴 영상 삭제 요청 시 **DB는 Soft Delete(보존 연한 준수)** 하되 **GCS의 실물 파일은 Hard Delete(완전 폐기)** 하여 사용자 안전을 보장합니다.

## 3. 요건별 상세 정의서

| 요구사항 ID | 도메인 | 기능명 | 상세 설명 | 우선순위 |
|---|---|---|---|---|
| REQ-ST-01 | 스토리지 보안 | V4 제한형 URL 발급 | 10분 만료의 업로드 URL 발급 시, `content-length-range` 헤더를 포함해 0~50MB 제약을 걸어 불법 트래픽을 GCS에서 컷 시킨다. | 1 |
| REQ-ST-02 | 스토리지 체계 | 오브젝트 물리적 격리 | 파일 덮어쓰기 방지를 위해 모든 객체 키를 `/{user_id}/{task_id}/input.mp4` 구조로 유저별 분리 저장한다. | 1 |
| REQ-ST-03 | 스토리지 보안 | 읽기 전용 핫링크 방지 | 3D 모델(`.splat`) 뷰어 제공 시, 영구 주소 대신 딱 5분짜리 GET 전용 만료 URL(Signed)로 응답하여 무단 도용을 완전 차단한다. | 1 |
| REQ-TK-01 | AI 연동 | 대기 순번 알림 UX | 사용자가 영상 처리 시작(`POST /tasks`)을 누르면, 백엔드는 MQ에 쌓인 깊이(Depth)를 계산해 "대기 순번 4번째, 대략 N분 남음"을 반환한다. | 1 |
| REQ-TK-02 | 에러 관리 | 표준 에러 코드 매핑 | AI가 작업 실패 시, 단순 텍스트가 아닌 `ERR_COLMAP_OOM`, `ERR_LOW_MOTION` 등의 실패 코드를 메인 서버의 `error_code` 필드에 매핑하여 프론트가 친절한 안내를 띄우게 돕는다. | 1 |
| REQ-TK-03 | Quota | 할당량과 분산 락 통제 | 클라우드 GPU비용 낭비를 억제하기 위해 **1인 1동시작업 제한(락)**, **1일 3회 변환 제한(Rate Limiter)**을 적용한다. | 1 |
| REQ-US-01 | 개인정보 | Soft Delete 컴플라이언스 | `DELETE /tasks/{taskId}` 요청을 받을 시 DB는 `deleted_at` 갱신으로 감사 목적을 남기고 GCS 내 원본 영상과 splat 파일은 즉시 물리 삭제한다. | 2 |

## 4. 핵심 API 규격

### 4.1. GCS 폭탄 방지 업로드 티켓 발급
* **GET** `/api/v1/tasks/upload-ticket?size=25000000`
* **Response**: Size 파라미터가 50MB(52,428,800 bytes)를 초과 시 즉각 `400 Bad Request` 에러. 정상일 땐 `uploadUrl` 과 예약된 UUID(TaskId) 동시 발급.

### 4.2. 변환 착수 및 대기열(Queue) 등록
* **POST** `/api/v1/tasks/{taskId}/start`
* **Response**: 
  ```json
  {
    "taskId": "UUID-...",
    "status": "PENDING",
    "queueDepthAhead": 3,
    "estimatedWaitMinutes": 90
  }
  ```

### 4.3. 결과 및 뷰어 렌더링용 임시 조회 (핫링킹 원천 차단)
* **GET** `/api/v1/tasks/{taskId}`
* **Response**: 
  ```json
  {
    "taskId": "UUID-...",
    "status": "COMPLETED",
    "videoSignedUrl": "https://...만료 5분...",
    "splatSignedUrl": "https://...만료 5분..."
  }
  ```

### 4.4. 작업 이력 및 무단 폐기 요청 (Soft Delete 적용)
* **DELETE** `/api/v1/tasks/{taskId}`
* **로직 구성**: DB의 `Task` 레코드는 `deleted_at = NOW()` 형태로 Update되며, 비동기 스레드에서 GCS SDK를 통해 `/{user_id}/{task_id}/...` 폴더 자체를 Drop(Hard Delete)한다.

### 4.5. AI 워커 콜백 엔드포인트
* **POST** `/api/v1/internal/webhook/task-status`
* **Request**: 
  ```json
  {
    "taskId": "UUID-...",
    "status": "FAILED",
    "errorCode": "ERR_COLMAP_BLUR",
    "errorMessage": "입력된 영상이 너무 흔들려 COLMAP SFM 복원이 불가능합니다."
  }
  ```
