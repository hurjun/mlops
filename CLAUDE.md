# CLAUDE.md

> 이 파일만 읽고 Claude Code가 전체 프로젝트를 처음부터 구현할 수 있도록 작성된 **자족적 프로젝트 브리프**.
> 빈 디렉터리에서 시작한다고 가정하고, 단계별로 빌드 순서·파일 구조·설계 결정·코딩 규약을 모두 담는다.

---

## 1. 미션

**미스릴(산업 안전 AI)** 면접용 프로토타입. 회사의 K-Palantir 컨셉(비전 기반 작업자 행동 분석 + 엣지 배포 + 대시보드)을 end-to-end 축소판으로 구현해, 면접 talking points를 코드로 뒷받침한다.

- **프로덕트 이름**: `ppe-watchman`
- **마감**: 2026-04-22 오전 면접
- **가용 시간**: 하룻밤 + 오전 일부 (약 10시간)
- **데모 형태**: 구두 설명 (라이브 데모 불필요). GitHub repo + README가 주 자산.
- **완성 기준**: 면접에서 모든 코드 경로를 자기 말로 설명할 수 있을 것. 기능보다 **설계 narrative의 선명함**이 우선.

---

## 2. 빌드 대상: PPE Watchman

산업 현장 CCTV/웹캠 스트림에서 **안전모·안전조끼 미착용**을 실시간 탐지하고, 위반 이벤트를 중앙 서버에 집계하여 대시보드에 표시하는 **엣지형 + 중앙 집계형** 하이브리드 시스템의 프로토타입.

### 아키텍처

```
detector (엣지)  ──POST /events──▶  api (중앙)  ──WebSocket──▶  dashboard (운영자)
 frame source                          SQLite
 YOLO inference                        broadcaster (asyncio.Queue)
 violation rules
 event publisher
```

- **detector**: 현장마다 1개 인스턴스(멀티 카메라는 멀티 detector). 무상태. GPU 있는 Jetson/산업용 PC 가정.
- **api**: 이벤트 수집·저장·브로드캐스트 허브. 스테이트풀(DB).
- **dashboard**: 운영자용 실시간 뷰. 라이브 이벤트 타임라인 + 일일 카운터.

### 왜 세 컴포넌트로 쪼갰나 (면접 핵심 narrative)

1. 엣지(detector) ↔ 중앙(api) 분리: 대역폭 절약(프레임 아닌 이벤트만 전송), 현장별 GPU 활용, 네트워크 단절 시에도 국지적 감시 지속 가능.
2. api ↔ dashboard 분리: 여러 현장의 이벤트를 한 대시보드에서 관제. 운영자가 현장마다 물리적으로 이동할 필요 없음.
3. 각 컴포넌트를 독립 Docker 이미지로 제공해 현장별 배포 자유도 확보.

---

## 3. 디렉터리 구조 (최종 형태)

