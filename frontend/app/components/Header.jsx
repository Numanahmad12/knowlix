"use client";

import { FileText, Search, Sparkles } from "lucide-react";
import { Button } from "./ui/Button";

export function Header({
  currentView,
  onOpenCommandPalette,
  onLoadSample,
  analyzing,
  health,
  activeDoc,
}) {
  const viewTitles = {
    overview: "Dashboard Overview",
    documents: "My Documents",
    workspace: "AI Workspace Studio",
    cache: "Semantic Cache Engine",
    analytics: "Analytics & Radar",
    guardrails: "Security & Guardrails",
    settings: "System Settings",
  };

  return (
    <header className="h-16 bg-white/95 backdrop-blur-md border-b border-[#e8dfe4] flex items-center justify-between px-6 sticky top-0 z-30 shadow-subtle">
      <div className="flex items-center gap-4">
        {/* Breadcrumbs */}
        <div className="flex items-center gap-2 text-xs md:text-sm">
          <span className="text-[#6b7194] font-medium">Knowlix</span>
          <span className="text-[#e8dfe4]">/</span>
          <span className="text-[#232b4a] font-bold">{viewTitles[currentView] || "Overview"}</span>
        </div>

        {activeDoc && (
          <div className="hidden lg:flex items-center gap-2 px-3 py-1 rounded-full bg-[#fdeef3] border border-[#f3b8ca] text-xs text-[#1e2a5c] font-mono font-medium">
            <FileText className="w-3.5 h-3.5 text-[#ff4d00]" />
            <span className="max-w-[200px] truncate">{activeDoc.filename}</span>
          </div>
        )}
      </div>

      <div className="flex items-center gap-3">
        {/* Quick Search Trigger */}
        <button
          onClick={onOpenCommandPalette}
          className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-[#fff9f3] hover:bg-[#fdeef3] text-xs text-[#6b7194] hover:text-[#232b4a] border border-[#e8dfe4] transition-colors"
        >
          <Search className="w-3.5 h-3.5 text-[#2e7d7b]" />
          <span className="hidden sm:inline">Search commands…</span>
          <kbd className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-white border border-[#e8dfe4] text-[#6b7194] font-bold">
            ⌘K
          </kbd>
        </button>

        {/* Load Sample Button */}
        <Button
          variant="secondary"
          size="sm"
          onClick={onLoadSample}
          loading={analyzing}
          icon={Sparkles}
        >
          <span className="hidden sm:inline">Try Sample PDF</span>
          <span className="sm:hidden">Sample</span>
        </Button>

        {/* Backend Online Status Pill */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-[#fdeef3] border border-[#f3b8ca] text-xs font-mono font-semibold text-[#1e2a5c]">
          <span
            className={`w-2 h-2 rounded-full ${
              health.ok ? "bg-[#ff4d00] shadow-[0_0_8px_rgba(244,91,11,0.6)]" : "bg-rose-500 animate-ping"
            }`}
          />
          <span className="hidden md:inline">
            {health.ok ? "FastAPI Online" : "Connecting..."}
          </span>
        </div>
      </div>
    </header>
  );
}
