"use client"; // 이 파일은 브라우저에서만 실행됨 (WebSocket은 서버에 없음)

import { useEffect, useState } from "react";
import { ViolationEvent } from "./types";

/**
 * WebSocket 연결을 관리하고 실시간 이벤트를 상태로 제공하는 커스텀 훅.
 *
 * 커스텀 훅(Custom Hook):
 *   React의 useState, useEffect 등을 조합해서 재사용 가능한 로직을 만드는 패턴.
 *   "use"로 시작하는 함수 = 훅.
 *   page.tsx에서 const events = useLiveEvents(...) 한 줄로 실시간 이벤트 구독 가능.
 *
 * @param wsUrl  WebSocket 서버 주소 (예: "ws://localhost:8000")
 * @param initial 초기 이벤트 목록 (서버에서 미리 받아온 최근 20개)
 */
export function useLiveEvents(
  wsUrl: string,
  initial: ViolationEvent[] = []
): ViolationEvent[] {
  // events: 화면에 표시할 이벤트 목록 (초기값 = 서버에서 받아온 최근 20개)
  const [events, setEvents] = useState<ViolationEvent[]>(initial);

  useEffect(() => {
    /**
     * useEffect: 컴포넌트가 브라우저에 마운트된 후 실행되는 코드.
     * 여기서 WebSocket 연결을 만든다.
     *
     * 실행 시점: 페이지가 처음 열릴 때 1번 실행 (deps 배열이 [] 이므로)
     */
    const ws = new WebSocket(`${wsUrl}/ws`);

    ws.onopen = () => {
      console.log("WebSocket connected to", wsUrl);
    };

    ws.onmessage = (msg) => {
      /**
       * 서버에서 새 이벤트가 push 되면 여기 실행됨.
       * 기존 목록 앞에 새 이벤트를 추가하고 최근 50개만 유지.
       * 50개 제한: 메모리 보호 (이벤트가 무한정 쌓이면 브라우저가 느려짐)
       */
      try {
        const newEvent: ViolationEvent = JSON.parse(msg.data);
        setEvents((prev) => [newEvent, ...prev].slice(0, 50));
      } catch {
        console.warn("Failed to parse WebSocket message:", msg.data);
      }
    };

    ws.onerror = (err) => {
      console.error("WebSocket error:", err);
    };

    ws.onclose = () => {
      console.log("WebSocket disconnected.");
    };

    // cleanup 함수: 컴포넌트가 언마운트(페이지 닫힘/이동)될 때 실행
    // WebSocket을 닫지 않으면 연결이 계속 남아서 서버 자원 낭비
    return () => {
      ws.close();
    };
  }, []); // [] = 처음 한 번만 실행 (wsUrl이 바뀌어도 재연결 안 함)

  return events;
}