```
ppe-watchman/
├── README.md                          # 면접 공개 자산 (Section 11 참조)
├── CLAUDE.md                          # 이 파일
├── docker-compose.yml                 # 전체 스택 오케스트레이션
├── .env.example                       # 환경변수 템플릿
├── .gitignore
│
├── detector/                          # 엣지 추론 서비스
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── src/
│   │   ├── __init__.py
│   │   ├── main.py                    # 엔트리포인트
│   │   ├── config.py                  # 환경변수 로드
│   │   ├── frame_source.py            # webcam/RTSP/file 추상화
│   │   ├── inference.py               # YOLO 래퍼 (Detection 반환)
│   │   ├── violation_rules.py         # 현장별 규칙 (customization point)
│   │   ├── event_publisher.py         # HTTP publisher (+ MQTT 확장 여지)
│   │   └── pipeline.py                # frame→infer→rules→publish 오케스트레이션
│   └── tests/
│       └── test_violation_rules.py    # pure logic 단위 테스트
│
├── api/                               # 중앙 FastAPI 서버
│   ├── Dockerfile
│   ├── requirements.txt
│   └── src/
│       ├── __init__.py
│       ├── main.py                    # FastAPI app + lifespan + CORS
│       ├── config.py
│       ├── database.py                # SQLAlchemy engine + session
│       ├── models.py                  # ORM: ViolationEvent
│       ├── schemas.py                 # Pydantic 요청/응답
│       ├── broadcaster.py             # in-memory pub/sub (asyncio.Queue)
│       └── routers/
│           ├── __init__.py
│           ├── events.py              # POST/GET /events
│           ├── stats.py               # GET /stats/daily
│           └── stream.py              # WebSocket /ws
│
├── dashboard/                         # Next.js 14 App Router
│   ├── Dockerfile
│   ├── package.json
│   ├── tsconfig.json
│   ├── next.config.js
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── globals.css
│   │   └── page.tsx                   # 라이브 타임라인 + 카운터
│   └── lib/
│       ├── types.ts
│       └── websocket.ts               # WS 구독 훅
│
├── samples/
│   └── .gitkeep                       # 샘플 영상 받는 방법은 README에 명시
│
└── docs/
    └── architecture.md                # (옵션) 심화 설계 논의
```

---

## 4. 빌드 순서 (시간 제약 기준)

앞 phase 안 끝나면 뒤는 스킵. 각 phase 끝나면 git commit.

### Phase 1: 뼈대 (30분)
1. 디렉터리 생성, `.gitignore`, `.env.example` 작성
2. README 초안 (Section 11의 템플릿 그대로)
3. `docker-compose.yml` 작성 — 아직 이미지 빌드 안 되어도 OK, 구조만

### Phase 2: detector (3시간) ← 가장 공들일 곳
1. `config.py` → `frame_source.py` → `inference.py` → `violation_rules.py` → `event_publisher.py` → `pipeline.py` → `main.py` 순서
2. 단위 테스트: `tests/test_violation_rules.py` (pure logic)
3. `requirements.txt`, `Dockerfile`
4. 로컬에서 `python -m src.main` 동작 확인 (api 아직 없으니 publish는 실패로그만 찍히면 OK)

### Phase 3: api (2시간)
1. `database.py` → `models.py` → `schemas.py` → `broadcaster.py` → `routers/*.py` → `main.py`
2. `requirements.txt`, `Dockerfile`
3. `docker-compose up api` 로 /docs 열어서 수동 확인
4. `docker-compose up detector api` 로 detector→api 이벤트 저장 확인 (SQLite에 row 들어오는지)

### Phase 4: dashboard (2시간)
1. Next.js 14 + App Router 스캐폴드
2. `app/page.tsx`: useEffect로 WS 연결, 수신 이벤트 state에 append, 타임라인 렌더
3. 초기 로드 시 REST로 최근 이벤트 20개 + 일일 통계 fetch
4. Tailwind 없이 `globals.css` + 인라인 style로 가볍게 (시간 절약)
5. Dockerfile (multi-stage build)

### Phase 5: 점검 + README 완성 (1시간)
1. `docker-compose up --build` 전체 스택 기동
2. README의 실행 방법 문구와 실제 동작 일치 확인
3. `cd detector && pytest -q` 통과 확인
4. README에 실행 스크린샷 또는 30초 녹화 gif 추가 (시간 여유 있을 때)
5. 최종 git commit: "v0.1 ready for interview"

---

## 5. 컴포넌트별 상세 설계

### 5.1 detector

#### `config.py`
- `@dataclass(frozen=True) class Config` 로 전체 설정 구조화
- `load_config() -> Config` 함수에서 `os.getenv`로 읽기
- 환경변수: `API_URL`, `SITE_ID`, `FRAME_SOURCE`(webcam/rtsp/file), `WEBCAM_INDEX`, `RTSP_URL`, `VIDEO_FILE`, `MODEL_PATH`, `CONFIDENCE_THRESHOLD`, `INFERENCE_INTERVAL`, `VIOLATION_COOLDOWN_SEC`

