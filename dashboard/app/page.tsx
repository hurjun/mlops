/**
 * 메인 대시보드 페이지.
 *
 * Next.js App Router의 서버/클라이언트 컴포넌트 분리 전략:
 *
 * [서버 컴포넌트] page.tsx (이 파일, "use client" 없음)
 *   - 브라우저가 아닌 서버에서 실행됨
 *   - API에서 초기 데이터(최근 이벤트 20개, 일일 통계)를 미리 fetch
 *   - fetch한 데이터를 클라이언트 컴포넌트에 props로 넘겨줌
 *   - 장점: 페이지 첫 로드 시 빈 화면 없이 데이터가 바로 보임
 *
 * [클라이언트 컴포넌트] LiveTimeline
 *   - 브라우저에서 실행됨
 *   - WebSocket 연결해서 실시간 이벤트를 받아 화면 업데이트
 *   - "use client" 선언 필수
 */

import { DailyStats, ViolationEvent } from "@/lib/types";
import LiveTimeline from "./LiveTimeline";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * 서버에서 초기 데이터를 fetch하는 함수들.
 * 페이지 로드 시 서버에서 실행되므로 브라우저 없이도 동작.
 */
async function getRecentEvents(): Promise<ViolationEvent[]> {
  try {
    const res = await fetch(`${API_URL}/events?limit=20`, {
      cache: "no-store", // 항상 최신 데이터 fetch (캐시 사용 안 함)
    });
    if (!res.ok) return [];
    return res.json();
  } catch {
    return []; // API 서버가 아직 안 떴을 때 빈 배열 반환
  }
}

async function getDailyStats(): Promise<DailyStats | null> {
  try {
    const res = await fetch(`${API_URL}/stats/daily`, { cache: "no-store" });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export default async function DashboardPage() {
  // 두 fetch를 동시에 실행 (순차 실행보다 빠름)
  const [events, stats] = await Promise.all([
    getRecentEvents(),
    getDailyStats(),
  ]);

  return (
    <main style={{ maxWidth: 900, margin: "0 auto", padding: "24px 16px" }}>
      {/* ── 헤더 ── */}
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, color: "#e2e8f0" }}>
          PPE Watchman
        </h1>
        <p style={{ color: "var(--text-muted)", marginTop: 4 }}>
          산업 현장 PPE 위반 실시간 모니터링
        </p>
      </div>

      {/* ── 일일 통계 카운터 ── */}
      {stats && <StatsBar stats={stats} />}

      {/* ── 실시간 타임라인 (클라이언트 컴포넌트) ── */}
      <section style={{ marginTop: 24 }}>
        <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12, color: "var(--text-muted)" }}>
          실시간 위반 이벤트
        </h2>
        {/* initialEvents: 서버에서 미리 받아온 최근 20개를 넘겨줌 */}
        <LiveTimeline initialEvents={events} />
      </section>
    </main>
  );
}

/** 오늘 위반 통계를 카드로 표시하는 서버 컴포넌트 */
function StatsBar({ stats }: { stats: DailyStats }) {
  const cardStyle: React.CSSProperties = {
    background: "var(--surface)",
    border: "1px solid var(--border)",
    borderRadius: 8,
    padding: "16px 20px",
  };

  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
      {/* 전체 위반 횟수 */}
      <div style={cardStyle}>
        <div style={{ color: "var(--text-muted)", fontSize: 12, marginBottom: 6 }}>
          오늘 전체 위반
        </div>
        <div style={{ fontSize: 32, fontWeight: 700, color: "var(--danger)" }}>
          {stats.total}
        </div>
      </div>

      {/* 현장별 */}
      <div style={cardStyle}>
        <div style={{ color: "var(--text-muted)", fontSize: 12, marginBottom: 6 }}>
          현장별
        </div>
        {Object.entries(stats.by_site).map(([site, count]) => (
          <div key={site} style={{ display: "flex", justifyContent: "space-between" }}>
            <span style={{ color: "var(--text-muted)" }}>{site}</span>
            <span style={{ fontWeight: 600 }}>{count}</span>
          </div>
        ))}
        {Object.keys(stats.by_site).length === 0 && (
          <span style={{ color: "var(--text-muted)" }}>없음</span>
        )}
      </div>

      {/* 종류별 */}
      <div style={cardStyle}>
        <div style={{ color: "var(--text-muted)", fontSize: 12, marginBottom: 6 }}>
          종류별
        </div>
        {Object.entries(stats.by_kind).map(([kind, count]) => (
          <div key={kind} style={{ display: "flex", justifyContent: "space-between" }}>
            <span style={{ color: "var(--warning)" }}>{kind}</span>
            <span style={{ fontWeight: 600 }}>{count}</span>
          </div>
        ))}
        {Object.keys(stats.by_kind).length === 0 && (
          <span style={{ color: "var(--text-muted)" }}>없음</span>
        )}
      </div>
    </div>
  );
}
