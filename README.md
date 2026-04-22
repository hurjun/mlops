# PPE Watchman

산업 현장 CCTV/웹캠 스트림에서 **안전모·안전조끼 미착용**을 실시간 탐지하고,
위반 이벤트를 중앙 서버에 집계해 운영자 대시보드에 표시하는
**엣지형 + 중앙 집계형** 하이브리드 시스템 프로토타입.

---

## 왜 이 프로젝트인가

건설·제조 현장의 PPE(개인 보호 장비) 미착용은 매년 수천 건의 중대 재해로 이어진다.
사람이 모든 CCTV를 24시간 감시하는 건 불가능하다.
비전 AI가 이 감시 부담을 덜어내고, 위반 발생 즉시 운영자에게 알릴 수 있다.

이 프로젝트는 그 개념을 **현장 배포 가능한 구조**로 축소 구현한다.

---

## 아키텍처

```
detector (엣지)  ──POST /events──▶  api (중앙)  ──WebSocket──▶  dashboard (운영자)
 frame source                          SQLite
 YOLO inference                        broadcaster (asyncio.Queue)
 violation rules
 event publisher
```

---

## 세 컴포넌트: 왜 쪼갰나

| 컴포넌트 | 역할 | 배포 위치 |
|---|---|---|
| **detector** | 프레임 수집 → YOLO 추론 → 위반 판정 → 이벤트 전송 | 현장 엣지 PC / Jetson |
| **api** | 이벤트 수집·저장·브로드캐스트 | 사내 서버 / 클라우드 |
| **dashboard** | 실시간 위반 타임라인 + 일일 통계 | 관제실 브라우저 |

**분리 이유:**

1. **대역폭 절약**: 현장에서 프레임(수십 MB/s) 대신 이벤트(수 KB)만 전송
2. **엣지 자율성**: 중앙 서버 연결이 끊겨도 현장 감시는 계속 (네트워크 실패 시 경고 로그만)
3. **멀티 사이트 관제**: 여러 현장 detector → 하나의 api → 한 대시보드에서 전체 관제

---

## 핵심 설계 결정과 Trade-off

| 결정 | 이유 | 프로덕션 확장 경로 |
|---|---|---|
| `violation_rules.py` 격리 | 현장마다 PPE 규칙이 다름 (건설=안전모, 화학=조끼+보안경) | 현장별 설정 파일 주입 |
| `inference.py` → Detection 계약 | 모델 교체(TensorRT/ONNX) 시 파이프라인 코드 무변경 | `nvcr.io/nvidia/l4t` 기반 Jetson 이미지 |
| `event_publisher.py` 추상화 | HTTP/MQTT/WebSocket 교체 가능 | 공장 격리망은 MQTT broker 경유 |
| 프레임 샘플링 (5프레임에 1회) | PPE 상태는 초 단위로 바뀌지 않음 → GPU 부하 5배 절감 | Temporal smoothing으로 FP 추가 감소 |
| Cooldown (10초) | 같은 위반의 API 스팸 방지 | 위반 지속 시간 트래킹으로 진화 |
| SQLite + in-memory broadcaster | 프로토타입 단순성 | Postgres + Redis pub/sub |
| WebSocket (REST polling 아님) | 이벤트 발생 시 즉시 push → 실시간성, 불필요한 요청 없음 | 동일 인터페이스 유지 |
| Docker Compose | 명령어 하나로 전체 스택 기동 | K8s manifest로 확장 |

---

## 프로덕션에서 추가 고민할 것

- **모델 경량화**: TensorRT FP16/INT8 변환으로 Jetson에서 추론 속도 향상
- **Temporal smoothing**: 연속 N 프레임에서 위반 감지 시에만 이벤트 발생 → FP 감소
- **MLOps 데이터 루프**: 위반 스냅샷을 S3에 적재 → 라벨링 → 재학습 파이프라인
- **MQTT publisher**: 인터넷 격리 공장망 대응
- **프라이버시**: 스냅샷 저장 범위, 얼굴 블러 처리, 데이터 보존 정책

---

## 실행 방법

```bash
# 1. 환경변수 설정
cp .env.example .env

# 2. 샘플 영상 준비 (공사현장 무료 영상)
# https://www.pexels.com/search/videos/construction/ 에서 다운로드
# → samples/sample.mp4 로 저장

# 3. 전체 스택 기동 (명령어 하나)
docker-compose up --build
```