#### `frame_source.py`
- `abstract class FrameSource` with `frames() -> Iterator[np.ndarray]`, `close()`
- `OpenCVFrameSource(source: int | str, reconnect: bool = True)` — webcam idx, RTSP URL, 파일 경로 모두 지원
- RTSP 실패 시 간단한 reconnect 루프 (프로덕션은 exponential backoff 필요하다는 주석)
- `build_frame_source(kind, ...)` 팩토리
- **주석에 담을 narrative**: "Jetson에선 GStreamer pipeline string을 넘겨 NVDEC 사용 가능. 인터페이스 동일해서 클래스 하나만 추가하면 됨."

#### `inference.py`
- `@dataclass(frozen=True) class Detection`: `label: str`, `confidence: float`, `bbox_xyxy_norm: tuple[float, float, float, float]` (normalized)
- `class YoloDetector`: `__init__(model_path, confidence_threshold)`, `infer(frame_bgr) -> list[Detection]`
- Ultralytics YOLO 사용, `predict(verbose=False)`, 결과는 `.boxes.xyxy/conf/cls`
- 클래스명은 `self._model.names` 딕셔너리에서 가져옴 (weights 교체 시 자동 반영)
- **주석에 담을 narrative**: "Jetson 타겟은 TensorRT engine으로 교체, CPU는 ONNX runtime. Detection 계약만 유지하면 파이프라인 다른 곳 안 건드림."

#### `violation_rules.py` ★ **가장 중요 — customization point**
- `@dataclass(frozen=True) class Violation`: `kind`, `confidence`, `bbox_xyxy_norm`, `description`
- `class ViolationRules`: `__init__(required_ppe: Iterable[str])`, `evaluate(detections: list[Detection]) -> list[Violation]`
- 두 가지 경로 구현:
  - **Case A**: PPE fine-tuned 모델(`no_helmet`, `no_vest` 같은 전용 클래스 존재)일 때 → 직접 매핑
  - **Case B (프로토타입 fallback)**: COCO weights만 있을 때 → person 감지되고 helmet/hardhat 클래스 없으면 위반 이벤트 stub 발생 (end-to-end 파이프라인 동작 확인용)
- **주석에 담을 narrative**: "현장마다 규칙이 다르다. 건설=안전모 필수, 화학공장=안전모+보안경+조끼, 냉동창고=방한복만. 이 파일이 고객사별 커스터마이징 포인트. JD의 *'고객 요구사항 기반 프로토콜/알고리즘 설계'* 와 직접 대응." Temporal smoothing은 pipeline 레이어에서 별도 처리할 것이라는 언급 포함.

#### `event_publisher.py`
- `abstract class EventPublisher`: `publish(site_id, violation, snapshot)`
- `class HttpEventPublisher(api_url)`: `requests.Session` + `POST /events`. snapshot은 cv2.imencode JPEG → base64
- try/except로 네트워크 실패해도 파이프라인 안 죽게. warning 로그만.
- **주석에 담을 narrative**: "공장은 인터넷 격리되어 MQTT broker 쓰는 경우 많음. MQTT/WebSocket 사이블링은 이 인터페이스 implement만 하면 됨. 로봇 실시간 제어에서 MQTT 써본 경험 직결." (← Dogugonggan 경험 연결고리 — 이 주석 꼭 넣을 것)

#### `pipeline.py`
- `class Pipeline`: frame_source, detector, rules, publisher를 주입받음
- `run()`: `for frame in frame_source.frames():`
  - 프레임 인덱스가 `INFERENCE_INTERVAL`의 배수일 때만 추론 (샘플링으로 GPU/CPU 절약)
  - 추론 → rules → 각 violation에 대해 cooldown 체크 → publish
  - 50프레임마다 FPS/카운트 로그
