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
      className={`fixed top-0 bottom-0 left-0 z-40 flex flex-col bg-white border-r border-[#e4ebeb] transition-all duration-300 shadow-subtle ${
        collapsed ? "w-16" : "w-64"
      }`}
    >
      {/* Brand Header */}
      <div className="h-16 flex items-center justify-between px-4 border-b border-[#e4ebeb]">
        {!collapsed && (
          <div
            className="flex items-center gap-2.5 cursor-pointer select-none"
            onClick={() => onNavigate("overview")}
          >
            {/* Knowlix Brand Mark (Teal + Orange) */}
            <div className="w-8 h-8 rounded-xl bg-[#a8c9c8] p-[1.5px] shadow-sm flex items-center justify-center">
              <div className="w-full h-full bg-white rounded-[10px] flex items-center justify-center">
                <Zap className="w-4 h-4 text-[#f45b0b] fill-[#f45b0b]" />
              </div>
            </div>
            <div className="flex flex-col">
              <div className="flex items-center gap-1.5">
                <span className="font-extrabold text-sm tracking-tight text-[#0f1717]">Knowlix</span>
                <span className="text-[10px] font-mono uppercase px-1.5 py-0.2 rounded bg-[#e5f0f0] text-[#274141] border border-[#a8c9c8] font-bold">
                  PRO
                </span>
              </div>
              <span className="text-[10px] text-[#647474]">Document Intelligence</span>
            </div>
          </div>
        )}

        {collapsed && (
          <div
            className="w-8 h-8 mx-auto rounded-xl bg-[#e5f0f0] border border-[#a8c9c8] flex items-center justify-center text-[#f45b0b] cursor-pointer"
            onClick={() => onNavigate("overview")}
          >
            <Zap className="w-4 h-4 fill-[#f45b0b]" />
          </div>
        )}

        <button
          onClick={onToggleCollapse}
          className="text-[#647474] hover:text-[#0f1717] p-1.5 rounded-lg hover:bg-[#f1f5f5] transition-colors"
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
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
              className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs md:text-sm font-semibold transition-all duration-150 select-none text-left w-full ${
                active
                  ? "bg-[#e5f0f0] text-[#274141] border border-[#a8c9c8] shadow-subtle"
                  : "text-[#447877] hover:text-[#0f1717] hover:bg-[#f8fafa] border border-transparent"
              } ${collapsed ? "justify-center px-0" : ""}`}
              title={collapsed ? item.label : undefined}
            >
              <Icon
                className={`w-4 h-4 flex-shrink-0 ${
                  active ? "text-[#f45b0b]" : "text-[#5a9695]"
                }`}
              />
              {!collapsed && <span className="flex-1 truncate">{item.label}</span>}
              {!collapsed && item.badge && (
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded-full bg-white text-[#274141] border border-[#a8c9c8] font-bold">
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Active Document Context Card */}
      {!collapsed && activeDoc && (
        <div className="p-3 mx-3 mb-3 rounded-xl bg-[#f8fafa] border border-[#a8c9c8] flex flex-col gap-1">
          <div className="flex items-center justify-between">
            <span className="text-[10px] uppercase font-mono tracking-wider text-[#647474] font-bold">
              Active Context
            </span>
            <span className="w-2 h-2 rounded-full bg-[#f45b0b] animate-pulse" />
          </div>
          <div className="text-xs font-bold text-[#0f1717] truncate" title={activeDoc.filename}>
            {activeDoc.filename}
          </div>
          <div className="text-[11px] text-[#447877] font-mono font-medium">
            {activeDoc.total_pages} pages • {activeDoc.total_chunks} chunks
          </div>
        </div>
      )}

      {/* Technical Spec Footnotes */}
      {!collapsed && (
        <div className="p-3.5 border-t border-[#e4ebeb] text-[10px] text-[#647474] font-mono flex flex-col gap-1.5 bg-[#f8fafa]">
          <div className="flex items-center justify-between">
            <span>Embeddings</span>
            <span className="text-[#274141] font-bold">ONNX 384d</span>
          </div>
          <div className="flex items-center justify-between">
            <span>Vector Cache</span>
            <span className="text-[#274141] font-bold">FAISS Cosine</span>
          </div>
          <div className="flex items-center justify-between">
            <span>LLM Engine</span>
            <span className="text-[#f45b0b] font-bold">Groq gpt-oss-120b</span>
          </div>
        </div>
      )}
    </aside>
  );
}
