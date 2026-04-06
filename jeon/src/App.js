import { useState, useRef, useEffect } from "react";
import "./App.css";
import bangulImg from "./assets/방울이_썸네일.png";
import wordmark from "./assets/05-워드마크.png"

/* ─────────────────────────────────────────────────────────
   상수
───────────────────────────────────────────────────────── */
const SYSTEM_PROMPT = `당신은 K-water(한국수자원공사)의 마스코트 방울이입니다.
진천군 수도정비 기본계획 문서를 기반으로 Graph RAG 파이프라인을 통해 Neo4j 데이터베이스에서 정보를 검색하여 답변합니다.
밝고 친근한 말투로, 가끔 "방울방울~", "물처럼 맑게!" 같은 방울이다운 표현을 자연스럽게 섞어 답변해주세요.
한국어로 답변해주세요.`;

const SUGGESTIONS = [
  { icon: "💧", label: "인구 계획", text: "진천군 전체 급수인구 목표가 얼마야?" },
  { icon: "🏗️", label: "시설 계획", text: "백곡정수장 개량 계획은?" },
  { icon: "🔗", label: "비상 대응", text: "비상연계 방안은?" },
  { icon: "🌊", label: "용수 공급", text: "광역상수도 공급 계획을 알려줘" },
];

/* ─────────────────────────────────────────────────────────
   방울이 SVG 컴포넌트
   variant: "default" | "happy" | "wink" | "talking"
───────────────────────────────────────────────────────── */
function BangulImg({ size = 48, bob = false }) {
  return (
    <img
      src={bangulImg}
      alt="방울이"
      width={size}
      height={size}
      className={bob ? "bangul-bob" : undefined}
      style={{ objectFit: "contain" }}
    />
  );
}

function WordmarkImg({ size = 48, bob = false }) {
  return (
    <img
      src={wordmark}
      alt="방울이"
      width={size}
      height={size}
      className={bob ? "bangul-bob" : undefined}
      style={{ objectFit: "contain" }}
    />
  );
}

/* ─────────────────────────────────────────────────────────
   타이핑 인디케이터
───────────────────────────────────────────────────────── */
function TypingDots() {
  return (
    <div className="typing-dots">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="typing-dot"
          style={{ animationDelay: `${i * 0.18}s` }}
        />
      ))}
    </div>
  );
}

/* ─────────────────────────────────────────────────────────
   메인 Chat 컴포넌트
───────────────────────────────────────────────────────── */
export default function Chat() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const bottomRef = useRef(null);
  const taRef = useRef(null);

  /* 자동 스크롤 */
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  /* textarea 높이 자동 조절 */
  const resizeTextarea = () => {
    const el = taRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 160) + "px";
  };

  /* 메시지 전송 */
  const send = async (text) => {
    const query = (text ?? input).trim();
    if (!query || loading) return;

    setInput("");
    if (taRef.current) taRef.current.style.height = "auto";

    const userMsg = { role: "user", content: query };
    const nextMsgs = [...messages, userMsg];
    setMessages(nextMsgs);
    setLoading(true);

    const aiIndex = nextMsgs.length;
    setMessages((prev) => [
      ...prev,
      { role: "assistant", content: "", streaming: true },
    ]);

    try {
      const response = await fetch("http://127.0.0.1:8000/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query,
          history: nextMsgs.map((m) => ({ role: m.role, content: m.content })),
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      if (!response.body) {
        throw new Error("응답 바디가 없습니다.");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let accumulated = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const text = decoder.decode(value, { stream: true });
        accumulated += text;

        setMessages((prev) => {
          const updated = [...prev];
          updated[aiIndex] = {
            role: "assistant",
            content: accumulated,
            streaming: true,
          };
          return updated;
        });
      }

      setMessages((prev) => {
        const updated = [...prev];
        updated[aiIndex] = {
          role: "assistant",
          content: accumulated,
          streaming: false,
        };
        return updated;
      });

    } catch (error) {
      console.error(error);

      setMessages((prev) => {
        const updated = [...prev];
        updated[aiIndex] = {
          role: "assistant",
          content: "앗, 오류가 났어요! 방울방울~ 다시 시도해줘요 😅",
          streaming: false,
        };
        return updated;
      });
    } finally {
      setLoading(false);
    }
  }

  /* 키 이벤트 (Enter 전송 / Shift+Enter 줄바꿈) */
  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  /* 파생 상태 */
  const isEmpty = messages.length === 0;
  const canSend = !loading && input.trim().length > 0;

  /* ── 렌더 ── */
  return (
    <div className="chat-root">

      {/* Header */}
      <header className="chat-header">
        <div className="chat-header__left">
          <WordmarkImg size={48} bob={false} />
          <div>
            <div className="chat-header__name">방울이 AI 어시스턴트</div>
          </div>
        </div>
        <div className="kwater-pill">
          <span className="online-dot" />
          K-water
        </div>
      </header>

      {/* Empty State */}
      {isEmpty && (
        <div className="chat-empty">
          <div className="chat-empty__hero">
            <BangulImg size={150} bob />
            <div className="chat-empty__bubble">
              안녕하세요! 저는 방울이에요 💧<br />
              무엇이든 물어보세요!
            </div>
            <div className="chat-empty__title">무엇이 궁금하신가요?</div>
          </div>

          <div className="suggestions">
            {SUGGESTIONS.map((s) => (
              <button
                key={s.text}
                className="suggestion-btn"
                onClick={() => send(s.text)}
              >
                <span className="suggestion-btn__label">{s.icon} {s.label}</span>
                {s.text}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Messages */}
      {!isEmpty && (
        <div className="chat-messages">
          <div className="chat-divider">오늘</div>

          {messages.map((msg, i) =>
            msg.role === "user" ? (
              /* 사용자 메시지 */
              <div key={i} className="msg-row msg-row--user">
                <div className="bubble-user">{msg.content}</div>
              </div>
            ) : (
              /* AI 메시지 */
              <div key={i} className="msg-row msg-row--ai">
                <div className="ai-avatar">
                  <BangulImg size={70} bob={msg.streaming} />
                </div>
                <div className="bubble-ai__wrap">
                  <div className="bubble-ai__name">방울이 💧</div>
                  <div className="bubble-ai">
                    {msg.streaming && !msg.content ? (
                      <TypingDots />
                    ) : (
                      <>
                        {msg.content}
                        {msg.streaming && <span className="stream-cursor" />}
                      </>
                    )}
                  </div>
                </div>
              </div>
            )
          )}

          <div ref={bottomRef} />
        </div>
      )}

      {/* Input */}
      <div className="chat-input-area">
        <div className="chat-input-box">
          <textarea
            ref={taRef}
            className="chat-textarea"
            value={input}
            onChange={(e) => { setInput(e.target.value); resizeTextarea(); }}
            onKeyDown={handleKeyDown}
            placeholder="방울이에게 질문하세요!  (Enter 전송 · Shift+Enter 줄바꿈)"
            disabled={loading}
            rows={1}
          />
          <button
            className={`send-btn ${canSend ? "send-btn--active" : "send-btn--disabled"}`}
            onClick={() => send()}
            disabled={!canSend}
          >
            <svg
              width="16" height="16" viewBox="0 0 16 16" fill="none"
              style={{ transform: "rotate(-90deg)" }}
            >
              <path
                d="M8 1.5L8 14.5M8 1.5L3 6.5M8 1.5L13 6.5"
                stroke={canSend ? "white" : "#bae6fd"}
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
        </div>
        <p className="chat-hint">

        </p>
      </div>

    </div>
  );
}