- `_last_emitted: dict[str, float]` 로 kind별 마지막 방출 시각 추적 → `VIOLATION_COOLDOWN_SEC` 동안 중복 방지
- **주석에 담을 narrative**: "한 프레임 놓쳐도 PPE 상태는 초단위로 바뀌지 않음 → 5프레임에 1회 추론으로 충분. 같은 위반이 계속 잡히면 api에 초당 수십 건 전송 → cooldown으로 억제." Temporal smoothing은 다음 iteration으로 TODO.

#### `main.py`
- `logging.basicConfig` + SIGTERM 핸들러 (docker-compose down 클린 종료)
- config 로드 → 의존성 wire-up → `pipeline.run()` → finally `frame_source.close()`

#### `requirements.txt`
```
ultralytics==8.3.40
opencv-python-headless==4.10.0.84
numpy==1.26.4
requests==2.32.3
pytest==8.3.3
```

#### `Dockerfile`
- `FROM python:3.11-slim`
- `libgl1`, `libglib2.0-0` 설치 (OpenCV 의존성)
- pip install → src 복사 → `CMD ["python", "-m", "src.main"]`
- **주석**: "실제 엣지 배포는 `nvcr.io/nvidia/l4t-pytorch:*` (Jetson) 또는 `nvidia/cuda:12.*-runtime` (x86 GPU). 여기선 포터블하게 slim 사용."

#### `tests/test_violation_rules.py`
- 최소 4개 케이스: empty detections, no_helmet 직접 클래스, person only (Case B fallback), helmet 존재 시 no violation
- pytest 표준, import는 `from src.inference import Detection`

### 5.2 api

#### `config.py`
- `DATABASE_URL` (default `sqlite:///./data/events.db`), `CORS_ORIGINS`

#### `database.py`
- SQLAlchemy 2.0 스타일 `DeclarativeBase`
- `engine`, `SessionLocal`, `init_db()`, `get_db()` 의존성
- SQLite의 경우 `connect_args={"check_same_thread": False}`
- `init_db()`에서 SQLite 파일 경로의 parent 디렉터리 mkdir

#### `models.py`
- `ViolationEvent`: id, site_id(index), kind(index), confidence, bbox(str), description, snapshot_b64(Text, nullable), occurred_at(DateTime, index, default utcnow)

#### `schemas.py`
```python
class ViolationEventIn(BaseModel):
    site_id: str
    kind: str
    confidence: float
    bbox_xyxy_norm: list[float]  # length 4
    description: str
    snapshot_b64: str | None = None

class ViolationEventOut(BaseModel):
    id: int
    site_id: str
    kind: str
    confidence: float
    bbox_xyxy_norm: list[float]
    description: str
    occurred_at: datetime
    # snapshot은 GET 응답에서 기본 제외 (용량). 별도 엔드포인트로 가져옴.

class DailyStats(BaseModel):
    date: date
    by_site: dict[str, int]
    by_kind: dict[str, int]
    total: int
```

#### `broadcaster.py`
- 싱글톤 `EventBroadcaster`:
  - `subscribers: set[asyncio.Queue]`
  - `subscribe() -> Queue`, `unsubscribe(q)`
  - `async publish(event: dict)` — 모든 subscriber queue에 put_nowait (가득 찬 큐는 drop + 경고)
- 모듈 레벨 인스턴스 `broadcaster`
- **주석**: "프로세스 로컬 in-memory pub/sub. uvicorn --workers 1 전제. 멀티 워커면 Redis pub/sub으로 교체. 인터페이스 동일."

#### `routers/events.py`
- `POST /events`:
  - `ViolationEventIn` 받음
  - DB 저장 (snapshot_b64 포함)
  - `broadcaster.publish({...})` (snapshot 제외해서 클라이언트 부담 줄임)
  - 201 반환
- `GET /events?limit=20&site_id=...&kind=...`:
  - 최근순, snapshot 제외하고 리스트 반환