| 서비스 | URL |
|---|---|
| API 문서 (Swagger) | http://localhost:8000/docs |
| 대시보드 | http://localhost:3000 |

---

## 단위 테스트

```bash
cd detector
pip install -r requirements.txt
pytest -v
```

```
tests/test_violation_rules.py::TestCaseA_DirectViolationLabels::test_no_helmet_detected PASSED
tests/test_violation_rules.py::TestCaseA_DirectViolationLabels::test_no_vest_detected PASSED
tests/test_violation_rules.py::TestCaseA_DirectViolationLabels::test_violation_not_in_required_ppe_ignored PASSED
tests/test_violation_rules.py::TestCaseB_CocoFallback::test_person_without_helmet_triggers_violation PASSED
tests/test_violation_rules.py::TestCaseB_CocoFallback::test_person_with_helmet_no_violation PASSED
tests/test_violation_rules.py::TestCaseB_CocoFallback::test_person_missing_multiple_ppe PASSED
tests/test_violation_rules.py::TestCaseB_CocoFallback::test_no_person_no_violation PASSED
tests/test_violation_rules.py::TestCaseB_CocoFallback::test_empty_detections PASSED

8 passed in 0.13s
```

---

## 디렉터리 구조

```
ppe-watchman/
├── detector/                   # 엣지 추론 서비스
│   ├── src/
│   │   ├── config.py           # 환경변수 → Config 객체
│   │   ├── frame_source.py     # webcam/RTSP/file 추상화
│   │   ├── inference.py        # YOLO 래퍼 → Detection 계약
│   │   ├── violation_rules.py  # 현장별 PPE 규칙 (커스터마이징 포인트)
│   │   ├── event_publisher.py  # HTTP publisher (MQTT 교체 가능)
│   │   ├── pipeline.py         # 샘플링 + cooldown 오케스트레이션
│   │   └── main.py             # 의존성 조립 + 실행
│   └── tests/
│       └── test_violation_rules.py
│
├── api/                        # 중앙 FastAPI 서버
│   └── src/
│       ├── database.py         # SQLAlchemy 연결
│       ├── models.py           # ViolationEvent 테이블
│       ├── schemas.py          # Pydantic 입출력 스키마
│       ├── broadcaster.py      # in-memory pub/sub
│       └── routers/
│           ├── events.py       # POST/GET /events
│           ├── stats.py        # GET /stats/daily
│           └── stream.py       # WebSocket /ws
│
├── dashboard/                  # Next.js 14 운영자 대시보드
│   ├── app/
│   │   ├── page.tsx            # 서버 컴포넌트 (초기 데이터 fetch)
│   │   └── LiveTimeline.tsx    # 클라이언트 컴포넌트 (WebSocket)
│   └── lib/
│       ├── types.ts            # ViolationEvent, DailyStats 타입
│       └── websocket.ts        # useLiveEvents 훅
│
├── samples/                    # 테스트용 영상 (직접 준비)
├── docker-compose.yml          # 전체 스택 오케스트레이션
└── .env.example                # 환경변수 템플릿
```

---

## 알려진 한계

- **COCO pretrained weights** 사용 중 (PPE fine-tuned 모델 미적용)
  - `MODEL_PATH`에 `keremberke/yolov8n-hard-hat-detection` 교체 시 Case A 경로 동작
- **단일 카메라** 스트림 (멀티 카메라는 detector 인스턴스 복수 기동으로 대응)
- **인증/권한 시스템** 없음
- **in-memory broadcaster**: uvicorn 단일 프로세스 전제 (멀티 워커 시 Redis 필요)

---

## Next Steps

- [ ] PPE fine-tuned 모델 교체 (`keremberke/yolov8n-hard-hat-detection`)
- [ ] Jetson TensorRT engine 변환 + FPS 벤치마크
- [ ] Temporal smoothing (연속 N 프레임 위반 시에만 이벤트 발생)
- [ ] S3 스냅샷 업로드
- [ ] MQTT publisher 구현 (공장 격리망 대응)
- [ ] Postgres + Redis 교체 (멀티 워커 스케일아웃)
