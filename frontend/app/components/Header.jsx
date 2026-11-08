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
    <header className="h-16 bg-white/95 backdrop-blur-md border-b border-[#e4ebeb] flex items-center justify-between px-6 sticky top-0 z-30 shadow-subtle">
      <div className="flex items-center gap-4">
        {/* Breadcrumbs */}
        <div className="flex items-center gap-2 text-xs md:text-sm">
          <span className="text-[#647474] font-medium">Knowlix</span>
          <span className="text-[#cbd6d6]">/</span>
          <span className="text-[#0f1717] font-bold">{viewTitles[currentView] || "Overview"}</span>
        </div>

        {activeDoc && (
          <div className="hidden lg:flex items-center gap-2 px-3 py-1 rounded-full bg-[#f3f8f8] border border-[#a8c9c8] text-xs text-[#274141] font-mono font-medium">
            <FileText className="w-3.5 h-3.5 text-[#f45b0b]" />
            <span className="max-w-[200px] truncate">{activeDoc.filename}</span>
          </div>
        )}
      </div>

      <div className="flex items-center gap-3">
        {/* Quick Search Trigger */}
        <button
          onClick={onOpenCommandPalette}
          className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-[#f8fafa] hover:bg-[#f1f5f5] text-xs text-[#647474] hover:text-[#0f1717] border border-[#e4ebeb] transition-colors"
        >
          <Search className="w-3.5 h-3.5 text-[#5a9695]" />
          <span className="hidden sm:inline">Search commands…</span>
          <kbd className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-white border border-[#cbd6d6] text-[#647474] font-bold">
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
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-[#e5f0f0] border border-[#a8c9c8] text-xs font-mono font-semibold text-[#274141]">
          <span
            className={`w-2 h-2 rounded-full ${
              health.ok ? "bg-[#f45b0b] shadow-[0_0_8px_rgba(244,91,11,0.6)]" : "bg-rose-500 animate-ping"
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
