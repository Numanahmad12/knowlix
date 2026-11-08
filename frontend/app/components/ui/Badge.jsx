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
    // Teal & White brand pairings
    default: "bg-[#f3f8f8] text-[#274141] border border-[#a8c9c8]",
    exact: "bg-[#e5f0f0] text-[#274141] border border-[#a8c9c8]",
    semantic: "bg-[#f3f8f8] text-[#375f5f] border border-[#86b3b2]",
    // Orange brand accents
    miss: "bg-[#fef5f0] text-[#dc4805] border border-[rgba(244,91,11,0.35)]",
    orange: "bg-[#f45b0b] text-white border border-[#dc4805]",
    mono: "font-mono bg-[#f3f8f8] text-[#274141] border border-[#a8c9c8]",
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
