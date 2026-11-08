"use client";

import {
  BarChart3,
  BookOpen,
  ChevronLeft,
  ChevronRight,
  Database,
  FileText,
  LayoutDashboard,
  Settings,
  ShieldCheck,
  Zap,
} from "lucide-react";
import { Badge } from "./ui/Badge";

export function Sidebar({
  currentView,
  onNavigate,
  collapsed,
  onToggleCollapse,
  documentsCount = 0,
  cacheEntriesCount = 0,
  activeDoc = null,
}) {
  const navItems = [
    { id: "overview", label: "Overview", icon: LayoutDashboard },
    {
      id: "documents",
      label: "My Documents",
      icon: FileText,
      badge: documentsCount > 0 ? documentsCount : null,
    },
    { id: "workspace", label: "AI Workspace", icon: BookOpen },
    {
      id: "cache",
      label: "Semantic Cache",
      icon: Zap,
      badge: cacheEntriesCount > 0 ? cacheEntriesCount : null,
    },
    { id: "analytics", label: "Analytics & Radar", icon: BarChart3 },
    { id: "guardrails", label: "Security & Gates", icon: ShieldCheck },
    { id: "settings", label: "System Settings", icon: Settings },
  ];

  return (
    <aside
      className={`fixed top-0 bottom-0 left-0 z-40 flex flex-col bg-white border-r border-[#e8dfe4] transition-[width] duration-300 shadow-subtle ${
        collapsed ? "w-16" : "w-64"
      }`}
    >
      {/* Brand Header */}
      <div className="h-16 flex items-center justify-between px-4 border-b border-[#e8dfe4]">
        {!collapsed && (
          <button
            type="button"
            className="flex items-center gap-2.5 cursor-pointer select-none bg-transparent p-0 text-left"
            onClick={() => onNavigate("overview")}
            aria-label="Go to overview"
          >
            {/* Knowlix Brand Mark — Direction 4: pink field, navy border */}
            <div className="w-8 h-8 rounded-xl bg-[#f5c9d6] border-[1.5px] border-[#1e2a5c] p-[1.5px] shadow-sm flex items-center justify-center">
              <div className="w-full h-full bg-white rounded-[10px] flex items-center justify-center">
                <Zap className="w-4 h-4 text-[#ff4d00] fill-[#ff4d00]" />
              </div>
            </div>
            <div className="flex flex-col">
              <div className="flex items-center gap-1.5">
                <span className="font-display text-[26px] leading-none tracking-wide text-[#1e2a5c]">KNOWLIX<span className="text-[#ff4d00]">.</span></span>
                <span className="text-[10px] font-mono uppercase px-1.5 py-0.2 rounded bg-[#fdeef3] text-[#1e2a5c] border border-[#f3b8ca] font-bold">
                  PRO
                </span>
              </div>
              <span className="text-[10px] text-[#6b7194]">Document Intelligence</span>
            </div>
          </button>
        )}

        {collapsed && (
          <button
            type="button"
            className="w-8 h-8 mx-auto rounded-xl bg-[#fdeef3] border border-[#f3b8ca] flex items-center justify-center text-[#ff4d00] cursor-pointer"
            onClick={() => onNavigate("overview")}
            aria-label="Go to overview"
          >
            <Zap className="w-4 h-4 fill-[#ff4d00]" />
          </button>
        )}

        <button
          onClick={onToggleCollapse}
          className="text-[#6b7194] hover:text-[#232b4a] p-1.5 rounded-lg hover:bg-[#fdeef3] transition-colors"
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>
      </div>

      {/* Navigation List */}
      <nav className="p-3 flex-1 flex flex-col gap-1 overflow-y-auto">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = currentView === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs md:text-sm font-semibold transition-[background-color,border-color,color,box-shadow] duration-150 select-none text-left w-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#ff4d00] ${
                active
                  ? "bg-[#fdeef3] text-[#1e2a5c] border border-[#f3b8ca] shadow-subtle"
                  : "text-[#2e7d7b] hover:text-[#232b4a] hover:bg-[#fff9f3] border border-transparent"
              } ${collapsed ? "justify-center px-0" : ""}`}
              title={collapsed ? item.label : undefined}
            >
              <Icon
                className={`w-4 h-4 flex-shrink-0 ${
                  active ? "text-[#ff4d00]" : "text-[#2e7d7b]"
                }`}
              />
              {!collapsed && <span className="flex-1 truncate">{item.label}</span>}
              {!collapsed && item.badge && (
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded-full bg-white text-[#1e2a5c] border border-[#f3b8ca] font-bold">
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Active Document Context Card */}
      {!collapsed && activeDoc && (
        <div className="p-3 mx-3 mb-3 rounded-xl bg-[#fff9f3] border border-[#f3b8ca] flex flex-col gap-1">
          <div className="flex items-center justify-between">
            <span className="text-[10px] uppercase font-mono tracking-wider text-[#6b7194] font-bold">
              Active Context
            </span>
            <span className="w-2 h-2 rounded-full bg-[#ff4d00] animate-pulse" />
          </div>
          <div className="text-xs font-bold text-[#232b4a] truncate" title={activeDoc.filename}>
            {activeDoc.filename}
          </div>
          <div className="text-[11px] text-[#2e7d7b] font-mono font-medium">
            {activeDoc.total_pages} pages • {activeDoc.total_chunks} chunks
          </div>
        </div>
      )}

      {/* Technical Spec Footnotes */}
      {!collapsed && (
        <div className="p-3.5 border-t border-[#e8dfe4] text-[10px] text-[#6b7194] font-mono flex flex-col gap-1.5 bg-[#fff9f3]">
          <div className="flex items-center justify-between">
            <span>Embeddings</span>
            <span className="text-[#1e2a5c] font-bold">ONNX 384d</span>
          </div>
          <div className="flex items-center justify-between">
            <span>Vector Cache</span>
            <span className="text-[#1e2a5c] font-bold">FAISS Cosine</span>
          </div>
          <div className="flex items-center justify-between">
            <span>LLM Engine</span>
            <span className="text-[#ff4d00] font-bold">Groq gpt-oss-120b</span>
          </div>
        </div>
      )}
    </aside>
  );
}
