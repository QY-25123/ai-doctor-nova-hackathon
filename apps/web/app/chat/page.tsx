"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import ReactMarkdown from "react-markdown";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface SpeechRecognitionEvent extends Event {
  resultIndex: number;
  results: { [i: number]: { [j: number]: { transcript: string }; length: number }; length: number };
}
interface SpeechRecognitionInstance extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((event: SpeechRecognitionEvent) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
}

type Message = {
  role: "user" | "assistant";
  content?: string;
  final_markdown?: string;
};

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [listening, setListening] = useState(false);
  const [hasSpeech, setHasSpeech] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || loading) return;

      setInput("");
      setMessages((prev) => [...prev, { role: "user", content: trimmed }]);
      setLoading(true);
      setError(null);

      try {
        const res = await fetch(`${API_URL}/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message: trimmed,
            conversation_id: conversationId ?? undefined,
          }),
        });
        if (!res.ok) throw new Error(res.statusText);
        const data = (await res.json()) as {
          conversation_id: number;
          risk_level: string | null;
          final_markdown: string | null;
        };
        setConversationId(data.conversation_id);
        const assistantMsg: Message = {
          role: "assistant",
          final_markdown: data.final_markdown ?? undefined,
        };
        setMessages((prev) => [...prev, assistantMsg]);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Request failed");
      } finally {
        setLoading(false);
      }
    },
    [conversationId, loading]
  );

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    sendMessage(input);
  }

  useEffect(() => {
    if (typeof window === "undefined") return;
    const SpeechRecognitionAPI =
      (window as unknown as { SpeechRecognition?: new () => SpeechRecognitionInstance }).SpeechRecognition ||
      (window as unknown as { webkitSpeechRecognition?: new () => SpeechRecognitionInstance }).webkitSpeechRecognition;
    if (!SpeechRecognitionAPI) return;
    setHasSpeech(true);
    const rec = new SpeechRecognitionAPI() as SpeechRecognitionInstance;
    rec.continuous = false;
    rec.interimResults = false;
    rec.lang = "en-US";
    rec.onresult = (event: SpeechRecognitionEvent) => {
      const transcript = event.results[event.resultIndex][0].transcript;
      setInput((prev) => (prev ? `${prev} ${transcript}` : transcript));
    };
    rec.onend = () => setListening(false);
    rec.onerror = () => setListening(false);
    recognitionRef.current = rec;
    return () => {
      try {
        recognitionRef.current?.abort();
      } catch {}
    };
  }, []);

  function toggleMic() {
    if (!recognitionRef.current) return;
    if (listening) {
      recognitionRef.current.stop();
      setListening(false);
    } else {
      try {
        recognitionRef.current.start();
        setListening(true);
      } catch {
        setListening(false);
      }
    }
  }

  return (
    <main className="chat-layout">
      <header className="chat-header">
        <h1>Health Assistant</h1>
        <p>General information only. Not medical advice.</p>
      </header>

      <section className="message-list">
        {messages.length === 0 && (
          <p className="message-placeholder">Describe how you feel or ask a question.</p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`message message--${m.role}`}>
            <div className="message-bubble">
              {m.role === "user" && m.content && <p className="message-text">{m.content}</p>}
              {m.final_markdown && (
                <div className="markdown-viewer">
                  <ReactMarkdown
                    components={{
                      h2: ({ children }) => <h2 className="md-h2">{children}</h2>,
                      ul: ({ children }) => <ul className="md-ul">{children}</ul>,
                      li: ({ children }) => <li className="md-li">{children}</li>,
                      p: ({ children }) => <p className="md-p">{children}</p>,
                      strong: ({ children }) => <strong className="md-strong">{children}</strong>,
                      a: ({ href, children }) => (
                        <a href={href} target="_blank" rel="noopener noreferrer" className="md-link">
                          {children}
                        </a>
                      ),
                    }}
                  >
                    {m.final_markdown}
                  </ReactMarkdown>
                </div>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="message message--assistant">
            <div className="message-bubble message-bubble--loading">Thinking…</div>
          </div>
        )}
        <div ref={bottomRef} />
      </section>

      {error && <p className="chat-error">{error}</p>}

      <form onSubmit={handleSubmit} className="chat-form">
        <div className="input-row">
          {hasSpeech && (
            <button
              type="button"
              className={`mic-btn ${listening ? "mic-btn--active" : ""}`}
              onClick={toggleMic}
              disabled={loading}
              title={listening ? "Stop" : "Voice input"}
              aria-label={listening ? "Stop listening" : "Start voice input"}
            >
              {listening ? "⏹" : "🎤"}
            </button>
          )}
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type or use voice…"
            disabled={loading}
            className="chat-input"
          />
          <button type="submit" disabled={loading || !input.trim()} className="chat-send">
            Send
          </button>
        </div>
      </form>
    </main>
  );
}
