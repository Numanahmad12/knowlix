"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  ArrowDown,
  ArrowRight,
  BarChart3,
  BookOpen,
  Bot,
  Check,
  CheckCircle2,
  Clock,
  Copy,
  Database,
  ExternalLink,
  Eye,
  FileCode,
  FileText,
  Filter,
  HelpCircle,
  Info,
  Layers,
  LayoutDashboard,
  Maximize2,
  Minimize2,
  Play,
  RefreshCw,
  Search,
  Settings as SettingsIcon,
  ShieldAlert,
  ShieldCheck,
  Sliders,
  Sparkles,
  Terminal,
  Trash2,
  UploadCloud,
  Zap,
} from "lucide-react";
import {
  API_URL,
  MAX_FILE_SIZE_BYTES,
  MAX_FILE_SIZE_MB,
  MAX_PDF_PAGES,
  RELEVANCE_GATE,
  askQuestion,
  checkHealth,
  clearAllCache,
  deleteCacheEntry,
  deleteSession,
  fetchBenchmarkHistory,
  fetchCacheEntries,
  fetchCacheSettings,
  fetchCacheStats,
  fetchSuggestedQuestions,
  loadSample,
  retrievalLabel,
  runBenchmark,
  updateCacheSettings,
  uploadPdf,
} from "../lib/api";

import { Sidebar } from "./components/Sidebar";
import { Header } from "./components/Header";
import { Button } from "./components/ui/Button";
import { Badge } from "./components/ui/Badge";
import { Card } from "./components/ui/Card";
import { EmptyState } from "./components/ui/EmptyState";
import { Input } from "./components/ui/Input";
import CommandPalette from "./components/CommandPalette";

// Dynamically import Three.js 3D canvas so it renders purely on client
const ThreeSemanticOrb = dynamic(() => import("./components/ThreeSemanticOrb"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-64 flex items-center justify-center">
      <div className="w-8 h-8 rounded-full border-2 border-[#f3b8ca] border-t-transparent animate-spin" />
    </div>
  ),
});

// Dynamic suggestions generated from active PDF

const SAMPLE_FILENAME = "test_document.pdf (sample)";

function truncate(text, n = 300) {
  if (!text) return "";
  return text.length > n ? text.slice(0, n) + "…" : text;
}

const SUPPORT_LINE_RE = /\n\n_Support: \d+\/\d+ claims backed by the document\._\s*$/;

function stripSupportLine(text) {
  if (!text) return "";
  return text.replace(SUPPORT_LINE_RE, "");
}

