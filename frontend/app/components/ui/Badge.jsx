"use client";

export function Badge({
  children,
  variant = "default", // "default" | "exact" | "semantic" | "miss" | "orange" | "mono"
  className = "",
  size = "md", // "sm" | "md"
  icon: Icon,
}) {
  const sizeStyles = {
    sm: "text-[10px] px-2 py-0.5 gap-1 font-semibold",
    md: "text-xs px-2.5 py-1 gap-1.5 font-semibold",
  }[size] || "text-xs px-2.5 py-1";

  const variantStyles = {
    // Direction 4: pink-soft default, teal for cache semantics, orange for miss
    default: "bg-[#fdeef3] text-[#1e2a5c] border border-[#f3b8ca]",
    exact: "bg-[#dcebe9] text-[#1d4f4e] border border-[#5fa8a6]",
    semantic: "bg-[#eef6f5] text-[#1d4f4e] border border-[#2e7d7b]",
    // Orange accents
    miss: "bg-[#fff1e8] text-[#e04400] border border-[rgba(255,77,0,0.4)]",
    orange: "bg-[#ff4d00] text-white border border-[#e04400]",
    mono: "font-mono bg-[#fdeef3] text-[#1e2a5c] border border-[#f3b8ca]",
  }[variant] || "";

  return (
    <span
      className={`inline-flex items-center rounded-full select-none ${sizeStyles} ${variantStyles} ${className}`}
    >
      {Icon && <Icon className="w-3 h-3 flex-shrink-0" />}
      {children}
    </span>
  );
}
