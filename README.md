# PPE Watchman

산업 현장 CCTV/웹캠 스트림에서 **안전모·안전조끼 미착용**을 실시간 탐지하고, 위반 이벤트를 중앙 서버에 집계해 대시보드에 표시하는 **엣지형 + 중앙 집계형** 하이브리드 시스템 프로토타입.

---

## 왜 이 프로젝트인가

건설·제조 현장의 PPE(개인 보호 장비) 미착용은 매년 수천 건의 중대 재해로 이어진다. 사람이 모든 CCTV를 24시간 감시하는 건 불가능하다. 비전 AI가 이 감시 부담을 덜어내고, 위반 발생 즉시 운영자에게 알릴 수 있다.

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
1. **대역폭**: 현장에서 프레임(수십 MB/s)을 통째로 올리지 않고 이벤트(수 KB)만 전송
2. **엣지 자율성**: 중앙 서버 연결이 끊겨도 현장 감시는 계속
3. **멀티 사이트**: 여러 현장의 detector가 하나의 api에 연결 → 운영자는 한 대시보드에서 전체 관제

---

## 핵심 설계 결정과 Trade-off

| 결정 | 이유 | 프로덕션 확장 경로 |
|---|---|---|
| `violation_rules.py` 격리 | 현장마다 규칙이 다름 (건설=안전모, 화학=조끼+보안경) | 현장별 설정 파일 주입 |
| `inference.py` → Detection 계약 | 모델 교체(TensorRT/ONNX) 시 파이프라인 무변경 | `nvcr.io/nvidia/l4t` 기반 Jetson 이미지 |
| `event_publisher.py` 추상화 | HTTP/MQTT/WebSocket 교체 가능 | 공장 격리망은 MQTT broker 경유 |
| 프레임 샘플링 (5프레임에 1회) | PPE 상태는 초단위로 바뀌지 않음 | Temporal smoothing으로 FP 추가 감소 |
| Cooldown (10초) | 같은 위반의 API 스팸 방지 | 위반 지속 시간 트래킹으로 진화 가능 |
| SQLite + in-memory broadcaster | 프로토타입 단순성 | Postgres + Redis pub/sub |

---

## 실행 방법

```bash
# 1. 환경변수 설정
cp .env.example .env

# 2. 샘플 영상 준비 (공사현장 무료 영상)
# https://www.pexels.com/search/videos/construction/ 에서 다운로드
# → samples/sample.mp4 에 저장

# 3. 전체 스택 기동
docker-compose up --build
```

접근:
- **API 문서**: http://localhost:8000/docs
- **대시보드**: http://localhost:3000

---

## 디렉터리 구조

```
ppe-watchman/
├── detector/          # 엣지 추론 서비스 (Python + YOLO)
├── api/               # 중앙 FastAPI 서버
├── dashboard/         # Next.js 14 운영자 대시보드
├── samples/           # 테스트용 영상 (git 제외, 직접 준비)
└── docker-compose.yml
```

---

## 알려진 한계

- COCO pretrained weights 사용 중 (PPE fine-tuned 모델 미적용)
- 단일 카메라 스트림 (멀티 카메라는 detector 인스턴스 복수 기동으로 대응)
- 인증/권한 시스템 없음
- 이벤트 스냅샷(JPEG base64)만 저장, 전체 영상 저장 없음

---

## Next Steps

- [ ] HuggingFace PPE fine-tuned 모델 교체 (`keremberke/yolov8n-hard-hat-detection`)
- [ ] Jetson TensorRT engine 변환 + FPS 벤치마크
- [ ] Temporal smoothing (연속 N 프레임 위반 시에만 이벤트 발생)
- [ ] S3 스냅샷 업로드
- [ ] MQTT publisher 구현 (공장 격리망 대응)
