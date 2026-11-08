"use client";

import { useEffect, useState } from "react";
import {
  Activity,
  BarChart3,
  BookOpen,
  Command,
  Database,
  FileText,
  Flame,
  LayoutDashboard,
  Play,
  RotateCcw,
  Search,
  Settings,
  ShieldAlert,
  Sparkles,
  X,
  Zap,
} from "lucide-react";

export default function CommandPalette({
  isOpen,
  onClose,
  onNavigate,
  onLoadSample,
  onRunBenchmark,
  onClearCache,
}) {
  const [query, setQuery] = useState("");

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const actions = [
    {
      id: "view-overview",
      icon: LayoutDashboard,
      title: "Go to Dashboard Overview",
      subtitle: "System status, metrics and quick actions",
      badge: "View",
      handler: () => { onNavigate("overview"); onClose(); },
    },
    {
      id: "view-documents",
      icon: FileText,
      title: "Go to My Documents",
      subtitle: "Upload and manage indexed PDF knowledge base",
      badge: "View",
      handler: () => { onNavigate("documents"); onClose(); },
    },
    {
      id: "view-workspace",
      icon: BookOpen,
      title: "Go to AI Workspace Studio",
      subtitle: "Document question-answering with citation grounding",
      badge: "View",
      handler: () => { onNavigate("workspace"); onClose(); },
    },
    {
      id: "view-cache",
      icon: Zap,
      title: "Go to Semantic Cache Engine",
      subtitle: "Vector similarity explorer and deduplication stats",
      badge: "View",
      handler: () => { onNavigate("cache"); onClose(); },
    },
    {
      id: "view-analytics",
      icon: BarChart3,
      title: "Go to Analytics & Latency Radar",
      subtitle: "Comparative latency graphs and cost savings",
      badge: "View",
      handler: () => { onNavigate("analytics"); onClose(); },
    },
    {
      id: "view-guardrails",
      icon: ShieldAlert,
      title: "Go to Security & Guardrails",
      subtitle: "Groundedness gate, sentence claim check, prompt injection checks",
      badge: "View",
      handler: () => { onNavigate("guardrails"); onClose(); },
    },
    {
      id: "view-settings",
      icon: Settings,
      title: "Go to System Settings",
      subtitle: "Similarity threshold, TTL, Redis configuration",
      badge: "View",
      handler: () => { onNavigate("settings"); onClose(); },
    },
    {
      id: "act-sample",
      icon: Sparkles,
      title: "Load Sample Document",
      subtitle: "Instantly index the built-in research PDF",
      badge: "Action",
      handler: () => { onLoadSample(); onClose(); },
    },
    {
      id: "act-benchmark",
      icon: Play,
      title: "Run 3-Mode Performance Benchmark",
      subtitle: "Compare Baseline RAG vs Exact Match vs Semantic Cache",
      badge: "Action",
      handler: () => { onRunBenchmark(); onClose(); },
    },
    {
      id: "act-clear",
      icon: RotateCcw,
      title: "Flush All Cache Entries",
      subtitle: "Clear exact Redis & FAISS semantic cache vectors",
      badge: "Danger",
      handler: () => { onClearCache(); onClose(); },
    },
  ];

  const filtered = actions.filter(
    (a) =>
      a.title.toLowerCase().includes(query.toLowerCase()) ||
      a.subtitle.toLowerCase().includes(query.toLowerCase())
  );

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-24 px-4 bg-slate-900/40 backdrop-blur-sm animate-fadeIn">
      <div 
        className="w-full max-w-2xl bg-white border border-[#f3b8ca] rounded-2xl shadow-2xl overflow-hidden text-[#232b4a]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center px-4 py-3.5 border-b border-[#e8dfe4] bg-[#fff9f3]">
          <Search className="w-5 h-5 text-[#2e7d7b] mr-3" />
          <input
            type="text"
            placeholder="Type a command or search actions..."
            className="w-full bg-transparent border-none outline-none text-[#232b4a] placeholder-[#9aa0b8] text-sm font-sans"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            autoFocus
          />
          <kbd className="hidden sm:inline-flex items-center gap-1 px-2 py-0.5 text-[11px] font-mono text-[#6b7194] bg-white border border-[#e8dfe4] rounded">
            ESC
          </kbd>
          <button 
            onClick={onClose} 
            className="p-1 ml-2 text-[#6b7194] hover:text-[#232b4a] transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="max-h-96 overflow-y-auto p-2 divide-y divide-[#fdeef3]">
          {filtered.length === 0 ? (
            <div className="p-8 text-center text-[#6b7194] text-sm">
              No matching actions found for "{query}"
            </div>
          ) : (
            filtered.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.id}
                  onClick={item.handler}
                  className="w-full flex items-center justify-between p-3 rounded-xl hover:bg-[#fdeef3] transition-all text-left group"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-xl bg-[#fdeef3] border border-[#f3b8ca] flex items-center justify-center text-[#1e2a5c] group-hover:scale-105 transition-all">
                      <Icon className="w-4 h-4 text-[#1e2a5c]" />
                    </div>
                    <div>
                      <div className="text-sm font-bold text-[#232b4a] group-hover:text-[#ff4d00] transition-colors">
                        {item.title}
                      </div>
                      <div className="text-xs text-[#6b7194] font-sans">
                        {item.subtitle}
                      </div>
                    </div>
                  </div>
                  <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border font-bold ${
                    item.badge === "Action"
                      ? "bg-[#fff1e8] text-[#ff4d00] border-[rgba(244,91,11,0.3)]"
                      : item.badge === "Danger"
                      ? "bg-rose-50 text-rose-600 border-rose-200"
                      : "bg-[#fdeef3] text-[#1e2a5c] border-[#f3b8ca]"
                  }`}>
                    {item.badge}
                  </span>
                </button>
              );
            })
          )}
        </div>

        <div className="px-4 py-2 bg-[#fff9f3] border-t border-[#e8dfe4] flex items-center justify-between text-[11px] text-[#6b7194] font-mono">
          <div className="flex items-center gap-2 font-semibold">
            <span className="w-2 h-2 rounded-full bg-[#ff4d00] animate-pulse" />
            Knowlix Command Hub
          </div>
          <div>Navigate with ↑ ↓ • Select ↵</div>
        </div>
      </div>
    </div>
  );
}
