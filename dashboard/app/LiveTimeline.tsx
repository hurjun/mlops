"use client";
/**
 * "use client": 이 파일은 브라우저에서 실행됨을 Next.js에 알리는 선언.
 * WebSocket, useState, useEffect 같은 브라우저 전용 기능을 쓰려면 필수.
 *
 * 서버 컴포넌트(page.tsx)에서 초기 이벤트를 받아
 * WebSocket으로 실시간 이벤트를 추가하며 타임라인을 표시한다.
 */

import { useLiveEvents } from "@/lib/websocket";
import { ViolationEvent } from "@/lib/types";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000";

/** 위반 kind별 색상 */
function kindColor(kind: string): string {
  if (kind.includes("helmet")) return "#fc4444"; // 빨강 — 안전모
  if (kind.includes("vest")) return "#f6ad55";   // 주황 — 조끼
  return "#a78bfa";                               // 보라 — 기타
}

/** ISO 시각 문자열 → 읽기 쉬운 형태 */
function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export default function LiveTimeline({
  initialEvents,
}: {
  initialEvents: ViolationEvent[];
}) {
  /**
   * useLiveEvents 훅:
   *   - initialEvents(서버에서 받은 최근 20개)로 시작
   *   - WebSocket 연결 후 새 이벤트가 올 때마다 앞에 추가
   *   - 최대 50개 유지
   *
   * events가 바뀔 때마다 React가 자동으로 화면을 다시 그림
   */
  const events = useLiveEvents(WS_URL, initialEvents);

  if (events.length === 0) {
    return (
      <div style={{ color: "var(--text-muted)", padding: "40px 0", textAlign: "center" }}>
        위반 이벤트 없음 — 대기 중…
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {events.map((ev) => (
        <EventCard key={ev.id} event={ev} />
      ))}
    </div>
  );
}

/** 위반 이벤트 1건을 카드로 표시 */
function EventCard({ event }: { event: ViolationEvent }) {
  const color = kindColor(event.kind);

  return (
    <div
      style={{
        background: "var(--surface)",
        border: `1px solid var(--border)`,
        borderLeft: `3px solid ${color}`, // 위반 종류별 색상 강조선
        borderRadius: 6,
        padding: "10px 14px",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        gap: 12,
      }}
    >
      {/* 왼쪽: 위반 정보 */}
      <div style={{ flex: 1, minWidth: 0 }}>
        {/* 위반 종류 뱃지 */}
        <span
          style={{
            background: color + "22", // 배경은 20% 투명도
            color: color,
            border: `1px solid ${color}44`,
            borderRadius: 4,
            padding: "2px 8px",
            fontSize: 12,
            fontWeight: 600,
            marginRight: 8,
          }}
        >
          {event.kind}
        </span>
        {/* 설명 */}
        <span style={{ color: "var(--text-muted)", fontSize: 12 }}>
          {event.description}
        </span>
      </div>

      {/* 오른쪽: 메타 정보 */}
      <div style={{ textAlign: "right", flexShrink: 0, fontSize: 12 }}>
        {/* 현장 + 확신도 */}
        <div style={{ color: "var(--text-muted)" }}>
          {event.site_id} · {(event.confidence * 100).toFixed(0)}%
        </div>
        {/* 발생 시각 */}
        <div style={{ color: "var(--text-muted)", marginTop: 2 }}>
          {formatTime(event.occurred_at)}
        </div>
      </div>
    </div>
  );
}