#### `routers/stats.py`
- `GET /stats/daily`:
  - 오늘 UTC 기준 `ViolationEvent` group by site_id, kind
  - `DailyStats` 반환

#### `routers/stream.py`
- `WebSocket /ws`:
  - accept → `queue = broadcaster.subscribe()`
  - try: `while True: event = await queue.get(); await ws.send_json(event)`
  - finally: `broadcaster.unsubscribe(queue)`

#### `main.py`
- `@asynccontextmanager lifespan`: `init_db()`
- `FastAPI(title="PPE Watchman API", version="0.1.0", lifespan=lifespan)`
- CORS 미들웨어 (`allow_origins=["*"]` + 프로덕션 주석)
- 3개 라우터 include
- `GET /health` 추가

#### `requirements.txt`
```
fastapi==0.115.0
uvicorn[standard]==0.32.0
sqlalchemy==2.0.35
pydantic==2.9.2
```

#### `Dockerfile`
- `FROM python:3.11-slim`
- pip install → src 복사 → `CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]`

### 5.3 dashboard

의도적으로 **가볍게**. Next.js 초과 사용 금지 (Redux, React Query, Tailwind 다 불필요).

#### `package.json` (핵심 deps만)
```json
{
  "dependencies": {
    "next": "14.2.x",
    "react": "^18.3.0",
    "react-dom": "^18.3.0"
  },
  "devDependencies": {
    "typescript": "^5.4.0",
    "@types/react": "^18.3.0",
    "@types/node": "^20.0.0"
  }
}
```

#### `lib/types.ts`
```typescript
export type ViolationEvent = {
  id: number;
  site_id: string;
  kind: string;
  confidence: number;
  bbox_xyxy_norm: [number, number, number, number];
  description: string;
  occurred_at: string;
};
```

#### `lib/websocket.ts`
- `useLiveEvents(apiUrl: string): ViolationEvent[]` 커스텀 훅
- `useEffect`에서 `new WebSocket(...)`, onmessage로 state append, cleanup에서 close
- 최근 50개만 유지 (메모리 보호)

#### `app/page.tsx`
- 서버 컴포넌트로 초기 최근 이벤트 20개 + 일일 통계 fetch
- 클라이언트 컴포넌트 `<LiveTimeline>` 로 실시간 append
- 레이아웃: 상단 카운터(오늘 위반 총계, kind별 breakdown), 하단 타임라인

#### `app/globals.css`
- CSS 변수로 색상 정의(배경/위험/경고), system font stack, 간단한 reset

#### `Dockerfile` (multi-stage)
```dockerfile
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
EXPOSE 3000
CMD ["node", "server.js"]
```

`next.config.js`에 `output: 'standalone'` 필수.

---

## 6. 코딩 규약

**Python:**
- `from __future__ import annotations` 모든 모듈 상단
- 타입 힌트 전면 사용 (`dict[str, int]`, `X | None` 스타일 — Python 3.10+)
- `@dataclass(frozen=True)` for 값 객체
- 모듈 docstring은 **"이 모듈이 왜 존재하는가"** 를 설명하는 narrative 스타일. 단순 요약 금지.
- 환경변수는 각 서비스의 `config.py`에 통합
- 로깅: `log = logging.getLogger(__name__)`, format `"%(asctime)s %(levelname)s %(name)s | %(message)s"`
- 주석은 **"왜"** 를 설명. 엣지 배포 고려사항, trade-off, 프로덕션 확장 포인트 언급. 이 주석들이 그대로 면접 talking point가 됨.

**TypeScript:**
- strict mode
- 함수형 컴포넌트 + hooks
- 서버 컴포넌트 기본, `"use client"`는 필요한 곳만

**파일:**
- 한 파일 한 책임
- tests/ 하위 import path 일관

---

## 7. 핵심 설계 결정 = 면접 narrative 앵커

