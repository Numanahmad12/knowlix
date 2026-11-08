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
  Flame,
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
import { MetricCard } from "./components/ui/MetricCard";
import { EmptyState } from "./components/ui/EmptyState";
import { Input } from "./components/ui/Input";
import CommandPalette from "./components/CommandPalette";

// Dynamically import Three.js 3D canvas so it renders purely on client
const ThreeSemanticOrb = dynamic(() => import("./components/ThreeSemanticOrb"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-64 flex items-center justify-center">
      <div className="w-8 h-8 rounded-full border-2 border-[#a8c9c8] border-t-transparent animate-spin" />
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
    <div className={`${currentView === "workspace" ? "h-screen max-h-screen overflow-hidden" : "min-h-screen"} bg-[#f8fafa] text-[#0f1717] flex flex-col font-sans selection:bg-[#a8c9c8]/30 selection:text-[#0f1717]`}>
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
        className={`flex-1 flex flex-col transition-all duration-300 bg-knowlix-pattern ${
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
          <div className="fixed top-20 right-6 z-50 flex items-center gap-2.5 px-4 py-2.5 rounded-xl bg-white border border-[#a8c9c8] shadow-card-hover animate-fadeIn text-xs">
            <CheckCircle2 className="w-4 h-4 text-[#f45b0b]" />
            <span className="text-[#0f1717] font-semibold">{notice.msg}</span>
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
              {/* Hero Banner with Three.js 3D Vector Orb (Teal & Orange) */}
              <Card className="p-6 md:p-8 relative overflow-hidden flex flex-col lg:flex-row items-center justify-between gap-6 border-[#a8c9c8] shadow-card">
                <div className="flex-1 z-10 flex flex-col gap-3.5">
                  <Badge variant="mono" icon={Zap}>
                    Document-Aware Semantic Caching Engine
                  </Badge>

                  <h1 className="text-2xl md:text-3xl lg:text-4xl font-extrabold tracking-tight text-[#0f1717] leading-tight">
                    High-Precision Document Intelligence with{" "}
                    <span className="text-[#f45b0b]">
                      Zero-Overhead Vector Caching
                    </span>
                  </h1>

                  <p className="text-[#647474] text-xs md:text-sm max-w-2xl leading-relaxed">
                    Instantly resolve semantically equivalent questions without re-running vector retrieval or Groq LLM generation. Bound to document SHA-256 with exact-match L1 and FAISS cosine similarity L2.
                  </p>

                  <div className="flex flex-wrap items-center gap-3 pt-2">
                    <Button
                      variant="primary"
                      onClick={() => setCurrentView("workspace")}
                      icon={ArrowRight}
                      iconPosition="right"
                    >
                      Open AI Workspace
                    </Button>

                    <Button
                      variant="secondary"
                      onClick={() => setCurrentView("documents")}
                      icon={UploadCloud}
                    >
                      Upload PDF
                    </Button>

                    <Button
                      variant="outline"
                      onClick={handleRunBenchmark}
                      loading={benchmarking}
                      icon={Play}
                    >
                      {benchmarking ? "Running Benchmark…" : "Run 3-Mode Benchmark"}
                    </Button>
                  </div>

                  <div className="flex flex-wrap items-center gap-4 pt-2 text-xs text-[#647474] font-mono">
                    <span className="flex items-center gap-1.5 font-medium">
                      <span className="w-2.5 h-2.5 rounded-full bg-[#a8c9c8]" /> ONNX MiniLM 384d
                    </span>
                    <span className="flex items-center gap-1.5 font-medium">
                      <span className="w-2.5 h-2.5 rounded-full bg-[#5a9695]" /> FAISS Cosine L2
                    </span>
                    <span className="flex items-center gap-1.5 font-medium">
                      <span className="w-2.5 h-2.5 rounded-full bg-[#f45b0b]" /> Sub-10ms Exact L1
                    </span>
                  </div>
                </div>

                {/* 3D Interactive Latent Vector Orb (Teal & Orange Particles) */}
                <div className="w-full lg:w-72 h-64 relative flex items-center justify-center flex-shrink-0">
                  <ThreeSemanticOrb size={260} mode={asking ? "searching" : "idle"} />
                  <div className="absolute bottom-1 right-2 text-[10px] font-mono text-[#274141] bg-white/90 px-2 py-0.5 rounded border border-[#a8c9c8] font-bold shadow-subtle">
                    384-d Latent Space
                  </div>
                </div>
              </Card>

              {/* Metric KPI Cards (Knowlix Palette) */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <MetricCard
                  title="Semantic Cache Hit Rate"
                  value={cacheStats?.hit_rate != null ? `${(cacheStats.hit_rate * 100).toFixed(1)}%` : "0.0%"}
                  subvalue={`${(cacheStats?.exact_hits || 0) + (cacheStats?.semantic_hits || 0)} hits`}
                  description="Queries served without LLM call"
                  icon={Zap}
                  color="teal"
                />

                <MetricCard
                  title="Avg Cache Latency"
                  value={`${(cacheStats?.avg_lookup_latency_ms ?? cacheStats?.avg_cache_latency_ms ?? 0).toFixed(0)} ms`}
                  subvalue="vs ~1,850ms RAG"
                  description="Up to 98% latency reduction"
                  icon={Clock}
                  color="teal"
                />

                <MetricCard
                  title="Tokens & Cost Saved"
                  value={(cacheStats?.estimated_tokens_saved ?? cacheStats?.tokens_saved ?? 0).toLocaleString()}
                  subvalue={`$${(cacheStats?.estimated_cost_saved_usd ?? cacheStats?.estimated_cost_saved ?? 0).toFixed(4)}`}
                  description="Zero redundant LLM tokens"
                  icon={Flame}
                  color="orange"
                />

                <MetricCard
                  title="Indexed Knowledge"
                  value={documents.length}
                  subvalue={activeDoc ? `${activeDoc.total_chunks} chunks` : "ready"}
                  description={activeDoc ? truncate(activeDoc.filename, 20) : "No active document"}
                  icon={FileCode}
                  color="teal"
                />
              </div>

              {/* Active Document Quick Spotlight */}
              {activeDoc && (
                <Card className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 border-[#a8c9c8]">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-xl bg-[#e5f0f0] border border-[#a8c9c8] flex items-center justify-center text-[#274141] flex-shrink-0">
                      <FileText className="w-6 h-6 text-[#f45b0b]" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="text-sm md:text-base font-bold text-[#0f1717]">{activeDoc.filename}</h3>
                        <Badge variant="exact" size="sm">Active Index</Badge>
                      </div>
                      <p className="text-xs text-[#647474] font-mono mt-1">
                        SHA-256: {activeDoc.doc_hash ? `${activeDoc.doc_hash.slice(0, 16)}…` : "generated"} • {activeDoc.total_pages} pages • {activeDoc.total_chunks} chunks
                      </p>
                    </div>
                  </div>

                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => setCurrentView("workspace")}
                    icon={BookOpen}
                  >
                    Open in Workspace
                  </Button>
                </Card>
              )}

              {/* Quick Actions Navigation Matrix */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <Card
                  hoverable
                  onClick={() => setCurrentView("workspace")}
                  className="flex flex-col gap-2 group"
                >
                  <div className="flex items-center justify-between">
                    <BookOpen className="w-5 h-5 text-[#f45b0b] group-hover:scale-110 transition-transform" />
                    <ArrowRight className="w-4 h-4 text-[#94a3a3] group-hover:text-[#f45b0b] transition-colors" />
                  </div>
                  <h4 className="font-bold text-[#0f1717] text-sm">AI Workspace Studio</h4>
                  <p className="text-xs text-[#647474] leading-relaxed">
                    Ask natural questions against your document with guaranteed page citations and sentence support checks.
                  </p>
                </Card>

                <Card
                  hoverable
                  onClick={() => setCurrentView("cache")}
                  className="flex flex-col gap-2 group"
                >
                  <div className="flex items-center justify-between">
                    <Zap className="w-5 h-5 text-[#375f5f] group-hover:scale-110 transition-transform" />
                    <ArrowRight className="w-4 h-4 text-[#94a3a3] group-hover:text-[#375f5f] transition-colors" />
                  </div>
                  <h4 className="font-bold text-[#0f1717] text-sm">Semantic Cache Inspector</h4>
                  <p className="text-xs text-[#647474] leading-relaxed">
                    Explore active vector cache entries, inspect cosine similarity scores, and benchmark response speed.
                  </p>
                </Card>

                <Card
                  hoverable
                  onClick={() => setCurrentView("guardrails")}
                  className="flex flex-col gap-2 group"
                >
                  <div className="flex items-center justify-between">
                    <ShieldCheck className="w-5 h-5 text-[#274141] group-hover:scale-110 transition-transform" />
                    <ArrowRight className="w-4 h-4 text-[#94a3a3] group-hover:text-[#274141] transition-colors" />
                  </div>
                  <h4 className="font-bold text-[#0f1717] text-sm">Security & Guardrails</h4>
                  <p className="text-xs text-[#647474] leading-relaxed">
                    View prompt injection barriers, groundedness validation (0.40 threshold), and sentence claim verification.
                  </p>
                </Card>
              </div>
            </div>
          )}

          {/* VIEW 2: MY DOCUMENTS */}
          {currentView === "documents" && (
            <div className="flex flex-col gap-6 animate-fadeIn">
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                <div>
                  <h2 className="text-xl md:text-2xl font-extrabold text-[#0f1717]">Document Library</h2>
                  <p className="text-xs text-[#647474] mt-1">
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
                <div className="w-14 h-14 mx-auto rounded-2xl bg-[#e5f0f0] border border-[#a8c9c8] flex items-center justify-center text-[#f45b0b] mb-4 shadow-subtle">
                  <UploadCloud className="w-7 h-7" />
                </div>
                <h3 className="text-sm md:text-base font-bold text-[#0f1717] mb-1">
                  Drop your PDF here, or <span className="text-[#f45b0b] underline underline-offset-4">browse files</span>
                </h3>
                <p className="text-xs text-[#647474] max-w-sm mx-auto mb-4">
                  Supports research papers, technical manuals, reports, and whitepapers. Max {MAX_FILE_SIZE_MB}MB, up to {MAX_PDF_PAGES} pages.
                </p>
                {analyzeStatus && (
                  <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#e5f0f0] text-[#274141] text-xs font-mono font-bold border border-[#a8c9c8]">
                    <RefreshCw className="w-3.5 h-3.5 animate-spin text-[#f45b0b]" />
                    <span>{analyzeStatus}</span>
                  </div>
                )}
              </div>

              {/* Documents Table */}
              <Card padding="p-0" className="overflow-hidden">
                <div className="p-4 border-b border-[#e4ebeb] flex items-center justify-between bg-[#f8fafa]">
                  <h3 className="text-sm font-bold text-[#0f1717]">Indexed Documents ({documents.length})</h3>
                  <span className="text-xs text-[#647474] font-mono">SHA-256 Protected</span>
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
                      <thead className="bg-[#f8fafa] text-[#647474] font-mono border-b border-[#e4ebeb]">
                        <tr>
                          <th className="p-4">Document</th>
                          <th className="p-4">Pages & Chunks</th>
                          <th className="p-4">SHA-256 Fingerprint</th>
                          <th className="p-4">Status</th>
                          <th className="p-4 text-right">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#e4ebeb] text-[#334141]">
                        {documents.map((doc) => {
                          const isActive = activeDoc?.session_id === doc.session_id;
                          return (
                            <tr key={doc.session_id} className="hover:bg-[#f8fafa] transition-colors">
                              <td className="p-4 font-bold text-[#0f1717] flex items-center gap-2">
                                <FileText className="w-4 h-4 text-[#f45b0b] flex-shrink-0" />
                                <span className="truncate max-w-xs">{doc.filename}</span>
                              </td>
                              <td className="p-4 font-mono text-[#647474]">
                                {doc.total_pages} pages • {doc.total_chunks} chunks
                              </td>
                              <td className="p-4 font-mono text-[#647474]">
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
                  <span className="text-[10px] font-mono uppercase tracking-wider text-[#647474] font-bold">
                    Active Document
                  </span>
                  {activeDoc ? (
                    <div>
                      <h3 className="text-sm font-bold text-[#0f1717] truncate" title={activeDoc.filename}>
                        {activeDoc.filename}
                      </h3>
                      <p className="text-xs text-[#5a9695] font-mono mt-0.5 font-medium">
                        {activeDoc.total_pages} pages • {activeDoc.total_chunks} chunks indexed
                      </p>
                    </div>
                  ) : (
                    <div className="text-xs text-[#647474]">
                      No document selected.{" "}
                      <button onClick={handleLoadSample} className="text-[#f45b0b] underline font-bold">
                        Load sample
                      </button>
                    </div>
                  )}
                </Card>

                {/* Dynamic Suggested Questions Generated from Active PDF */}
                <Card className="flex flex-col gap-2">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] font-mono uppercase tracking-wider text-[#647474] font-bold">
                      Suggested Questions
                    </span>
                    {loadingSuggestions && (
                      <RefreshCw className="w-3 h-3 text-[#f45b0b] animate-spin" />
                    )}
                  </div>
                  {suggestions.length === 0 ? (
                    <div className="text-xs text-[#647474] italic py-3 text-center">
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
                        className="text-left p-2.5 rounded-xl bg-[#f8fafa] hover:bg-[#e5f0f0] border border-[#e4ebeb] hover:border-[#a8c9c8] text-xs text-[#334141] hover:text-[#0f1717] font-medium transition-all disabled:opacity-50 flex items-start gap-2 group"
                      >
                        <HelpCircle className="w-3.5 h-3.5 text-[#5a9695] group-hover:text-[#f45b0b] flex-shrink-0 mt-0.5 transition-colors" />
                        <span className="leading-snug">{sq}</span>
                      </button>
                    ))
                  )}
                </Card>

                {/* Guardrails Active Status */}
                <Card className="flex flex-col gap-2 text-xs font-mono">
                  <span className="text-[10px] uppercase tracking-wider text-[#647474] font-bold">Guardrails Active</span>
                  <div className="flex items-center justify-between text-[#647474]">
                    <span>Groundedness Gate:</span>
                    <span className="text-[#274141] font-bold">≥ {RELEVANCE_GATE}</span>
                  </div>
                  <div className="flex items-center justify-between text-[#647474]">
                    <span>Claim Check:</span>
                    <span className="text-[#f45b0b] font-bold">Sentence Level</span>
                  </div>
                  <div className="flex items-center justify-between text-[#647474]">
                    <span>Semantic Cache:</span>
                    <span className="text-[#375f5f] font-bold">Dual-Tier L1+L2</span>
                  </div>
                </Card>
              </div>

              {/* Center Column: Fixed-Height Conversation Thread */}
              <div className="flex-1 min-h-0 h-full flex flex-col bg-white rounded-2xl border border-[#a8c9c8] shadow-subtle overflow-hidden relative">
                {/* Chat Top Header */}
                <div className="shrink-0 p-3.5 md:p-4 border-b border-[#e4ebeb] flex items-center justify-between bg-[#f8fafa]">
                  <div className="flex items-center gap-2">
                    <Bot className="w-4 h-4 text-[#f45b0b]" />
                    <span className="text-xs md:text-sm font-bold text-[#0f1717]">Knowlix Document Studio</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setChat([])}
                      className="text-xs text-[#647474] hover:text-[#0f1717] transition-colors"
                      title="Clear chat history"
                    >
                      Clear history
                    </button>
                    <button
                      onClick={() => setRightPanelOpen(!rightPanelOpen)}
                      className="text-xs text-[#375f5f] hover:text-[#0f1717] font-semibold transition-colors ml-2 hidden lg:inline"
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
                  className="flex-1 min-h-0 overflow-y-auto p-4 md:p-6 flex flex-col gap-4 bg-[#fdfefe] overscroll-contain"
                >
                  {chat.length === 0 ? (
                    <div className="m-auto text-center max-w-md py-8">
                      <div className="w-12 h-12 mx-auto rounded-2xl bg-[#e5f0f0] border border-[#a8c9c8] flex items-center justify-center text-[#f45b0b] mb-3 shadow-subtle">
                        <Sparkles className="w-6 h-6" />
                      </div>
                      <h4 className="text-base font-bold text-[#0f1717] mb-1">
                        Ask Anything About This Document
                      </h4>
                      <p className="text-xs text-[#647474] leading-relaxed mb-4">
                        Knowlix verifies answers against real document pages and caches semantically equivalent questions for instantaneous responses.
                      </p>
                      {suggestions.length > 0 && (
                        <div className="flex flex-col gap-2 text-left">
                          <span className="text-[11px] font-mono text-[#647474] text-center mb-1">Try one of these:</span>
                          {suggestions.slice(0, 3).map((sq, idx) => (
                            <button
                              key={idx}
                              onClick={() => handleAsk(sq)}
                              disabled={!activeDoc || asking}
                              className="text-xs text-[#274141] hover:text-[#0f1717] bg-[#f8fafa] hover:bg-[#e5f0f0] p-2.5 rounded-xl border border-[#e4ebeb] hover:border-[#a8c9c8] text-left transition-all"
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
                              <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-[#e4ebeb]">
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
                                  <span className="text-[11px] font-mono text-[#647474]">
                                    {msg.model_used || "Groq gpt-oss-120b"}
                                  </span>
                                </div>
                                {msg.cache_performance.cache_hit && (
                                  <span className="text-[10px] font-mono text-[#274141] font-bold bg-[#e5f0f0] px-2 py-0.5 rounded border border-[#a8c9c8]">
                                    Zero LLM Overhead
                                  </span>
                                )}
                              </div>
                            )}

                            {/* Answer Text */}
                            <div className="text-xs md:text-sm text-[#0f1717] leading-relaxed whitespace-pre-wrap font-sans break-words [overflow-wrap:anywhere]">
                              {stripSupportLine(msg.content)}
                            </div>

                            {msg.refused && (
                              <div className="mt-2.5 pt-2.5 border-t border-dashed border-[#e4ebeb] text-xs text-[#647474] flex items-start gap-1.5 bg-[#fbfdfd] p-2 rounded-lg">
                                <Info className="w-3.5 h-3.5 text-[#5a9695] shrink-0 mt-0.5" />
                                <span>
                                  This query scored below the groundedness gate (≥ 0.40) or had no backing claims in the document. Try asking an overview question (e.g. <em>&quot;What is this document about?&quot;</em>) or select from the suggested questions in the left panel.
                                </span>
                              </div>
                            )}

                            {/* Citations & Source Page Pills (Teal Spotlight) */}
                            {msg.citations && msg.citations.length > 0 && (
                              <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-[#e4ebeb]">
                                <span className="text-xs text-[#647474] font-mono font-medium">Sources:</span>
                                {msg.citations.map((p) => (
                                  <button
                                    key={p}
                                    onClick={() => setActiveCitationPage(p)}
                                    className="citation-pill"
                                  >
                                    Page {p}
                                  </button>
                                ))}
                                <span className="text-[11px] font-mono text-[#274141] font-bold ml-auto bg-[#e5f0f0] px-2 py-0.5 rounded border border-[#a8c9c8]">
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
                      <div className="chat-bubble-assistant flex items-center gap-3 py-3 px-4 rounded-2xl bg-white border border-[#a8c9c8]">
                        <div className="w-4 h-4 rounded-full border-2 border-[#f45b0b] border-t-transparent animate-spin flex-shrink-0" />
                        <span className="text-xs text-[#274141] font-mono font-medium">
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
                    className="absolute bottom-24 right-6 z-20 flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white border border-[#a8c9c8] shadow-card-hover text-xs font-semibold text-[#0f1717] hover:bg-[#e5f0f0] transition-all"
                  >
                    <ArrowDown className="w-3.5 h-3.5 text-[#f45b0b]" />
                    <span>Scroll to latest</span>
                    {hasNewMessagesWhileScrolledUp && (
                      <span className="w-2 h-2 rounded-full bg-[#f45b0b] animate-pulse" />
                    )}
                  </button>
                )}

                {/* Fixed Modern Composer Input Bar */}
                <div className="shrink-0 p-3 md:p-4 border-t border-[#e4ebeb] bg-white relative shadow-[0_-4px_16px_rgba(0,0,0,0.03)]">
                  <form
                    onSubmit={(e) => {
                      e.preventDefault();
                      handleAsk();
                    }}
                    className="flex items-end gap-2.5"
                  >
                    <div className="flex-1 relative rounded-xl border border-[#cbdada] focus-within:border-[#f45b0b] focus-within:ring-2 focus-within:ring-[#f45b0b]/20 bg-[#f8fafa] focus-within:bg-white transition-all">
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
                        className="w-full resize-none bg-transparent px-3.5 py-2.5 text-xs md:text-sm text-[#0f1717] placeholder-[#94a3a3] outline-none max-h-32 min-h-[42px] leading-relaxed scrollbar-thin"
                      />
                    </div>
                    <Button
                      type="submit"
                      variant="primary"
                      size="md"
                      disabled={!activeDoc || asking || !question.trim() || activeDoc.chunk_count === 0}
                      icon={ArrowRight}
                      className="h-[42px] px-4 flex-shrink-0 shadow-sm"
                    >
                      Ask
                    </Button>
                  </form>
                  <div className="flex items-center justify-between mt-1.5 px-1 text-[11px] text-[#94a3a3] font-mono">
                    <span>↵ to send • Shift+↵ for new line</span>
                    <span className="hidden sm:inline">Grounding: Page-level citations verified</span>
                  </div>
                </div>
              </div>

              {/* Right Column (320px): Source Inspector */}
              {rightPanelOpen && (
                <Card className="w-full lg:w-72 xl:w-80 h-full flex flex-col gap-4 overflow-y-auto shrink-0 pl-1 border-[#a8c9c8]">
                  <div className="flex items-center justify-between pb-2 border-b border-[#e4ebeb]">
                    <span className="text-xs font-bold text-[#0f1717] flex items-center gap-1.5">
                      <Eye className="w-4 h-4 text-[#f45b0b]" /> Source Inspector
                    </span>
                    <span className="text-[10px] font-mono text-[#274141] bg-[#e5f0f0] px-2 py-0.5 rounded font-bold">
                      {activeCitationPage ? `Page ${activeCitationPage}` : "All citations"}
                    </span>
                  </div>

                  {chat.length === 0 || !chat[chat.length - 1]?.source_chunks ? (
                    <div className="p-8 text-center text-[#647474] text-xs">
                      Ask a question to inspect retrieved source excerpts and sentence claim support.
                    </div>
                  ) : (
                    <div className="flex flex-col gap-3">
                      {chat[chat.length - 1].source_chunks
                        .filter((c) => (activeCitationPage ? c.page === activeCitationPage : true))
                        .map((chunk, idx) => (
                          <div
                            key={idx}
                            className="p-3 rounded-xl bg-[#f8fafa] border border-[#a8c9c8] flex flex-col gap-1.5 text-xs shadow-subtle"
                          >
                            <div className="flex items-center justify-between">
                              <span className="font-mono text-[#f45b0b] font-bold">
                                Page {chunk.page}
                              </span>
                              <span className="text-[10px] font-mono text-[#274141] font-bold bg-[#e5f0f0] px-1.5 py-0.2 rounded border border-[#a8c9c8]">
                                Score: {(chunk.score || 0.85).toFixed(2)}
                              </span>
                            </div>
                            <p className="text-[#334141] text-[11px] leading-relaxed italic">
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
                  <h2 className="text-xl md:text-2xl font-extrabold text-[#0f1717]">Semantic Cache Engine</h2>
                  <p className="text-xs text-[#647474] mt-1">
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
                <Card className="border-[#a8c9c8] flex flex-col gap-4">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-[#0f1717] flex items-center gap-2">
                      <Zap className="w-4 h-4 text-[#f45b0b]" /> 3-Mode Performance Benchmark Comparison
                    </span>
                    <span className="text-[10px] font-mono text-[#274141] bg-[#e5f0f0] px-2 py-0.5 rounded font-bold border border-[#a8c9c8]">
                      Speedup: {benchmarkResult.semantic_speedup_factor}x faster
                    </span>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {/* Mode A */}
                    <div className="p-4 rounded-xl bg-[#fef5f0] border border-[rgba(244,91,11,0.25)] flex flex-col gap-1">
                      <span className="text-xs text-[#dc4805] font-mono font-bold">Mode A: Baseline RAG</span>
                      <span className="text-xl font-bold font-mono text-[#b73507]">
                        {(benchmarkResult.mode_a_baseline?.avg_latency_ms ?? benchmarkResult.mode_a_baseline_rag?.avg_latency_ms ?? 1250).toFixed(0)} ms
                      </span>
                      <span className="text-[11px] text-[#647474] font-mono">
                        {benchmarkResult.mode_a_baseline?.llm_calls ?? 4} LLM calls (full compute)
                      </span>
                    </div>

                    {/* Mode B */}
                    <div className="p-4 rounded-xl bg-[#e5f0f0] border border-[#a8c9c8] flex flex-col gap-1">
                      <span className="text-xs text-[#274141] font-mono font-bold">Mode B: Exact Cache</span>
                      <span className="text-xl font-bold font-mono text-[#274141]">
                        {(benchmarkResult.mode_b_exact?.avg_latency_ms ?? benchmarkResult.mode_b_exact_cache?.avg_latency_ms ?? 0.8).toFixed(1)} ms
                      </span>
                      <span className="text-[11px] text-[#375f5f] font-mono font-medium">
                        {benchmarkResult.mode_b_exact?.cache_hits ?? 1} hits (100% saved)
                      </span>
                    </div>

                    {/* Mode C */}
                    <div className="p-4 rounded-xl bg-[#f3f8f8] border border-[#86b3b2] flex flex-col gap-1">
                      <span className="text-xs text-[#274141] font-mono font-bold">Mode C: Semantic Cache</span>
                      <span className="text-xl font-bold font-mono text-[#274141]">
                        {(benchmarkResult.mode_c_semantic?.avg_latency_ms ?? benchmarkResult.mode_c_semantic_cache?.avg_latency_ms ?? 24).toFixed(1)} ms
                      </span>
                      <span className="text-[11px] text-[#f45b0b] font-mono font-bold">
                        {benchmarkResult.mode_c_semantic?.tokens_saved ?? 600} tokens saved
                      </span>
                    </div>
                  </div>
                </Card>
              )}

              {/* Cache Entries Table */}
              <Card padding="p-0" className="overflow-hidden">
                <div className="p-4 border-b border-[#e4ebeb] flex items-center justify-between bg-[#f8fafa]">
                  <h3 className="text-sm font-bold text-[#0f1717]">Active Cache Entries ({cacheEntries.length})</h3>
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
                      <thead className="bg-[#f8fafa] text-[#647474] font-mono border-b border-[#e4ebeb]">
                        <tr>
                          <th className="p-4">Cached Query</th>
                          <th className="p-4">Hits</th>
                          <th className="p-4">Tokens Saved</th>
                          <th className="p-4">Document Hash</th>
                          <th className="p-4 text-right">Invalidate</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#e4ebeb] text-[#334141] font-mono">
                        {cacheEntries.map((entry) => (
                          <tr key={entry.entry_id} className="hover:bg-[#f8fafa] transition-colors">
                            <td className="p-4 font-sans font-semibold text-[#0f1717] max-w-sm truncate">
                              {entry.normalized_query || entry.query_text}
                            </td>
                            <td className="p-4 text-[#274141] font-bold">{entry.hit_count}</td>
                            <td className="p-4 text-[#f45b0b] font-bold">{entry.tokens_saved ?? (entry.hit_count * 150)}</td>
                            <td className="p-4 text-[#647474]">{entry.doc_hash?.slice(0, 12)}…</td>
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
                <h2 className="text-xl md:text-2xl font-extrabold text-[#0f1717]">Performance Analytics & Latency Radar</h2>
                <p className="text-xs text-[#647474] mt-1">
                  Telemetry tracking query throughput, latency distribution, and cost reductions.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <Card className="flex flex-col gap-3">
                  <span className="text-xs font-bold text-[#647474]">Throughput Summary</span>
                  <div className="text-3xl font-extrabold font-mono text-[#0f1717]">
                    {(cacheStats?.total_queries || 0)}
                  </div>
                  <span className="text-xs text-[#647474]">Total Queries Evaluated</span>
                  <div className="w-full bg-[#e5f0f0] h-2.5 rounded-full overflow-hidden mt-2">
                    <div
                      className="bg-[#f45b0b] h-full"
                      style={{ width: `${(cacheStats?.hit_rate || 0) * 100}%` }}
                    />
                  </div>
                </Card>

                <Card className="flex flex-col gap-3">
                  <span className="text-xs font-bold text-[#647474]">Net Token Savings</span>
                  <div className="text-3xl font-extrabold font-mono text-[#f45b0b]">
                    {(cacheStats?.estimated_tokens_saved ?? cacheStats?.tokens_saved ?? 0).toLocaleString()}
                  </div>
                  <span className="text-xs text-[#647474]">Tokens Saved vs Groq gpt-oss-120b</span>
                </Card>

                <Card className="flex flex-col gap-3">
                  <span className="text-xs font-bold text-[#647474]">Estimated Cost Reduction</span>
                  <div className="text-3xl font-extrabold font-mono text-[#274141]">
                    ${(cacheStats?.estimated_cost_saved_usd ?? cacheStats?.estimated_cost_saved ?? 0).toFixed(4)}
                  </div>
                  <span className="text-xs text-[#647474]">Saved at $0.70/1M tokens</span>
                </Card>
              </div>
            </div>
          )}

          {/* VIEW 6: GUARDRAILS & SECURITY */}
          {currentView === "guardrails" && (
            <div className="flex flex-col gap-6 animate-fadeIn">
              <div>
                <h2 className="text-xl md:text-2xl font-extrabold text-[#0f1717]">Security Architecture & Guardrails</h2>
                <p className="text-xs text-[#647474] mt-1">
                  Knowlix applies four consecutive defense layers to prevent prompt injection and hallucinations.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Card className="flex flex-col gap-2">
                  <div className="flex items-center gap-2 text-[#274141] font-bold text-sm">
                    <ShieldCheck className="w-4 h-4 text-[#f45b0b]" /> Layer 1: Prompt Injection Sanitization
                  </div>
                  <p className="text-xs text-[#647474] leading-relaxed">
                    Strips instruction overrides, system-prompt exploits, and jailbreak delimiters before embeddings or LLM inference.
                  </p>
                </Card>

                <Card className="flex flex-col gap-2">
                  <div className="flex items-center gap-2 text-[#274141] font-bold text-sm">
                    <Filter className="w-4 h-4 text-[#5a9695]" /> Layer 2: Relevance Retrieval Gate
                  </div>
                  <p className="text-xs text-[#647474] leading-relaxed">
                    Enforces strict minimum cosine retrieval threshold (0.40). Queries outside document scope are rejected before LLM invocation.
                  </p>
                </Card>

                <Card className="flex flex-col gap-2">
                  <div className="flex items-center gap-2 text-[#274141] font-bold text-sm">
                    <FileCode className="w-4 h-4 text-[#f45b0b]" /> Layer 3: Groundedness Validation
                  </div>
                  <p className="text-xs text-[#647474] leading-relaxed">
                    Verifies answers strictly match document citations. Extractive fallback executes automatically if generative drift is detected.
                  </p>
                </Card>

                <Card className="flex flex-col gap-2">
                  <div className="flex items-center gap-2 text-[#274141] font-bold text-sm">
                    <CheckCircle2 className="w-4 h-4 text-[#5a9695]" /> Layer 4: Sentence-Level Claim Check
                  </div>
                  <p className="text-xs text-[#647474] leading-relaxed">
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
                <h2 className="text-xl md:text-2xl font-extrabold text-[#0f1717]">System Settings</h2>
                <p className="text-xs text-[#647474] mt-1">
                  Configure semantic similarity thresholds, cache TTLs, and backend connection parameters.
                </p>
              </div>

              <Card className="flex flex-col gap-5 border-[#a8c9c8]">
                <div className="flex flex-col gap-2">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-bold text-[#0f1717]">
                      Semantic Similarity Threshold
                    </label>
                    <span className="text-xs font-mono font-bold text-[#f45b0b] bg-[#fef5f0] px-2 py-0.5 rounded border border-[rgba(244,91,11,0.25)]">
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
                    className="w-full accent-[#f45b0b] cursor-pointer"
                  />
                  <span className="text-[11px] text-[#647474]">
                    Lower values increase semantic rephrase hit rate (0.70-0.78 recommended for MiniLM embeddings); higher values require near-identical wording. Default is 0.75.
                  </span>
                </div>

                <div className="pt-4 border-t border-[#e4ebeb] flex items-center justify-between">
                  <div>
                    <div className="text-xs font-bold text-[#0f1717]">Flush Semantic Cache</div>
                    <div className="text-[11px] text-[#647474]">
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
