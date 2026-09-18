import { FormEvent, useEffect, useState } from "react";
import { AuthApi, api, EmployeeApi, type Citation } from "../api";
import { useAuth } from "../auth";
import { AdminBadge } from "../components/AdminBadge";

type Message = { role: "user" | "assistant"; content: string; citations?: Citation[] };
type Conversation = { id: string; title: string };

export function ChatPage() {
  const { user, setUser } = useAuth();
  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [history, setHistory] = useState<Conversation[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [documents, setDocuments] = useState<any[]>([]);
  const [docsOpen, setDocsOpen] = useState(false);

  async function loadData() {
    try {
      const items = await api<Conversation[]>("/api/conversations");
      setHistory(items);
      const docs = await EmployeeApi.getDocuments();
      setDocuments(docs);
    } catch {
      // ignore
    }
  }

  useEffect(() => {
    void loadData();
  }, []);

  async function logout() {
    await AuthApi.logout();
    setUser(null);
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!query.trim()) return;
    const text = query.trim();
    setQuery("");
    setBusy(true);
    setError(null);
    setMessages((current) => [...current, { role: "user", content: text }]);
    try {
      const result = await api<{ conversation_id: string; answer: string; citations: Citation[] }>("/api/chat", {
        method: "POST",
        body: JSON.stringify({ query: text, conversation_id: conversationId }),
      });
      setConversationId(result.conversation_id);
      setMessages((current) => [
        ...current,
        { role: "assistant", content: result.answer, citations: result.citations },
      ]);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to process request");
    } finally {
      setBusy(false);
    }
  }

  async function openConversation(id: string) {
    const detail = await api<{ messages: Array<{ role: "user" | "assistant"; content: string; citations: Citation[] }> }>(
      `/api/conversations/${id}`,
    );
    setConversationId(id);
    setMessages(detail.messages);
  }

  function startNewChat() {
    setConversationId(null);
    setMessages([]);
    setQuery("");
    setError(null);
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
          <div className="brand" style={{ fontFamily: "'Outfit', 'Inter', sans-serif", fontSize: "1.2rem", fontWeight: 700, background: "linear-gradient(90deg, #60a5fa, #a78bfa)", WebkitBackgroundClip: "text", color: "transparent" }}>
            {user?.company_name || "ACME Corp"}
          </div>
          {user && (
            <span style={{ 
              display: "inline-flex",
              alignItems: "center",
              background: "linear-gradient(135deg, #059669 0%, #10b981 100%)",
              color: "#ffffff",
              fontWeight: 700,
              fontSize: "0.72rem",
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              padding: "0.22rem 0.65rem",
              borderRadius: "9999px",
              border: "1px solid rgba(255, 255, 255, 0.35)",
              boxShadow: "0 2px 8px rgba(16, 185, 129, 0.35), inset 0 1px 1px rgba(255, 255, 255, 0.45)",
            }}>
              {user.role_names && user.role_names.length > 0 ? user.role_names[0] : "EMPLOYEE"}
            </span>
          )}
        </div>
        <div className="identity" style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
          <div style={{ position: "relative" }}>
            <button 
              className="linkish" 
              onClick={() => setDocsOpen(!docsOpen)}
              style={{ display: "flex", alignItems: "center", gap: "0.25rem", background: "none", border: "none", cursor: "pointer", fontSize: "0.9rem" }}
            >
              My Documents ({documents.length})
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="6 9 12 15 18 9"></polyline>
              </svg>
            </button>
            {docsOpen && (
              <div style={{ position: "absolute", top: "100%", right: 0, marginTop: "0.5rem", background: "var(--card-bg, #ffffff)", border: "1px solid var(--border-color, #e2e8f0)", borderRadius: "8px", boxShadow: "0 4px 6px -1px rgba(0,0,0,0.1)", minWidth: "250px", zIndex: 10 }}>
                {documents.length === 0 ? (
                  <div style={{ padding: "1rem", color: "var(--muted-color, #64748b)", fontSize: "0.9rem", textAlign: "center" }}>
                    No authorized documents.
                  </div>
                ) : (
                  <ul style={{ listStyle: "none", padding: "0.5rem", margin: 0, maxHeight: "300px", overflowY: "auto" }}>
                    {documents.map((doc) => (
                      <li key={doc.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "0.5rem", borderBottom: "1px solid var(--border-color, #e2e8f0)" }}>
                        <span style={{ color: "#000000", fontSize: "0.85rem", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", marginRight: "1rem", maxWidth: "150px" }} title={doc.title}>
                          {doc.title}
                        </span>
                        <a
                          href={EmployeeApi.downloadDocumentUrl(doc.id)}
                          target="_blank"
                          rel="noreferrer"
                          style={{ fontSize: "0.75rem", background: "var(--primary-color, #2563eb)", color: "white", padding: "0.2rem 0.5rem", borderRadius: "4px", textDecoration: "none" }}
                        >
                          Download
                        </a>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>
          
          <div className="user-identity-wrap" style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: "0" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <span style={{ fontWeight: 600 }}>{user?.full_name}</span>
              {user?.app_role === "ADMIN" && <AdminBadge />}
            </div>
            <span className="muted" style={{ fontSize: "0.8rem" }}>{user?.email}</span>
          </div>
          
          <button className="linkish" onClick={() => void logout()}>
            Logout
          </button>
        </div>
      </header>
      <div className="chat-layout">
        <aside className="sidebar" aria-label="Conversations">
          <h2>History</h2>
          {history.length === 0 ? <p className="muted">No conversations yet.</p> : null}
          <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: "0.5rem", overflow: "hidden" }}>
            {history.map((item) => (
              <li key={item.id} style={{ width: "100%", overflow: "hidden" }}>
                <button 
                  className="linkish" 
                  onClick={() => void openConversation(item.id)}
                  style={{ 
                    display: "block", 
                    width: "100%", 
                    textAlign: "left", 
                    whiteSpace: "nowrap", 
                    overflow: "hidden", 
                    textOverflow: "ellipsis",
                    padding: "0.5rem",
                    boxSizing: "border-box"
                  }}
                  title={item.title}
                >
                  {item.title}
                </button>
              </li>
            ))}
          </ul>
        </aside>
        <section className="chat-main">
          {messages.length === 0 ? (
            <div className="empty">
              <h1>Ask a question</h1>
              <p>Answers are generated only from documents you are authorized to read.</p>
            </div>
          ) : (
            <ol className="messages">
              {messages.map((message, index) => (
                <li key={`${message.role}-${index}`} className={message.role}>
                  <p>{message.content}</p>
                  {message.citations && message.citations.length > 0 ? (
                    <ul className="citations">
                      {message.citations.map((citation) => (
                        <li key={citation.source_id}>
                          {citation.title}
                          {citation.page ? ` · p.${citation.page}` : ""}
                          {citation.section ? ` · ${citation.section}` : ""}
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </li>
              ))}
            </ol>
          )}
          {error ? <p role="alert" className="error">{error}</p> : null}
          {busy ? <p className="muted">Retrieving authorized sources…</p> : null}
          <form className="composer" onSubmit={onSubmit}>
            <label className="sr-only" htmlFor="query">
              Question
            </label>
            <textarea
              id="query"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ask about company information you are allowed to access"
              required
            />
            <div style={{ display: "flex", gap: "1rem", marginTop: "1rem" }}>
              <button 
                type="submit" 
                disabled={busy} 
                style={{ flex: 1, padding: "0.75rem", borderRadius: "8px", fontWeight: 600 }}
              >
                Send
              </button>
              <button 
                type="button" 
                onClick={startNewChat}
                style={{ 
                  flex: 1, 
                  background: "transparent", 
                  color: "var(--primary-color, #2563eb)", 
                  border: "1px solid var(--primary-color, #2563eb)",
                  padding: "0.75rem",
                  borderRadius: "8px",
                  fontWeight: 600,
                  cursor: "pointer"
                }}
              >
                Start new chat
              </button>
            </div>
          </form>
        </section>
      </div>
    </div>
  );
}