아래 결정들이 **코드로 드러나도록** 빌드할 것. README와 코드가 상호 참조해야 함.

| 결정 | 근거 | 면접 talking point |
|---|---|---|
| 세 서비스 분리 (detector/api/dashboard) | 엣지 대역폭, 멀티 사이트 관제, 배포 자유도 | "실제 현장 배포 고려한 책임 분리" |
| `violation_rules.py` 격리 | 현장마다 규칙이 다름 | JD *"고객 요구사항 기반 프로토콜 설계"* 직접 대응 |
| `inference.py`가 Detection만 반환 | 모델 교체(TensorRT/ONNX) 시 파이프라인 무변경 | "엣지 타겟별 모델 배포 경로" |
| `event_publisher.py` 추상화 | HTTP/MQTT/WebSocket 교체 가능 | **Dogugonggan MQTT/WebRTC 경험 연결** |
| 프레임 샘플링 + cooldown | 실시간성 보존 + FP 스팸 억제 | "프로덕션에서 노이즈 어떻게 줄이나" 답변 |
| SQLite + in-memory broadcaster | 프로토타입 단순성, 확장 경로는 주석으로 | "프로덕션이면 Postgres + Redis" |
| `violation_rules` 단위 테스트 | pure logic 테스트 가능 수준으로 격리 | "엔지니어링 성숙도" 신호 |
| Docker compose | 1명령으로 전체 스택 기동 | "배포 가능한 상태로 만들었다" |

---

## 8. 실행 커맨드

```bash
# 전체 스택
cp .env.example .env
docker-compose up --build

# detector 단독
cd detector
pip install -r requirements.txt
python -m src.main

# detector 테스트
cd detector
pytest -q

# api 단독
cd api
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8000

# dashboard 단독
cd dashboard
npm install
npm run dev
```

접근 URL:
- api docs: http://localhost:8000/docs
- dashboard: http://localhost:3000

---

## 9. 하지 말 것 (스코프 밖)

- 인증/권한 시스템
- 실제 모델 fine-tune (pretrained weights + 교체 경로 문서화로 충분)
- Postgres·Redis 실제 도입 (주석으로 확장 경로만)
- Kubernetes manifest
- GraphQL, gRPC (REST + WebSocket로 충분)
- 추가 마이크로서비스 (detector/api/dashboard 3개 고정)
- Redux, React Query, Tailwind, Material UI (dashboard 가볍게 유지)
- Alembic 마이그레이션 (SQLite `create_all`로 충분)
- 멀티 카메라 동시 관리 로직 (detector 인스턴스를 여러 개 띄우는 방식으로 설명만)

**원칙: 있는 구조를 더 정교하게 만드는 쪽은 OK, 구조를 확장·추가하는 쪽은 NO.**

---

## 10. Gotchas

- **Mac/Windows Docker**: 웹캠 접근 불가 → `FRAME_SOURCE=file` + `samples/sample.mp4` 사용
- **Linux + 웹캠**: `docker-compose.yml`의 `devices: - /dev/video0:/dev/video0` 주석 해제
- **yolov8n.pt 다운로드**: 첫 실행 시 Ultralytics CDN에서 자동 다운로드. 오프라인 환경이면 사전 준비
- **PPE fine-tuned 모델 실제 적용 시**: HuggingFace의 `keremberke/yolov8n-hard-hat-detection` 등을 받아 `MODEL_PATH` 교체. Case B fallback 분기는 남겨둬도 무해.
- **SQLite 휘발**: `docker-compose down -v` 하면 `api/data/events.db` 날아감 (의도된 동작)
- **WebSocket 싱글톤**: in-memory pub/sub은 uvicorn `--workers 1` 전제. 멀티 워커 시 이벤트 일관성 깨짐 → 확장 경로는 주석으로만
- **샘플 영상 구하기**: Pexels(pexels.com/search/videos/construction)에서 무료 공사현장 영상 다운로드. README에 링크 안내.
- **Next.js standalone build**: `next.config.js`에 `output: 'standalone'` 필수 (Dockerfile에서 참조)

