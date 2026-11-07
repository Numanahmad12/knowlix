"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  API_URL,
  MAX_FILE_SIZE_BYTES,
  MAX_FILE_SIZE_MB,
  MAX_PDF_PAGES,
  RELEVANCE_GATE,
  askQuestion,
  checkHealth,
  deleteSession,
  loadSample,
  retrievalLabel,
  uploadPdf,
} from "../lib/api";

const SAMPLE_QUESTIONS = [
  "What is this document about?",
  "What are the main findings?",
  "What problem does this paper solve?",
  "Summarize the key results.",
];

const SAMPLE_FILENAME = "test_document.pdf (sample)";

function formatSources(citations) {
  if (!citations || citations.length === 0) return null;
  return citations.map((p) => `p. ${p}`).join(", ");
}

function truncate(text, n = 600) {
  if (!text) return "";
  return text.length > n ? text.slice(0, n) + "…" : text;
}

// The backend appends a markdown-italic "_Support: n/m claims backed by
// the document._" line to the answer body (for clients that render
// markdown). This frontend renders answers as plain text and already shows
// the same information in the structured Support metadata line below, so
// strip the trailing line here to avoid showing it twice — once with
// literal underscores — above the metadata.
const SUPPORT_LINE_RE = /\n\n_Support: \d+\/\d+ claims backed by the document\._\s*$/;

function stripSupportLine(text) {
  if (!text) return "";
  return text.replace(SUPPORT_LINE_RE, "");
}

