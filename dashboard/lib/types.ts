/**
 * API 서버(api/src/schemas.py의 ViolationEventOut)와 1:1로 대응하는 타입.
 * 백엔드 스키마가 바뀌면 여기도 같이 바꿔야 한다.
 */
export type ViolationEvent = {
  id: number;
  site_id: string;   // 어느 현장 (예: "site-001")
  kind: string;      // 위반 종류 (예: "no_helmet", "no_vest")
  confidence: number; // 탐지 확신도 (0.0 ~ 1.0)
  bbox_xyxy_norm: [number, number, number, number]; // 위반 위치 (0~1 정규화)
  description: string;
  occurred_at: string; // ISO 8601 문자열 (예: "2026-04-21T09:30:00Z")
};

/**
 * GET /stats/daily 응답 타입.
 * 대시보드 상단 카운터에 사용.
 */
export type DailyStats = {
  date: string;
  by_site: Record<string, number>; // {"site-001": 12, "site-002": 5}
  by_kind: Record<string, number>; // {"no_helmet": 10, "no_vest": 7}
  total: number;
};