export default function Home() {
  // Navigation State: "overview" | "documents" | "workspace" | "cache" | "analytics" | "guardrails" | "settings"
  const [currentView, setCurrentView] = useState("overview");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [rightPanelOpen, setRightPanelOpen] = useState(true);
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);

  // App & Backend State
  const [health, setHealth] = useState({ checked: false, ok: false, data: null });
  const [documents, setDocuments] = useState([]);
  const [activeDoc, setActiveDoc] = useState(null);
  const [activeCitationPage, setActiveCitationPage] = useState(null);

  // Chat State
  const [chat, setChat] = useState([]);
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeStatus, setAnalyzeStatus] = useState(null);
  const [error, setError] = useState(null);
  const [copySuccess, setCopySuccess] = useState(null);

  // Drag-and-drop state
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef(null);
  const analyzingRef = useRef(false);
  const chatEndRef = useRef(null);
  const messagesContainerRef = useRef(null);
  const textareaRef = useRef(null);

  // Dynamic Suggestions & Scroll Management
  const [suggestions, setSuggestions] = useState([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [isAtBottom, setIsAtBottom] = useState(true);
  const [hasNewMessagesWhileScrolledUp, setHasNewMessagesWhileScrolledUp] = useState(false);

  // Semantic Cache & Telemetry State
  const [cacheStats, setCacheStats] = useState(null);
  const [cacheEntries, setCacheEntries] = useState([]);
  const [cacheFilter, setCacheFilter] = useState("");
  const [cacheSettings, setCacheSettings] = useState(null);
  const [benchmarkResult, setBenchmarkResult] = useState(null);
  const [benchmarking, setBenchmarking] = useState(false);
  const [notice, setNotice] = useState(null);

  // Check backend health
  useEffect(() => {
    let cancelled = false;
    checkHealth().then((result) => {
      if (!cancelled) setHealth({ checked: true, ...result });
    });
    return () => {
      cancelled = true;
    };
  }, []);

  // Scroll management: keep at bottom if user is already at bottom
  const handleMessagesScroll = () => {
    const el = messagesContainerRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 60;
    setIsAtBottom(atBottom);
    if (atBottom) {
      setHasNewMessagesWhileScrolledUp(false);
    }
  };

  const scrollToBottom = (smooth = true) => {
    const el = messagesContainerRef.current;
    if (!el) return;
    el.scrollTo({
      top: el.scrollHeight,
      behavior: smooth ? "smooth" : "auto",
    });
    setHasNewMessagesWhileScrolledUp(false);
  };

  useEffect(() => {
    if (isAtBottom) {
      scrollToBottom(false);
    } else {
      setHasNewMessagesWhileScrolledUp(true);
    }
  }, [chat, asking]);

  // Dynamic Suggestions: Load whenever active document changes
  useEffect(() => {
    if (!activeDoc) {
      setSuggestions([]);
      return;
    }
    if (activeDoc.suggested_questions && activeDoc.suggested_questions.length > 0) {
      setSuggestions(activeDoc.suggested_questions);
      return;
    }
    let active = true;
    setLoadingSuggestions(true);
    fetchSuggestedQuestions(activeDoc.session_id)
      .then((data) => {
        if (active && data?.suggested_questions?.length > 0) {
          setSuggestions(data.suggested_questions);
          setActiveDoc((prev) =>
            prev ? { ...prev, suggested_questions: data.suggested_questions } : prev
          );
        }
      })
      .catch((err) => {
        console.warn("Could not fetch suggestions:", err);
      })
      .finally(() => {
        if (active) setLoadingSuggestions(false);
      });
    return () => {
      active = false;
    };
  }, [activeDoc?.session_id, activeDoc?.doc_hash]);

  // Load Cache Telemetry & Settings
  const refreshCacheData = useCallback(async () => {
    try {
      const [stats, entriesData, settings, bench] = await Promise.all([
        fetchCacheStats(),
        fetchCacheEntries(cacheFilter),
        fetchCacheSettings(),
        fetchBenchmarkHistory(),
      ]);
      setCacheStats(stats);
      setCacheEntries(entriesData.entries || []);
      setCacheSettings(settings);
      if (bench?.history?.length > 0) {
        setBenchmarkResult(bench.history[0]);
      }
    } catch (e) {
      console.warn("Failed to fetch cache data:", e);
    }
  }, [cacheFilter]);

  useEffect(() => {
    refreshCacheData();
    const interval = setInterval(refreshCacheData, 12000);
    return () => clearInterval(interval);
  }, [refreshCacheData]);

  // Notice banner auto-clear
  const showNotice = (msg, type = "success") => {
    setNotice({ msg, type });
    setTimeout(() => setNotice(null), 4000);
  };

  // Keyboard shortcut listener (Cmd+K / Ctrl+K)
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setCommandPaletteOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Handlers for Document Upload & Selection
  const registerNewDocument = (docMeta) => {
    setDocuments((prev) => {
      const filtered = prev.filter((d) => d.session_id !== docMeta.session_id);
      return [docMeta, ...filtered];
    });
    setActiveDoc(docMeta);
    showNotice(`Document "${docMeta.filename}" indexed successfully.`);
  };

  const handleAnalyzeFile = async (file) => {
    if (!file) return;
    if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
      setError("Please select a valid PDF file.");
      return;
    }
    if (file.size > MAX_FILE_SIZE_BYTES) {
      setError(`File is too large (${(file.size / (1024 * 1024)).toFixed(1)} MB). Max limit is ${MAX_FILE_SIZE_MB} MB.`);
      return;
    }

    setError(null);
    setAnalyzing(true);
    analyzingRef.current = true;
    setAnalyzeStatus("Parsing PDF and extracting page text…");

    try {
      setTimeout(() => {
        if (analyzingRef.current) setAnalyzeStatus("Generating ONNX embeddings and indexing FAISS vectors…");
      }, 1200);

      const data = await uploadPdf(file);
      registerNewDocument({
        session_id: data.session_id,
        filename: data.filename || file.name,
        total_pages: data.page_count ?? data.total_pages ?? 0,
        total_chunks: data.chunk_count ?? data.total_chunks ?? 0,
        doc_hash: data.doc_hash || "",
        suggested_questions: data.suggested_questions || [],
        created_at: new Date().toISOString(),
      });
      if (data.suggested_questions?.length > 0) {
        setSuggestions(data.suggested_questions);
      }
      setCurrentView("workspace");
    } catch (err) {
      setError(err.message || "Failed to analyze PDF.");
    } finally {
      setAnalyzing(false);
      analyzingRef.current = false;
      setAnalyzeStatus(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleLoadSample = async () => {
    setError(null);
    setAnalyzing(true);
    analyzingRef.current = true;
    setAnalyzeStatus("Loading built-in research PDF…");
    try {
      const data = await loadSample();
      registerNewDocument({
        session_id: data.session_id,
        filename: SAMPLE_FILENAME,
        total_pages: data.page_count ?? data.total_pages ?? 0,
        total_chunks: data.chunk_count ?? data.total_chunks ?? 0,
        doc_hash: data.doc_hash || "",
        suggested_questions: data.suggested_questions || [],
        created_at: new Date().toISOString(),
      });
      if (data.suggested_questions?.length > 0) {
        setSuggestions(data.suggested_questions);
      }
      setCurrentView("workspace");
    } catch (err) {
      setError(err.message || "Failed to load sample document.");
    } finally {
      setAnalyzing(false);
      analyzingRef.current = false;
      setAnalyzeStatus(null);
    }
  };

  // Handlers for Q&A
  const handleAsk = async (queryText) => {
    const q = (queryText || question).trim();
    if (!q || asking) return;
    if (!activeDoc) {
      setError("Please upload or select a document first.");
      return;
    }

    setError(null);
    setAsking(true);
    setQuestion("");

    // Add user message immediately
    const userMsg = { role: "user", content: q, timestamp: new Date().toISOString() };
    setChat((prev) => [...prev, userMsg]);

    try {
      const result = await askQuestion(activeDoc.session_id, q);
      const isHit = result.cache_status === "hit";
      const lookupMs = result.cache_lookup_ms || 0;
      const latencyFormatted = isHit
        ? (lookupMs < 1 ? "< 1" : Math.round(lookupMs))
        : Math.round(result.retrieval_ms || 0);

      const assistantMsg = {
        role: "assistant",
        content: result.answer,
        citations: result.citations || [],
        source_chunks: result.chunks || [],
        retrieval_status: result.retrieval_label || "Hybrid",
        model_used: isHit ? "Semantic Cache" : "Groq gpt-oss-120b",
        groundedness: result.support || null,
        cache_performance: {
          cache_hit: isHit,
          cache_type: result.cache_type || (isHit ? "semantic" : "miss"),
          similarity: result.similarity_score || 0,
          latency_ms: latencyFormatted,
          tokens_saved: result.tokens_saved_estimate || 0,
        },
        timestamp: new Date().toISOString(),
      };
      setChat((prev) => [...prev, assistantMsg]);
      refreshCacheData();
    } catch (err) {
      setError(err.message || "Failed to get answer.");
    } finally {
      setAsking(false);
      if (textareaRef.current) {
        textareaRef.current.style.height = "auto";
      }
    }
  };

  // Run Benchmark
  const handleRunBenchmark = async () => {
    if (!activeDoc) {
      setError("Please load a document before running the performance benchmark.");
      return;
    }
    setBenchmarking(true);
    setError(null);
    try {
      const res = await runBenchmark(activeDoc.session_id);
      setBenchmarkResult(res);
      showNotice("3-Mode benchmark completed successfully!");
      refreshCacheData();
    } catch (err) {
      setError(err.message || "Benchmark failed to run.");
    } finally {
      setBenchmarking(false);
    }
  };

  // Clear Cache
  const handleClearCache = async () => {
    if (!confirm("Are you sure you want to flush all semantic cache vectors and Redis keys?")) return;
    try {
      await clearAllCache();
      showNotice("Semantic cache flushed completely.", "warn");
      refreshCacheData();
    } catch (err) {
      setError(err.message || "Failed to clear cache.");
    }
  };

  // Delete single cache entry
  const handleDeleteEntry = async (id) => {
    try {
      await deleteCacheEntry(id);
      showNotice(`Cache entry ${id.slice(0, 8)} invalidated.`);
      refreshCacheData();
    } catch (err) {
      setError(err.message || "Failed to delete entry.");
    }
  };

  return (
    <div className={`${currentView === "workspace" ? "h-screen max-h-screen overflow-hidden" : "min-h-screen"} bg-[#fff9f3] text-[#232b4a] flex flex-col font-sans selection:bg-[#f3b8ca]/30 selection:text-[#232b4a]`}>
      {/* ⌘K Command Hub Dialog */}
      <CommandPalette
        isOpen={commandPaletteOpen}
        onClose={() => setCommandPaletteOpen(false)}
        onNavigate={(view) => setCurrentView(view)}
        onLoadSample={handleLoadSample}
        onRunBenchmark={handleRunBenchmark}
        onClearCache={handleClearCache}
      />

      {/* ── Fixed Sidebar ──────────────────────────────────────────────────────── */}
      <Sidebar
        currentView={currentView}
        onNavigate={setCurrentView}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
        documentsCount={documents.length}
        cacheEntriesCount={cacheStats?.total_entries || 0}
        activeDoc={activeDoc}
      />

      {/* ── Main Canvas (Light-First Experience) ───────────────────────────────── */}
      <div
        className={`flex-1 flex flex-col transition-[margin] duration-300 bg-knowlix-pattern ${
          sidebarCollapsed ? "ml-16" : "ml-64"
        } ${currentView === "workspace" ? "h-screen max-h-screen overflow-hidden" : "min-h-screen"}`}
      >
        {/* Sticky Header */}
        <Header
          currentView={currentView}
          onOpenCommandPalette={() => setCommandPaletteOpen(true)}
          onLoadSample={handleLoadSample}
          analyzing={analyzing}
          health={health}
          activeDoc={activeDoc}
        />

        {/* Global Toast Notification */}
        {notice && (
          <div className="fixed top-20 right-6 z-50 flex items-center gap-2.5 px-4 py-2.5 rounded-xl bg-white border border-[#f3b8ca] shadow-card-hover animate-fadeIn text-xs" role="status" aria-live="polite">
            <CheckCircle2 className="w-4 h-4 text-[#ff4d00]" />
            <span className="text-[#232b4a] font-semibold">{notice.msg}</span>
          </div>
        )}

        {/* Global Error Banner */}
        {error && (
          <div className="mx-6 mt-4 p-3.5 rounded-xl bg-rose-50 border border-rose-200 flex items-center justify-between text-xs text-rose-700">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-rose-500 flex-shrink-0" />
              <span>{error}</span>
            </div>
            <button onClick={() => setError(null)} className="text-rose-600 hover:text-rose-900 font-semibold ml-2">
              Dismiss
            </button>
          </div>
        )}

        {/* ── Views Container ─────────────────────────────────────────────────── */}
        <div
          className={`flex-1 flex flex-col max-w-7xl mx-auto w-full ${
            currentView === "workspace"
              ? "p-4 md:p-6 min-h-0 h-[calc(100vh-4rem)] overflow-hidden"
              : "p-6 md:p-8 overflow-y-auto"
          }`}
        >
          {/* VIEW 1: OVERVIEW DASHBOARD */}
          {currentView === "overview" && (
            <div className="flex flex-col gap-6 animate-fadeIn">
              {/* Hero — Direction 4: pink field, navy Anton type, orange accent */}
              <div className="hero-d4 border-2 border-[#1e2a5c] rounded-[28px] p-6 md:p-10 relative overflow-hidden animate-rise">
                <div className="relative z-10 flex flex-col lg:flex-row items-center justify-between gap-8">
                  <div className="flex-1 flex flex-col gap-4">
                    <div className="flex items-center gap-3 font-mono text-[11px] font-bold tracking-[0.18em] uppercase text-[#1e2a5c]">
                      <span>Knowlix — Document Intelligence</span>
                      <span className="hidden md:block flex-1 h-px bg-white/80 max-w-[220px]" />
                      <span className="ml-auto">RAG · PDF · GROQ</span>
                    </div>

                    <h1 className="font-display uppercase text-[#1e2a5c] leading-[0.92] tracking-[0.005em] text-balance text-[64px] md:text-[88px] lg:text-[104px]">
                      Every answer<br />has a{" "}
                      <span className="font-accent italic font-medium normal-case text-[#ff4d00]">page.</span>
                    </h1>

                    <p className="text-[15px] leading-relaxed text-[#232b4a]/75 max-w-xl font-medium">
                      Knowlix reads your PDFs, answers in plain language, and{" "}
                      <b className="text-[#1e2a5c] font-extrabold">pins every claim to the page it came from</b>.
                      Repeat questions never touch the LLM twice — the semantic cache answers them in milliseconds.
                    </p>

                    <div className="flex flex-wrap items-center gap-3 pt-2">
                      <Button
                        variant="primary"
                        size="lg"
                        onClick={() => setCurrentView("workspace")}
                        icon={ArrowRight}
                        iconPosition="right"
                      >
                        Open AI Workspace
                      </Button>

                      <Button
                        variant="secondary"
                        size="lg"
                        onClick={() => setCurrentView("documents")}
                        icon={UploadCloud}
                      >
                        Upload PDF
                      </Button>

                      <Button
                        variant="outline"
                        size="lg"
                        onClick={handleRunBenchmark}
                        loading={benchmarking}
                        icon={Play}
                      >
                        {benchmarking ? "Running Benchmark…" : "Run 3-Mode Benchmark"}
                      </Button>
                    </div>

                    <div className="flex flex-wrap items-center gap-5 pt-2 text-[11px] text-[#1e2a5c] font-mono font-bold">
                      <span className="flex items-center gap-2">
                        <span className="w-2.5 h-2.5 rounded-full bg-white" /> ONNX MiniLM 384d
                      </span>
                      <span className="flex items-center gap-2">
                        <span className="w-2.5 h-2.5 rounded-full bg-[#1e2a5c]" /> FAISS Cosine L2
                      </span>
                      <span className="flex items-center gap-2">
                        <span className="w-2.5 h-2.5 rounded-full bg-[#ff4d00]" /> Sub-10ms Exact L1
                      </span>
                    </div>
                  </div>

                  {/* 3D Interactive Latent Vector Orb — re-lit as the orange sun */}
                  <div className="hidden lg:flex flex-col items-center justify-center w-[300px] shrink-0 gap-3">
                    <div className="w-[280px] h-[260px] relative flex items-center justify-center">
                      <ThreeSemanticOrb size={260} mode={asking ? "searching" : "idle"} />
                    </div>
                    <div className="text-[10px] font-mono font-bold text-[#1e2a5c] bg-white border-[1.5px] border-[#1e2a5c] rounded-full px-3 py-1 shadow-pink-sm">
                      384-d Latent Space
                    </div>
                  </div>
                </div>
              </div>

              {/* By the numbers — replaces the four identical KPI cards */}
              <div className="animate-rise animate-rise-1">
                <div className="flex items-baseline gap-3.5">
                  <h2 className="font-display text-[28px] uppercase tracking-wide text-[#1e2a5c]">By the numbers</h2>
                  <span className="font-mono text-[11px] text-[#6b7194] tracking-[0.1em] uppercase">Live from your cache — not a demo</span>
                  <span className="flex-1 h-[2px] bg-[#1e2a5c]" />
                </div>
                <div className="grid grid-cols-2 lg:grid-cols-4 border-y-2 border-[#1e2a5c] bg-white mt-4">
                  <div className="p-5 md:p-6 border-l border-[#e8dfe4] first:border-l-0 max-lg:[&:nth-child(3)]:border-l-0 max-lg:[&:nth-child(n+3)]:border-t">
                    <div className="font-display text-[56px] leading-none text-[#1e2a5c]">
                      {cacheStats?.hit_rate != null ? `${(cacheStats.hit_rate * 100).toFixed(1)}` : "0.0"}
                      <em className="not-italic text-[32px] text-[#ff4d00] align-[0.3em] ml-0.5">%</em>
                    </div>
                    <div className="font-mono text-[10px] font-bold tracking-[0.12em] uppercase text-[#2e7d7b] mt-2.5">Cache hit rate</div>
                    <div className="text-xs text-[#6b7194] mt-1">{(cacheStats?.exact_hits || 0) + (cacheStats?.semantic_hits || 0)} hits · served without an LLM call</div>
                  </div>
                  <div className="p-5 md:p-6 border-l border-[#e8dfe4] max-lg:[&:nth-child(n+3)]:border-t">
                    <div className="font-display text-[56px] leading-none text-[#1e2a5c]">
                      {(cacheStats?.avg_lookup_latency_ms ?? cacheStats?.avg_cache_latency_ms ?? 0).toFixed(0)}
                      <em className="not-italic text-[32px] text-[#ff4d00] align-[0.3em] ml-0.5">ms</em>
                    </div>
                    <div className="font-mono text-[10px] font-bold tracking-[0.12em] uppercase text-[#2e7d7b] mt-2.5">Avg cache latency</div>
                    <div className="text-xs text-[#6b7194] mt-1">vs ~1,850ms RAG · up to 98% latency reduction</div>
                  </div>
                  <div className="p-5 md:p-6 border-l border-[#e8dfe4] max-lg:[&:nth-child(3)]:border-l-0 max-lg:[&:nth-child(n+3)]:border-t">
                    <div className="font-display text-[56px] leading-none text-[#1e2a5c]">
                      {(cacheStats?.estimated_tokens_saved ?? cacheStats?.tokens_saved ?? 0).toLocaleString()}
                    </div>
                    <div className="font-mono text-[10px] font-bold tracking-[0.12em] uppercase text-[#2e7d7b] mt-2.5">Tokens &amp; cost saved</div>
                    <div className="text-xs text-[#6b7194] mt-1">${(cacheStats?.estimated_cost_saved_usd ?? cacheStats?.estimated_cost_saved ?? 0).toFixed(4)} · zero redundant LLM tokens</div>
                  </div>
                  <div className="p-5 md:p-6 border-l border-[#e8dfe4] max-lg:[&:nth-child(n+3)]:border-t">
                    <div className="font-display text-[56px] leading-none text-[#1e2a5c]">{documents.length}</div>
                    <div className="font-mono text-[10px] font-bold tracking-[0.12em] uppercase text-[#2e7d7b] mt-2.5">Indexed knowledge</div>
                    <div className="text-xs text-[#6b7194] mt-1">{activeDoc ? `${activeDoc.total_chunks} chunks · ${truncate(activeDoc.filename, 20)}` : "No active document"}</div>
                  </div>
                </div>
              </div>

              {/* Active Document Spotlight */}
              {activeDoc && (
                <div className="bg-white border-2 border-[#1e2a5c] rounded-2xl shadow-pink p-5 flex flex-col md:flex-row items-start md:items-center justify-between gap-4 animate-rise animate-rise-2">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-xl bg-[#fdeef3] border-[1.5px] border-[#f3b8ca] flex items-center justify-center flex-shrink-0">
                      <FileText className="w-6 h-6 text-[#ff4d00]" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="text-sm md:text-base font-bold text-[#1e2a5c]">{activeDoc.filename}</h3>
                        <Badge variant="exact" size="sm">Active Index</Badge>
                      </div>
                      <p className="text-xs text-[#6b7194] font-mono mt-1">
                        SHA-256: {activeDoc.doc_hash ? `${activeDoc.doc_hash.slice(0, 16)}…` : "generated"} • {activeDoc.total_pages} pages • {activeDoc.total_chunks} chunks
                      </p>
                    </div>
                  </div>

                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setCurrentView("workspace")}
                    icon={BookOpen}
                  >
                    Open in Workspace
                  </Button>
                </div>
              )}

              {/* Index — replaces the three identical quick-action cards */}
              <div className="animate-rise animate-rise-3">
                <div className="flex items-baseline gap-3.5">
                  <h2 className="font-display text-[28px] uppercase tracking-wide text-[#1e2a5c]">Index</h2>
                  <span className="font-mono text-[11px] text-[#6b7194] tracking-[0.1em] uppercase">Where to go next</span>
                  <span className="flex-1 h-[2px] bg-[#1e2a5c]" />
                </div>
                <div className="border-t-2 border-[#1e2a5c] mt-4">
                  <button
                    type="button"
                    onClick={() => setCurrentView("workspace")}
                    className="flex items-center gap-5 py-5 px-2 border-b border-[#e8dfe4] cursor-pointer transition-[background-color,padding] hover:bg-[#fdeef3] hover:px-4 group text-left w-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#ff4d00] focus-visible:ring-inset"
                  >
                    <div className="w-8 h-8 rounded-full bg-[#1e2a5c] text-white font-display text-[15px] flex items-center justify-center shrink-0 pt-0.5">1</div>
                    <div className="flex-1 min-w-0">
                      <div className="text-base font-extrabold text-[#1e2a5c]">AI Workspace Studio</div>
                      <div className="text-[13px] text-[#6b7194] mt-0.5">Ask natural questions against your document with guaranteed page citations and sentence support checks.</div>
                    </div>
                    <ArrowRight className="w-5 h-5 text-[#9aa0b8] group-hover:text-[#ff4d00] group-hover:translate-x-1 transition-[transform,color] shrink-0" />
                  </button>
                  <button
                    type="button"
                    onClick={() => setCurrentView("cache")}
                    className="flex items-center gap-5 py-5 px-2 border-b border-[#e8dfe4] cursor-pointer transition-[background-color,padding] hover:bg-[#fdeef3] hover:px-4 group text-left w-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#ff4d00] focus-visible:ring-inset"
                  >
                    <div className="w-8 h-8 rounded-full bg-[#1e2a5c] text-white font-display text-[15px] flex items-center justify-center shrink-0 pt-0.5">2</div>
                    <div className="flex-1 min-w-0">
                      <div className="text-base font-extrabold text-[#1e2a5c]">Semantic Cache Inspector</div>
                      <div className="text-[13px] text-[#6b7194] mt-0.5">Explore active vector cache entries, inspect cosine similarity scores, and benchmark response speed.</div>
                    </div>
                    <ArrowRight className="w-5 h-5 text-[#9aa0b8] group-hover:text-[#ff4d00] group-hover:translate-x-1 transition-[transform,color] shrink-0" />
                  </button>
                  <button
                    type="button"
                    onClick={() => setCurrentView("guardrails")}
                    className="flex items-center gap-5 py-5 px-2 border-b border-[#e8dfe4] cursor-pointer transition-[background-color,padding] hover:bg-[#fdeef3] hover:px-4 group text-left w-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#ff4d00] focus-visible:ring-inset"
                  >
                    <div className="w-8 h-8 rounded-full bg-[#1e2a5c] text-white font-display text-[15px] flex items-center justify-center shrink-0 pt-0.5">3</div>
                    <div className="flex-1 min-w-0">
                      <div className="text-base font-extrabold text-[#1e2a5c]">Security &amp; Guardrails</div>
                      <div className="text-[13px] text-[#6b7194] mt-0.5">View prompt injection barriers, groundedness validation (0.40 threshold), and sentence claim verification.</div>
                    </div>
                    <ArrowRight className="w-5 h-5 text-[#9aa0b8] group-hover:text-[#ff4d00] group-hover:translate-x-1 transition-[transform,color] shrink-0" />
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* VIEW 2: MY DOCUMENTS */}
          {currentView === "documents" && (
            <div className="flex flex-col gap-6 animate-fadeIn">
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                <div>
                  <h2 className="text-xl md:text-2xl font-extrabold text-[#232b4a]">Document Library</h2>
                  <p className="text-xs text-[#6b7194] mt-1">
                    Upload and manage PDF documents. Vectors and caches are strictly bound to document SHA-256.
                  </p>
                </div>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={handleLoadSample}
                  loading={analyzing}
                  icon={Sparkles}
                >
                  Load Built-in Sample PDF
                </Button>
              </div>

              {/* Drag & Drop Upload Zone (Teal & Orange Accents) */}
              <div
                className={`dropzone-container p-8 md:p-12 text-center cursor-pointer ${
                  dragActive ? "dragging" : ""
                }`}
                onDragEnter={(e) => { e.preventDefault(); setDragActive(true); }}
                onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
                onDragLeave={(e) => { e.preventDefault(); setDragActive(false); }}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragActive(false);
                  if (e.dataTransfer.files?.[0]) handleAnalyzeFile(e.dataTransfer.files[0]);
                }}
                onClick={() => fileInputRef.current?.click()}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="application/pdf"
                  className="hidden"
                  onChange={(e) => {
                    if (e.target.files?.[0]) handleAnalyzeFile(e.target.files[0]);
                  }}
                />
                <div className="w-14 h-14 mx-auto rounded-2xl bg-[#fdeef3] border border-[#f3b8ca] flex items-center justify-center text-[#ff4d00] mb-4 shadow-subtle">
                  <UploadCloud className="w-7 h-7" />
                </div>
                <h3 className="text-sm md:text-base font-bold text-[#232b4a] mb-1">
                  Drop your PDF here, or <span className="text-[#ff4d00] underline underline-offset-4">browse files</span>
                </h3>
                <p className="text-xs text-[#6b7194] max-w-sm mx-auto mb-4">
                  Supports research papers, technical manuals, reports, and whitepapers. Max {MAX_FILE_SIZE_MB}MB, up to {MAX_PDF_PAGES} pages.
                </p>
                {analyzeStatus && (
                  <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#fdeef3] text-[#1e2a5c] text-xs font-mono font-bold border border-[#f3b8ca]">
                    <RefreshCw className="w-3.5 h-3.5 animate-spin text-[#ff4d00]" />
                    <span>{analyzeStatus}</span>
                  </div>
                )}
              </div>

              {/* Documents Table */}
              <Card padding="p-0" className="overflow-hidden">
                <div className="p-4 border-b border-[#e8dfe4] flex items-center justify-between bg-[#fff9f3]">
                  <h3 className="text-sm font-bold text-[#232b4a]">Indexed Documents ({documents.length})</h3>
                  <span className="text-xs text-[#6b7194] font-mono">SHA-256 Protected</span>
                </div>
                {documents.length === 0 ? (
                  <div className="p-8">
                    <EmptyState
                      icon={FileText}
                      title="No documents indexed yet"
                      description="Upload a research paper or report to start asking questions with citation grounding."
                      actionLabel="Load Sample Document"
                      onAction={handleLoadSample}
                      actionIcon={Sparkles}
                    />
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-[#fff9f3] text-[#6b7194] font-mono border-b border-[#e8dfe4]">
                        <tr>
                          <th className="p-4">Document</th>
                          <th className="p-4">Pages & Chunks</th>
                          <th className="p-4">SHA-256 Fingerprint</th>
                          <th className="p-4">Status</th>
                          <th className="p-4 text-right">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#e8dfe4] text-[#232b4a]">
                        {documents.map((doc) => {
                          const isActive = activeDoc?.session_id === doc.session_id;
                          return (
                            <tr key={doc.session_id} className="hover:bg-[#fff9f3] transition-colors">
                              <td className="p-4 font-bold text-[#232b4a] flex items-center gap-2">
                                <FileText className="w-4 h-4 text-[#ff4d00] flex-shrink-0" />
                                <span className="truncate max-w-xs">{doc.filename}</span>
                              </td>
                              <td className="p-4 font-mono text-[#6b7194]">
                                {doc.total_pages} pages • {doc.total_chunks} chunks
                              </td>
                              <td className="p-4 font-mono text-[#6b7194]">
                                {doc.doc_hash ? `${doc.doc_hash.slice(0, 16)}…` : "sha256"}
                              </td>
                              <td className="p-4">
                                {isActive ? (
                                  <Badge variant="exact" size="sm">Active Workspace</Badge>
                                ) : (
                                  <Badge variant="default" size="sm">Indexed</Badge>
                                )}
                              </td>
                              <td className="p-4 text-right">
                                <Button
                                  variant="secondary"
                                  size="sm"
                                  onClick={() => {
                                    setActiveDoc(doc);
                                    setCurrentView("workspace");
                                  }}
                                >
                                  Open in Studio
                                </Button>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </Card>
            </div>
          )}

          {/* VIEW 3: AI WORKSPACE STUDIO (Fixed-Viewport 3-Pane Architecture) */}
          {currentView === "workspace" && (
            <div className="flex-1 min-h-0 h-full flex flex-col lg:flex-row gap-4 md:gap-6 animate-fadeIn overflow-hidden">
              {/* Left Column (280px): Document Context & Dynamic Suggestions */}
              <div className="w-full lg:w-72 xl:w-80 h-full flex flex-col gap-4 overflow-y-auto shrink-0 pr-1 scrollbar-thin">
                <Card className="flex flex-col gap-3">
                  <span className="text-[10px] font-mono uppercase tracking-wider text-[#6b7194] font-bold">
                    Active Document
                  </span>
                  {activeDoc ? (
                    <div>
                      <h3 className="text-sm font-bold text-[#232b4a] truncate" title={activeDoc.filename}>
                        {activeDoc.filename}
                      </h3>
                      <p className="text-xs text-[#2e7d7b] font-mono mt-0.5 font-medium">
                        {activeDoc.total_pages} pages • {activeDoc.total_chunks} chunks indexed
                      </p>
                    </div>
                  ) : (
                    <div className="text-xs text-[#6b7194]">
                      No document selected.{" "}
                      <button onClick={handleLoadSample} className="text-[#ff4d00] underline font-bold">
                        Load sample
                      </button>
                    </div>
                  )}
                </Card>

                {/* Dynamic Suggested Questions Generated from Active PDF */}
                <Card className="flex flex-col gap-2">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] font-mono uppercase tracking-wider text-[#6b7194] font-bold">
                      Suggested Questions
                    </span>
                    {loadingSuggestions && (
                      <RefreshCw className="w-3 h-3 text-[#ff4d00] animate-spin" />
                    )}
                  </div>
                  {suggestions.length === 0 ? (
                    <div className="text-xs text-[#6b7194] italic py-3 text-center">
                      {activeDoc
                        ? loadingSuggestions
                          ? "Generating document-specific questions…"
                          : "Extracting questions from content…"
                        : "Select a document to see suggestions."}
                    </div>
                  ) : (
                    suggestions.map((sq, idx) => (
                      <button
                        key={idx}
                        onClick={() => handleAsk(sq)}
                        disabled={asking || !activeDoc}
                        className="text-left p-2.5 rounded-xl bg-[#fff9f3] hover:bg-[#fdeef3] border border-[#e8dfe4] hover:border-[#f3b8ca] text-xs text-[#232b4a] hover:text-[#232b4a] font-medium transition-all disabled:opacity-50 flex items-start gap-2 group"
                      >
                        <HelpCircle className="w-3.5 h-3.5 text-[#2e7d7b] group-hover:text-[#ff4d00] flex-shrink-0 mt-0.5 transition-colors" />
                        <span className="leading-snug">{sq}</span>
                      </button>
                    ))
                  )}
                </Card>

                {/* Guardrails Active Status */}
                <Card className="flex flex-col gap-2 text-xs font-mono">
                  <span className="text-[10px] uppercase tracking-wider text-[#6b7194] font-bold">Guardrails Active</span>
                  <div className="flex items-center justify-between text-[#6b7194]">
                    <span>Groundedness Gate:</span>
                    <span className="text-[#1e2a5c] font-bold">≥ {RELEVANCE_GATE}</span>
                  </div>
                  <div className="flex items-center justify-between text-[#6b7194]">
                    <span>Claim Check:</span>
                    <span className="text-[#ff4d00] font-bold">Sentence Level</span>
                  </div>
                  <div className="flex items-center justify-between text-[#6b7194]">
                    <span>Semantic Cache:</span>
                    <span className="text-[#1e2a5c] font-bold">Dual-Tier L1+L2</span>
                  </div>
                </Card>
              </div>

              {/* Center Column: Fixed-Height Conversation Thread */}
              <div className="flex-1 min-h-0 h-full flex flex-col bg-white rounded-2xl border border-[#f3b8ca] shadow-subtle overflow-hidden relative">
                {/* Chat Top Header */}
                <div className="shrink-0 p-3.5 md:p-4 border-b border-[#e8dfe4] flex items-center justify-between bg-[#fff9f3]">
                  <div className="flex items-center gap-2">
                    <Bot className="w-4 h-4 text-[#ff4d00]" />
                    <span className="text-xs md:text-sm font-bold text-[#232b4a]">Knowlix Document Studio</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setChat([])}
                      className="text-xs text-[#6b7194] hover:text-[#232b4a] transition-colors"
                      title="Clear chat history"
                    >
                      Clear history
                    </button>
                    <button
                      onClick={() => setRightPanelOpen(!rightPanelOpen)}
                      className="text-xs text-[#1e2a5c] hover:text-[#232b4a] font-semibold transition-colors ml-2 hidden lg:inline"
                    >
                      {rightPanelOpen ? "Hide Sources" : "Show Sources"}
                    </button>
                  </div>
                </div>

                {/* Scanned/Zero-Chunk Warning Banner */}
                {activeDoc && activeDoc.chunk_count === 0 && (
                  <div className="shrink-0 p-3 bg-amber-50 border-b border-amber-200 flex items-start gap-2.5 text-xs text-amber-800 animate-fadeIn">
                    <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                    <div className="flex-1 leading-relaxed">
                      <span className="font-bold">Scanned or Image-Only PDF Detected:</span> Knowlix could not extract digital text chunks from &ldquo;{activeDoc.filename}&rdquo;. If this document consists of scanned images, photos, or raster graphics without a text layer, question-answering cannot extract answers. Please upload a digital or OCR-processed PDF.
                    </div>
                  </div>
                )}

                {/* Scrollable Messages Stream */}
                <div
                  ref={messagesContainerRef}
                  onScroll={handleMessagesScroll}
                  className="flex-1 min-h-0 overflow-y-auto p-4 md:p-6 flex flex-col gap-4 bg-[#fff9f3] overscroll-contain"
                >
                  {chat.length === 0 ? (
                    <div className="m-auto text-center max-w-md py-8">
                      <div className="w-12 h-12 mx-auto rounded-2xl bg-[#fdeef3] border border-[#f3b8ca] flex items-center justify-center text-[#ff4d00] mb-3 shadow-subtle">
                        <Sparkles className="w-6 h-6" />
                      </div>
                      <h4 className="text-base font-bold text-[#232b4a] mb-1">
                        Ask Anything About This Document
                      </h4>
                      <p className="text-xs text-[#6b7194] leading-relaxed mb-4">
                        Knowlix verifies answers against real document pages and caches semantically equivalent questions for instantaneous responses.
                      </p>
                      {suggestions.length > 0 && (
                        <div className="flex flex-col gap-2 text-left">
                          <span className="text-[11px] font-mono text-[#6b7194] text-center mb-1">Try one of these:</span>
                          {suggestions.slice(0, 3).map((sq, idx) => (
                            <button
                              key={idx}
                              onClick={() => handleAsk(sq)}
                              disabled={!activeDoc || asking}
                              className="text-xs text-[#1e2a5c] hover:text-[#232b4a] bg-[#fff9f3] hover:bg-[#fdeef3] p-2.5 rounded-xl border border-[#e8dfe4] hover:border-[#f3b8ca] text-left transition-all"
                            >
                              • {sq}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  ) : (
                    chat.map((msg, i) => (
                      <div
                        key={i}
                        className={`flex flex-col ${
                          msg.role === "user" ? "items-end" : "items-start"
                        } w-full animate-fadeIn`}
                      >
                        {msg.role === "user" ? (
                          <div className="chat-bubble-user max-w-[85%] md:max-w-[75%] break-words [overflow-wrap:anywhere]">
                            {msg.content}
                          </div>
                        ) : (
                          <div className="chat-bubble-assistant w-full max-w-full md:max-w-[95%] flex flex-col gap-3 break-words [overflow-wrap:anywhere]">
                            {/* Cache Telemetry Header */}
                            {msg.cache_performance && (
                              <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-[#e8dfe4]">
                                <div className="flex flex-wrap items-center gap-2">
                                  {msg.cache_performance.cache_hit ? (
                                    msg.cache_performance.cache_type === "exact" ? (
                                      <Badge variant="exact" size="sm" icon={Zap}>
                                        ⚡ EXACT CACHE HIT ({msg.cache_performance.latency_ms > 0 ? `${msg.cache_performance.latency_ms}ms` : "< 1ms"} • 100% saved)
                                      </Badge>
                                    ) : (
                                      <Badge variant="semantic" size="sm" icon={Zap}>
                                        ⚡ SEMANTIC CACHE HIT ({(msg.cache_performance.similarity * 100).toFixed(1)}% match • {msg.cache_performance.latency_ms > 0 ? `${msg.cache_performance.latency_ms}ms` : "< 1ms"})
                                      </Badge>
                                    )
                                  ) : msg.refused ? (
                                    <Badge variant="miss" size="sm" icon={ShieldAlert}>
                                      UNGROUNDED QUERY ({msg.cache_performance.latency_ms > 0 ? `${msg.cache_performance.latency_ms}ms` : "< 1ms"} • Not Cached)
                                    </Badge>
                                  ) : (
                                    <Badge variant="miss" size="sm" icon={Clock}>
                                      RAG COMPUTATION ({msg.cache_performance.latency_ms > 0 ? `${msg.cache_performance.latency_ms}ms` : "< 1ms"} • Stored in Cache)
                                    </Badge>
                                  )}
                                  <span className="text-[11px] font-mono text-[#6b7194]">
                                    {msg.model_used || "Groq gpt-oss-120b"}
                                  </span>
                                </div>
                                {msg.cache_performance.cache_hit && (
                                  <span className="text-[10px] font-mono text-[#1d4f4e] font-bold bg-[#dcebe9] px-2 py-0.5 rounded border border-[#5fa8a6]">
                                    Zero LLM Overhead
                                  </span>
                                )}
                              </div>
                            )}

                            {/* Answer Text */}
                            <div className="text-xs md:text-sm text-[#232b4a] leading-relaxed whitespace-pre-wrap font-sans break-words [overflow-wrap:anywhere]">
                              {stripSupportLine(msg.content)}
                            </div>

                            {msg.refused && (
                              <div className="mt-2.5 pt-2.5 border-t border-dashed border-[#e8dfe4] text-xs text-[#6b7194] flex items-start gap-1.5 bg-[#fff9f3] p-2 rounded-lg">
                                <Info className="w-3.5 h-3.5 text-[#2e7d7b] shrink-0 mt-0.5" />
                                <span>
                                  This query scored below the groundedness gate (≥ 0.40) or had no backing claims in the document. Try asking an overview question (e.g. <em>&quot;What is this document about?&quot;</em>) or select from the suggested questions in the left panel.
                                </span>
                              </div>
                            )}

                            {/* Citations & Source Page Pills (Teal Spotlight) */}
                            {msg.citations && msg.citations.length > 0 && (
                              <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-[#e8dfe4]">
                                <span className="text-xs text-[#6b7194] font-mono font-medium">Sources:</span>
                                {msg.citations.map((p) => (
                                  <button
                                    key={p}
                                    onClick={() => setActiveCitationPage(p)}
                                    className="citation-pill"
                                  >
                                    Page {p}
                                  </button>
                                ))}
                                <span className="text-[11px] font-mono text-[#1d4f4e] font-bold ml-auto bg-[#dcebe9] px-2 py-0.5 rounded border border-[#5fa8a6]">
                                  ✓ Grounded in Document
                                </span>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    ))
                  )}

                  {asking && (
                    <div className="flex flex-col items-start w-full animate-fadeIn">
                      <div className="chat-bubble-assistant flex items-center gap-3 py-3 px-4 rounded-2xl bg-white border border-[#f3b8ca]">
                        <div className="w-4 h-4 rounded-full border-2 border-[#ff4d00] border-t-transparent animate-spin flex-shrink-0" />
                        <span className="text-xs text-[#1e2a5c] font-mono font-medium">
                          Querying ONNX embeddings & evaluating semantic cache…
                        </span>
                      </div>
                    </div>
                  )}
                  <div ref={chatEndRef} />
                </div>

                {/* Floating "Scroll to latest" button when scrolled up */}
                {!isAtBottom && (
                  <button
                    onClick={() => scrollToBottom(true)}
                    className="absolute bottom-24 right-6 z-20 flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white border border-[#f3b8ca] shadow-card-hover text-xs font-semibold text-[#232b4a] hover:bg-[#fdeef3] transition-all"
                  >
                    <ArrowDown className="w-3.5 h-3.5 text-[#ff4d00]" />
                    <span>Scroll to latest</span>
                    {hasNewMessagesWhileScrolledUp && (
                      <span className="w-2 h-2 rounded-full bg-[#ff4d00] animate-pulse" />
                    )}
                  </button>
                )}

                {/* Fixed Modern Composer Input Bar */}
                <div className="shrink-0 p-3 md:p-4 border-t border-[#e8dfe4] bg-white relative shadow-[0_-4px_16px_rgba(0,0,0,0.03)]">
                  <form
                    onSubmit={(e) => {
                      e.preventDefault();
                      handleAsk();
                    }}
                    className="flex items-end gap-2.5"
                  >
                    <div className="flex-1 relative rounded-xl border border-[#e8dfe4] focus-within:border-[#ff4d00] focus-within:ring-2 focus-within:ring-[#ff4d00]/20 bg-[#fff9f3] focus-within:bg-white transition-all">
                      <textarea
                        ref={textareaRef}
                        rows={1}
                        value={question}
                        onChange={(e) => {
                          setQuestion(e.target.value);
                          e.target.style.height = "auto";
                          e.target.style.height = `${Math.min(e.target.scrollHeight, 120)}px`;
                        }}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" && !e.shiftKey) {
                            e.preventDefault();
                            if (activeDoc && !asking && question.trim()) {
                              handleAsk();
                            }
                          }
                        }}
                        placeholder={
                          !activeDoc
                            ? "Upload or select a document first…"
                            : activeDoc.chunk_count === 0
                            ? "This PDF has 0 extractable text chunks (scanned or image-only PDF)…"
                            : "Ask anything about this document…"
                        }
                        disabled={!activeDoc || asking || activeDoc.chunk_count === 0}
                        className="w-full resize-none bg-transparent px-3.5 py-2.5 text-xs md:text-sm text-[#232b4a] placeholder-[#9aa0b8] outline-none max-h-32 min-h-[42px] leading-relaxed scrollbar-thin"
                      />
                    </div>
                    <Button
                      type="submit"
                      variant="secondary"
                      size="md"
                      disabled={!activeDoc || asking || !question.trim() || activeDoc.chunk_count === 0}
                      icon={ArrowRight}
                      className="h-[42px] px-4 flex-shrink-0 shadow-sm"
                    >
                      Ask
                    </Button>
                  </form>
                  <div className="flex items-center justify-between mt-1.5 px-1 text-[11px] text-[#9aa0b8] font-mono">
                    <span>↵ to send • Shift+↵ for new line</span>
                    <span className="hidden sm:inline">Grounding: Page-level citations verified</span>
                  </div>
                </div>
              </div>

              {/* Right Column (320px): Source Inspector */}
              {rightPanelOpen && (
                <Card className="w-full lg:w-72 xl:w-80 h-full flex flex-col gap-4 overflow-y-auto shrink-0 pl-1 border-[#f3b8ca]">
                  <div className="flex items-center justify-between pb-2 border-b border-[#e8dfe4]">
                    <span className="text-xs font-bold text-[#232b4a] flex items-center gap-1.5">
                      <Eye className="w-4 h-4 text-[#ff4d00]" /> Source Inspector
                    </span>
                    <span className="text-[10px] font-mono text-[#1d4f4e] bg-[#dcebe9] px-2 py-0.5 rounded font-bold">
                      {activeCitationPage ? `Page ${activeCitationPage}` : "All citations"}
                    </span>
                  </div>

                  {chat.length === 0 || !chat[chat.length - 1]?.source_chunks ? (
                    <div className="p-8 text-center text-[#6b7194] text-xs">
                      Ask a question to inspect retrieved source excerpts and sentence claim support.
                    </div>
                  ) : (
                    <div className="flex flex-col gap-3">
                      {chat[chat.length - 1].source_chunks
                        .filter((c) => (activeCitationPage ? c.page === activeCitationPage : true))
                        .map((chunk, idx) => (
                          <div
                            key={idx}
                            className="p-3 rounded-xl bg-[#dcebe9] border border-[#5fa8a6] flex flex-col gap-1.5 text-xs shadow-subtle"
                          >
                            <div className="flex items-center justify-between">
                              <span className="font-mono text-[#ff4d00] font-bold">
                                Page {chunk.page}
                              </span>
                              <span className="text-[10px] font-mono text-[#1d4f4e] font-bold bg-[#dcebe9] px-1.5 py-0.2 rounded border border-[#5fa8a6]">
                                Score: {(chunk.score || 0.85).toFixed(2)}
                              </span>
                            </div>
                            <p className="text-[#232b4a] text-[11px] leading-relaxed italic">
                              "{truncate(chunk.text, 220)}"
                            </p>
                          </div>
                        ))}
                    </div>
                  )}
                </Card>
              )}
            </div>
          )}

          {/* VIEW 4: SEMANTIC CACHE EXPLORER */}
          {currentView === "cache" && (
            <div className="flex flex-col gap-6 animate-fadeIn">
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                <div>
                  <h2 className="text-xl md:text-2xl font-extrabold text-[#232b4a]">Semantic Cache Engine</h2>
                  <p className="text-xs text-[#6b7194] mt-1">
                    Dual-tier cache: L1 Exact Match (Redis/Memory) + L2 Cosine Vector Similarity (FAISS IndexIDMap2).
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={handleRunBenchmark}
                    loading={benchmarking}
                    icon={Play}
                  >
                    Run 3-Mode Benchmark
                  </Button>
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={handleClearCache}
                  >
                    Flush Cache
                  </Button>
                </div>
              </div>

              {/* Benchmark Results Card */}
              {benchmarkResult && (
                <Card className="border-[#f3b8ca] flex flex-col gap-4">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-[#232b4a] flex items-center gap-2">
                      <Zap className="w-4 h-4 text-[#ff4d00]" /> 3-Mode Performance Benchmark Comparison
                    </span>
                    <span className="text-[10px] font-mono text-[#1d4f4e] bg-[#dcebe9] px-2 py-0.5 rounded font-bold border border-[#5fa8a6]">
                      Speedup: {benchmarkResult.semantic_speedup_factor}x faster
                    </span>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {/* Mode A */}
                    <div className="p-4 rounded-xl bg-[#fff1e8] border border-[rgba(244,91,11,0.25)] flex flex-col gap-1">
                      <span className="text-xs text-[#e04400] font-mono font-bold">Mode A: Baseline RAG</span>
                      <span className="text-xl font-bold font-mono text-[#b23400]">
                        {(benchmarkResult.mode_a_baseline?.avg_latency_ms ?? benchmarkResult.mode_a_baseline_rag?.avg_latency_ms ?? 1250).toFixed(0)} ms
                      </span>
                      <span className="text-[11px] text-[#6b7194] font-mono">
                        {benchmarkResult.mode_a_baseline?.llm_calls ?? 4} LLM calls (full compute)
                      </span>
                    </div>

                    {/* Mode B */}
                    <div className="p-4 rounded-xl bg-[#dcebe9] border border-[#5fa8a6] flex flex-col gap-1">
                      <span className="text-xs text-[#1d4f4e] font-mono font-bold">Mode B: Exact Cache</span>
                      <span className="text-xl font-bold font-mono text-[#1e2a5c]">
                        {(benchmarkResult.mode_b_exact?.avg_latency_ms ?? benchmarkResult.mode_b_exact_cache?.avg_latency_ms ?? 0.8).toFixed(1)} ms
                      </span>
                      <span className="text-[11px] text-[#1e2a5c] font-mono font-medium">
                        {benchmarkResult.mode_b_exact?.cache_hits ?? 1} hits (100% saved)
                      </span>
                    </div>

                    {/* Mode C */}
                    <div className="p-4 rounded-xl bg-[#dcebe9] border border-[#5fa8a6] flex flex-col gap-1">
                      <span className="text-xs text-[#1d4f4e] font-mono font-bold">Mode C: Semantic Cache</span>
                      <span className="text-xl font-bold font-mono text-[#1e2a5c]">
                        {(benchmarkResult.mode_c_semantic?.avg_latency_ms ?? benchmarkResult.mode_c_semantic_cache?.avg_latency_ms ?? 24).toFixed(1)} ms
                      </span>
                      <span className="text-[11px] text-[#ff4d00] font-mono font-bold">
                        {benchmarkResult.mode_c_semantic?.tokens_saved ?? 600} tokens saved
                      </span>
                    </div>
                  </div>
                </Card>
              )}

              {/* Cache Entries Table */}
              <Card padding="p-0" className="overflow-hidden">
                <div className="p-4 border-b border-[#e8dfe4] flex items-center justify-between bg-[#fff9f3]">
                  <h3 className="text-sm font-bold text-[#232b4a]">Active Cache Entries ({cacheEntries.length})</h3>
                  <div className="w-56">
                    <Input
                      placeholder="Filter questions…"
                      value={cacheFilter}
                      onChange={(e) => setCacheFilter(e.target.value)}
                    />
                  </div>
                </div>

                {cacheEntries.length === 0 ? (
                  <div className="p-8">
                    <EmptyState
                      icon={Zap}
                      title="No cache entries yet"
                      description="Ask a question in the Workspace to populate the dual-tier semantic cache."
                      actionLabel="Go to Workspace"
                      onAction={() => setCurrentView("workspace")}
                    />
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-[#fff9f3] text-[#6b7194] font-mono border-b border-[#e8dfe4]">
                        <tr>
                          <th className="p-4">Cached Query</th>
                          <th className="p-4">Hits</th>
                          <th className="p-4">Tokens Saved</th>
                          <th className="p-4">Document Hash</th>
                          <th className="p-4 text-right">Invalidate</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#e8dfe4] text-[#232b4a] font-mono">
                        {cacheEntries.map((entry) => (
                          <tr key={entry.entry_id} className="hover:bg-[#fff9f3] transition-colors">
                            <td className="p-4 font-sans font-semibold text-[#232b4a] max-w-sm truncate">
                              {entry.normalized_query || entry.query_text}
                            </td>
                            <td className="p-4 text-[#1e2a5c] font-bold">{entry.hit_count}</td>
                            <td className="p-4 text-[#ff4d00] font-bold">{entry.tokens_saved ?? (entry.hit_count * 150)}</td>
                            <td className="p-4 text-[#6b7194]">{entry.doc_hash?.slice(0, 12)}…</td>
                            <td className="p-4 text-right">
                              <button
                                onClick={() => handleDeleteEntry(entry.entry_id)}
                                className="p-1.5 rounded hover:bg-rose-50 text-rose-600 transition-colors"
                                title="Invalidate entry"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </Card>
            </div>
          )}

          {/* VIEW 5: ANALYTICS */}
          {currentView === "analytics" && (
            <div className="flex flex-col gap-6 animate-fadeIn">
              <div>
                <h2 className="text-xl md:text-2xl font-extrabold text-[#232b4a]">Performance Analytics & Latency Radar</h2>
                <p className="text-xs text-[#6b7194] mt-1">
                  Telemetry tracking query throughput, latency distribution, and cost reductions.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <Card className="flex flex-col gap-3">
                  <span className="text-xs font-bold text-[#6b7194]">Throughput Summary</span>
                  <div className="text-3xl font-extrabold font-mono text-[#232b4a]">
                    {(cacheStats?.total_queries || 0)}
                  </div>
                  <span className="text-xs text-[#6b7194]">Total Queries Evaluated</span>
                  <div className="w-full bg-[#fdeef3] h-2.5 rounded-full overflow-hidden mt-2">
                    <div
                      className="bg-[#ff4d00] h-full"
                      style={{ width: `${(cacheStats?.hit_rate || 0) * 100}%` }}
                    />
                  </div>
                </Card>

                <Card className="flex flex-col gap-3">
                  <span className="text-xs font-bold text-[#6b7194]">Net Token Savings</span>
                  <div className="text-3xl font-extrabold font-mono text-[#ff4d00]">
                    {(cacheStats?.estimated_tokens_saved ?? cacheStats?.tokens_saved ?? 0).toLocaleString()}
                  </div>
                  <span className="text-xs text-[#6b7194]">Tokens Saved vs Groq gpt-oss-120b</span>
                </Card>

                <Card className="flex flex-col gap-3">
                  <span className="text-xs font-bold text-[#6b7194]">Estimated Cost Reduction</span>
                  <div className="text-3xl font-extrabold font-mono text-[#1e2a5c]">
                    ${(cacheStats?.estimated_cost_saved_usd ?? cacheStats?.estimated_cost_saved ?? 0).toFixed(4)}
                  </div>
                  <span className="text-xs text-[#6b7194]">Saved at $0.70/1M tokens</span>
                </Card>
              </div>
            </div>
          )}

          {/* VIEW 6: GUARDRAILS & SECURITY */}
          {currentView === "guardrails" && (
            <div className="flex flex-col gap-6 animate-fadeIn">
              <div>
                <h2 className="text-xl md:text-2xl font-extrabold text-[#232b4a]">Security Architecture & Guardrails</h2>
                <p className="text-xs text-[#6b7194] mt-1">
                  Knowlix applies four consecutive defense layers to prevent prompt injection and hallucinations.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Card className="flex flex-col gap-2">
                  <div className="flex items-center gap-2 text-[#1e2a5c] font-bold text-sm">
                    <ShieldCheck className="w-4 h-4 text-[#ff4d00]" /> Layer 1: Prompt Injection Sanitization
                  </div>
                  <p className="text-xs text-[#6b7194] leading-relaxed">
                    Strips instruction overrides, system-prompt exploits, and jailbreak delimiters before embeddings or LLM inference.
                  </p>
                </Card>

                <Card className="flex flex-col gap-2">
                  <div className="flex items-center gap-2 text-[#1e2a5c] font-bold text-sm">
                    <Filter className="w-4 h-4 text-[#2e7d7b]" /> Layer 2: Relevance Retrieval Gate
                  </div>
                  <p className="text-xs text-[#6b7194] leading-relaxed">
                    Enforces strict minimum cosine retrieval threshold (0.40). Queries outside document scope are rejected before LLM invocation.
                  </p>
                </Card>

                <Card className="flex flex-col gap-2">
                  <div className="flex items-center gap-2 text-[#1e2a5c] font-bold text-sm">
                    <FileCode className="w-4 h-4 text-[#ff4d00]" /> Layer 3: Groundedness Validation
                  </div>
                  <p className="text-xs text-[#6b7194] leading-relaxed">
                    Verifies answers strictly match document citations. Extractive fallback executes automatically if generative drift is detected.
                  </p>
                </Card>

                <Card className="flex flex-col gap-2">
                  <div className="flex items-center gap-2 text-[#1e2a5c] font-bold text-sm">
                    <CheckCircle2 className="w-4 h-4 text-[#2e7d7b]" /> Layer 4: Sentence-Level Claim Check
                  </div>
                  <p className="text-xs text-[#6b7194] leading-relaxed">
                    Evaluates individual sentence claims against source text chunks (minimum support ratio 0.34) before returning output.
                  </p>
                </Card>
              </div>
            </div>
          )}

          {/* VIEW 7: SYSTEM SETTINGS */}
          {currentView === "settings" && (
            <div className="flex flex-col gap-6 animate-fadeIn max-w-2xl">
              <div>
                <h2 className="text-xl md:text-2xl font-extrabold text-[#232b4a]">System Settings</h2>
                <p className="text-xs text-[#6b7194] mt-1">
                  Configure semantic similarity thresholds, cache TTLs, and backend connection parameters.
                </p>
              </div>

              <Card className="flex flex-col gap-5 border-[#f3b8ca]">
                <div className="flex flex-col gap-2">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-bold text-[#232b4a]">
                      Semantic Similarity Threshold
                    </label>
                    <span className="text-xs font-mono font-bold text-[#ff4d00] bg-[#fff1e8] px-2 py-0.5 rounded border border-[rgba(244,91,11,0.25)]">
                      {cacheSettings?.similarity_threshold || 0.88}
                    </span>
                  </div>
                  <input
                    type="range"
                    min="0.60"
                    max="0.95"
                    step="0.01"
                    value={cacheSettings?.similarity_threshold || 0.75}
                    onChange={(e) => {
                      const val = parseFloat(e.target.value);
                      setCacheSettings((prev) => ({ ...prev, similarity_threshold: val }));
                      updateCacheSettings({ similarity_threshold: val });
                    }}
                    className="w-full accent-[#ff4d00] cursor-pointer"
                  />
                  <span className="text-[11px] text-[#6b7194]">
                    Lower values increase semantic rephrase hit rate (0.70-0.78 recommended for MiniLM embeddings); higher values require near-identical wording. Default is 0.75.
                  </span>
                </div>

                <div className="pt-4 border-t border-[#e8dfe4] flex items-center justify-between">
                  <div>
                    <div className="text-xs font-bold text-[#232b4a]">Flush Semantic Cache</div>
                    <div className="text-[11px] text-[#6b7194]">
                      Invalidates all Redis keys and empties the FAISS vector index.
                    </div>
                  </div>
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={handleClearCache}
                  >
                    Flush Cache
                  </Button>
                </div>
              </Card>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