export default function Home() {
  const [health, setHealth] = useState({ checked: false, ok: false, data: null });
  // Loaded document (from /api/upload or /api/sample), or null.
  const [doc, setDoc] = useState(null);
  const [docName, setDocName] = useState(null);
  const [chat, setChat] = useState([]);
  const [question, setQuestion] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [asking, setAsking] = useState(false);
  const [analyzeStatus, setAnalyzeStatus] = useState(null); // {kind, text}
  const [error, setError] = useState(null);
  const [fileKey, setFileKey] = useState(null); // "name:size" of analyzed file
  const [pickedFile, setPickedFile] = useState(null);
  const fileInputRef = useRef(null);
  // Guards against double-submits / stale auto-analyze runs.
  const analyzingRef = useRef(false);
  const chatEndRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    checkHealth().then((result) => {
      if (!cancelled) setHealth({ checked: true, ...result });
    });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [chat, asking]);

  const loadDoc = useCallback((data, name, key) => {
    setDoc(data);
    setDocName(name);
    setFileKey(key);
    setChat([]);
    setError(null);
    setAnalyzeStatus({
      kind: "success",
      text: `Ready — ${data.page_count ?? "?"} pages, ${data.chunk_count ?? "?"} chunks indexed`,
    });
  }, []);

  const analyzeFile = useCallback(
    async (file) => {
      if (!file || analyzingRef.current) return;
      if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
        setError("That file is not a PDF — please choose a PDF file.");
        return;
      }
      if (file.size > MAX_FILE_SIZE_BYTES) {
        setError(
          `PDF is ${(file.size / 1024 / 1024).toFixed(1)} MB, above the ${MAX_FILE_SIZE_MB} MB limit.`
        );
        return;
      }
      analyzingRef.current = true;
      setAnalyzing(true);
      setError(null);
      setAnalyzeStatus({ kind: "info", text: "Analyzing your PDF…" });
      try {
        const data = await uploadPdf(file);
        loadDoc(data, file.name, `${file.name}:${file.size}`);
      } catch (err) {
        setError(err.message || "Couldn't analyze that PDF.");
        setAnalyzeStatus({ kind: "error", text: "Couldn't analyze that PDF" });
        // Remember the file so picking it again doesn't silently retry forever;
        // the user can still re-analyze explicitly with the button.
        setFileKey(`${file.name}:${file.size}`);
      } finally {
        analyzingRef.current = false;
        setAnalyzing(false);
      }
    },
    [loadDoc]
  );

  // Auto-analyze a newly picked file; the same file (name + size) is never re-analyzed.
  const onFilePicked = useCallback(
    (event) => {
      const file = event.target.files?.[0];
      if (!file) return;
      setPickedFile(file);
      const key = `${file.name}:${file.size}`;
      if (key !== fileKey) {
        analyzeFile(file);
      }
    },
    [analyzeFile, fileKey]
  );

  const onSample = useCallback(async () => {
    if (analyzingRef.current) return;
    analyzingRef.current = true;
    setAnalyzing(true);
    setError(null);
    setAnalyzeStatus({ kind: "info", text: "Loading the sample document…" });
    try {
      const data = await loadSample();
      loadDoc(data, SAMPLE_FILENAME, `sample:${data.filename || "test_document.pdf"}`);
    } catch (err) {
      setError(err.message || "Sample document not found. Upload a PDF instead.");
      setAnalyzeStatus({ kind: "error", text: "Couldn't load the sample document" });
    } finally {
      analyzingRef.current = false;
      setAnalyzing(false);
    }
  }, [loadDoc]);

  const ask = useCallback(
    async (questionText) => {
      const q = (questionText || "").trim();
      if (!q || asking) return;
      if (!doc?.session_id) {
        setError("Ask with no document loaded — upload a PDF or try the sample document first.");
        return;
      }
      setAsking(true);
      setError(null);
      setQuestion("");
      try {
        const result = await askQuestion(doc.session_id, q);
        setChat((prev) => [
          ...prev,
          {
            question: q,
            answer: stripSupportLine(result.answer),
            citations: result.citations || [],
            support: result.support || null,
            refused: !!result.refused,
            bestScore: typeof result.best_score === "number" ? result.best_score : 0,
            denseAvailable: !!result.dense_available,
            retrievalLabel:
              result.retrieval_label || retrievalLabel(doc),
            chunks: (result.chunks || []).slice(0, 3),
          },
        ]);
      } catch (err) {
        if (err.status === 404) {
          setError(
            "Unknown session — the document is no longer loaded on the backend. Please upload the PDF again."
          );
          setDoc(null);
          setDocName(null);
          setFileKey(null);
        } else {
          setError(err.message || "Could not answer that question.");
        }
      } finally {
        setAsking(false);
      }
    },
    [asking, doc]
  );

  const clearDoc = useCallback(async () => {
    if (doc?.session_id) {
      await deleteSession(doc.session_id);
    }
    setDoc(null);
    setDocName(null);
    setChat([]);
    setQuestion("");
    setError(null);
    setAnalyzeStatus(null);
    setFileKey(null);
    setPickedFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }, [doc]);

  const sensitive = doc?.sensitive_data || [];

  return (
    <div className="page">
      <header className="page-head">
        <h1>📄 Nexora</h1>
        <p>
          Upload a PDF and ask questions about it — answers are grounded in the
          document, with page citations.
        </p>
        <p className="health" aria-live="polite">
          {health.checked ? (
            health.ok ? (
              <>
                <span className="dot ok" /> Backend connected
                {health.data?.llm_mode ? ` · LLM: ${health.data.llm_mode}` : ""}
                {health.data?.version ? ` · v${health.data.version}` : ""}
              </>
            ) : (
              <>
                <span className="dot down" /> Backend unreachable at {API_URL} —
                upload and questions need the API running.
              </>
            )
          ) : (
            "Checking backend…"
          )}
        </p>
      </header>

      <div className="layout">
        <main className="main-col">
          {/* --- Upload card --- */}
          <section className="card" aria-label="Your document">
            <h2>Your document</h2>
            <input
              ref={fileInputRef}
              type="file"
              accept="application/pdf,.pdf"
              onChange={onFilePicked}
              aria-label="Upload a PDF"
            />
            <div className="upload-actions">
              <button
                type="button"
                className="primary"
                disabled={!pickedFile || analyzing}
                onClick={() => pickedFile && analyzeFile(pickedFile)}
              >
                Analyze this PDF
              </button>
              <span className="small">
                Analysis starts automatically when you pick a new file. Max{" "}
                {MAX_FILE_SIZE_MB} MB, {MAX_PDF_PAGES} pages.
              </span>
            </div>
            {analyzeStatus && (
              <div className={`status ${analyzeStatus.kind}`} role="status">
                {analyzing && <span className="spinner" aria-hidden="true" />}
                {analyzeStatus.text}
                {analyzing &&
                  " Extracting text, chunking it by page, and building the search index — then writing a short summary."}
              </div>
            )}
            {error && (
              <div className="status error" role="alert">
                {error}
              </div>
            )}
          </section>

          {/* --- Empty state --- */}
          {!doc && (
            <section className="card" aria-label="Start here">
              <h2>Start here</h2>
              <p>
                Upload a PDF above and it will be analyzed automatically. Then
                ask questions in plain language — every answer is checked
                against the document before you see it.
              </p>
              <p>
                <strong>What you&apos;ll get:</strong> a short summary, grounded
                answers with [p. N] page citations, and a note on how much of
                each answer the document actually backs up. Questions the
                document can&apos;t answer are refused instead of guessed.
              </p>
              <button
                type="button"
                className="primary"
                disabled={analyzing}
                onClick={onSample}
                style={{ width: "100%" }}
              >
                {analyzing ? "Loading…" : "Try the sample document"}
              </button>
            </section>
          )}

          {/* --- Loaded document --- */}
          {doc && (
            <>
              <section className="card" aria-label="Loaded document">
                <p>
                  <strong>Loaded:</strong> {docName || doc.filename || "document"}
                </p>
                <div className="metrics">
                  <div className="metric">
                    <div className="label">Pages</div>
                    <div className="value">{doc.page_count ?? "?"}</div>
                  </div>
                  <div className="metric">
                    <div className="label">Words</div>
                    <div className="value">
                      {(doc.word_count ?? 0).toLocaleString("en-US")}
                    </div>
                  </div>
                  <div className="metric">
                    <div className="label">Chunks</div>
                    <div className="value">{doc.chunk_count ?? "?"}</div>
                  </div>
                  <div className="metric">
                    <div className="label">Retrieval</div>
                    <div className="value" style={{ fontSize: "1rem", paddingTop: "0.2rem" }}>
                      {retrievalLabel(doc)}
                    </div>
                  </div>
                </div>
                {sensitive.length > 0 && (
                  <div className="status warning" role="alert">
                    This document appears to contain {sensitive.join(", ")}. Be
                    careful about sharing it.
                  </div>
                )}
              </section>

              <div className="two-col">
                <section className="card" aria-label="Document summary">
                  <h2>Document summary</h2>
                  <p className="summary">{doc.summary || "No summary available yet."}</p>
                  <p className="small">
                    The backend returns a summary only — there is no endpoint
                    for the full extracted text, so no text preview is shown
                    here.
                  </p>
                </section>

                <section className="card" aria-label="Ask a follow-up question">
                  <h2>Ask a follow-up question</h2>
                  <p>Tap a suggestion, or type your own question below.</p>
                  <div className="chips">
                    {SAMPLE_QUESTIONS.map((prompt) => (
                      <button
                        key={prompt}
                        type="button"
                        className="chip"
                        disabled={asking}
                        onClick={() => ask(prompt)}
                      >
                        {prompt}
                      </button>
                    ))}
                  </div>
                  <form
                    className="ask-row"
                    onSubmit={(e) => {
                      e.preventDefault();
                      ask(question);
                    }}
                  >
                    <input
                      type="text"
                      value={question}
                      onChange={(e) => setQuestion(e.target.value)}
                      placeholder="Ask a question about this PDF…"
                      aria-label="Ask a question about this PDF"
                      disabled={asking}
                    />
                    <button type="submit" className="primary" disabled={asking || !question.trim()}>
                      Ask
                    </button>
                  </form>
                  {asking && (
                    <div className="status info" role="status" style={{ marginTop: "0.75rem" }}>
                      <span className="spinner" aria-hidden="true" />
                      Searching the document and checking the answer…
                    </div>
                  )}
                </section>
              </div>

              {/* --- Conversation --- */}
              <section className="card" aria-label="Conversation">
                <h2>Conversation</h2>
                {chat.length === 0 && !asking && (
                  <p>
                    Questions you ask will appear here with their answers,
                    sources, and the passages they came from.
                  </p>
                )}
                <div className="chat">
                  {chat.map((item, i) => (
                    <article className="qa" key={i}>
                      <div className="q">
                        <span className="who">You</span>
                        {item.question}
                      </div>
                      <div className="a">
                        <span className="who">Answer</span>
                        {item.answer}
                      </div>
                      {item.refused && (
                        <p className="meta refused">
                          No passage scored above the {RELEVANCE_GATE.toFixed(2)}{" "}
                          relevance gate (best score{" "}
                          {item.bestScore.toFixed(2)}) — so the app refused
                          instead of guessing.
                        </p>
                      )}
                      {item.support && (
                        <p className="meta">
                          Support: {item.support.supported}/{item.support.total}{" "}
                          claims backed by the document.
                        </p>
                      )}
                      {item.citations && item.citations.length > 0 && (
                        <p className="meta">Sources: {formatSources(item.citations)}</p>
                      )}
                      <p className="meta">
                        Retrieval: {item.retrievalLabel} (best score{" "}
                        {item.bestScore.toFixed(2)})
                      </p>
                      {item.chunks && item.chunks.length > 0 && (
                        <details className="passages">
                          <summary>Relevant passages</summary>
                          <ol>
                            {item.chunks.map((chunk, j) => (
                              <li key={j}>
                                <span className="page-label">[p. {chunk.page}]</span>{" "}
                                {truncate(chunk.text, 600)}
                              </li>
                            ))}
                          </ol>
                        </details>
                      )}
                    </article>
                  ))}
                  <div ref={chatEndRef} />
                </div>
              </section>
            </>
          )}
        </main>

        {/* --- Sidebar --- */}
        <aside className="sidebar">
          <section className="card" aria-label="How it works">
            <h3>How it works</h3>
            <ol>
              <li>
                <strong>Upload</strong> a PDF file.
              </li>
              <li>
                The app <strong>extracts and chunks</strong> the text, page by
                page.
              </li>
              <li>
                <strong>Ask a question</strong> — the answer comes from the
                document, with citations.
              </li>
            </ol>
          </section>
          <div className="guardrails">
            <strong>Guardrails on:</strong> hybrid dense + keyword retrieval,
            groundedness gate, inline [p. N] citations, claim checks, and
            prompt-injection defense.
          </div>
          {doc && (
            <button type="button" className="danger" onClick={clearDoc}>
              Clear current PDF
            </button>
          )}
        </aside>
      </div>

      <footer className="foot">
        PDF Q&amp;A Studio · Answers are grounded in the document you upload.
      </footer>
    </div>
  );
}