---

## 11. README.md 템플릿

README는 면접관이 볼 **공개 자산**. 아래 섹션 순서로 작성:

1. **왜 이 프로젝트인가** — 산업 안전 문제, 비전 AI의 역할
2. **아키텍처 다이어그램** — Section 2의 ASCII 그림 재사용
3. **세 컴포넌트 설명 + 왜 쪼갰나**
4. **핵심 설계 결정과 Trade-off** — Section 7의 테이블을 공개용으로 다듬어서
5. **프로덕션에서 추가 고민할 것** — 모델 경량화(TensorRT FP16/INT8), temporal smoothing, 현장 캘리브레이션, MLOps 데이터 루프, 프라이버시, 감시 정당성 UX
6. **실행 방법** — docker-compose up 한 방
7. **디렉터리 구조**
8. **알려진 한계** — COCO weights 사용 중, 단일 카메라, 인증 없음, 이벤트 스냅샷만 저장
9. **Next steps** — PPE fine-tuned 교체, TensorRT 변환 & FPS 벤치마크, temporal smoothing, S3 업로드, MQTT publisher

Tone: 솔직하게. "이건 안 했다"를 숨기지 말고 **왜 이 스코프에서 멈췄는지** 설명. 프로토타입의 미덕은 명확한 경계.

---

## 12. 커밋 전략

- Phase 단위로 의미 있는 커밋
- 메시지 형식: `[area] short description`
  - `[setup] initial structure and compose file`
  - `[detector] add frame source abstraction`
  - `[detector] add violation rules with tests`
  - `[api] add events endpoint`
  - `[api] add websocket broadcast`
  - `[dashboard] live timeline with websocket`
  - `[docs] complete README`
- 면접관이 커밋 히스토리 볼 가능성 있음 — 논리적 흐름이 드러나면 플러스 신호
- 마지막 커밋 전에 `pytest` + `docker-compose up --build` 성공 확인

---

## 13. Claude Code 작업 방식 가이드

이 프로젝트에서 Claude Code를 쓸 때의 권장 루틴:

1. **빈 디렉터리에 이 CLAUDE.md만 먼저 둔다** (`mkdir ppe-watchman && cd ppe-watchman && <CLAUDE.md 복사>`)
2. `claude` 실행
3. 첫 지시: **"CLAUDE.md 읽고 Phase 1부터 시작해. 각 phase 끝날 때마다 git commit 하고 다음 phase 진행 전에 알려줘."**
4. Phase 완료 보고 받으면 빠르게 훑어보고 OK → 다음 phase 지시
5. 의심스러운 선택은 즉시 개입: "왜 X 안 하고 Y 했어?" — Claude Code가 근거 설명 못 하면 CLAUDE.md 규약대로 다시 하라고 지시
6. Phase 2 (detector) 끝나면 반드시 한 번 **모든 파일을 직접 읽어본다**. 이 부분은 면접에서 말로 설명해야 함. 이해 안 되는 코드 있으면 Claude Code에 "이 함수 왜 이렇게 썼어?" 질문해서 파악.
7. 시간 부족하면 Phase 4 (dashboard) 스킵. README에 "dashboard는 구현 안 함, WebSocket 엔드포인트까지만" 이라고 명시하면 방어 가능.

**Claude Code에 첫 지시 예시:**
```
이 프로젝트는 내일 오전 미스릴 면접용 프로토타입이야. CLAUDE.md에 전체 설계·빌드 순서·규약이 다 있어. Phase 1 (뼈대) 부터 시작해줘. 각 phase 끝날 때마다 git commit 하고 멈춰서 내가 확인할 수 있게 해줘. CLAUDE.md의 Section 7 narrative 앵커들이 코드로 드러나도록 docstring/주석 꼭 넣을 것.
```

