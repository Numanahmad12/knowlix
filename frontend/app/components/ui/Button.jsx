"use client";

import { forwardRef } from "react";

export const Button = forwardRef(function Button(
  {
    children,
    variant = "primary", // "primary" (Orange) | "secondary" (Teal tint) | "outline" | "ghost" | "danger"
    size = "md", // "sm" | "md" | "lg" | "icon"
    className = "",
    disabled = false,
    loading = false,
    icon: Icon,
    iconPosition = "left",
    ...props
  },
  ref
) {
  const baseStyles =
    "inline-flex items-center justify-center font-medium transition-[background-color,border-color,box-shadow,transform] duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#ff4d00] disabled:opacity-50 disabled:pointer-events-none select-none";

  const sizeStyles = {
    sm: "text-xs px-3 py-1.5 rounded-full gap-1.5 h-8 font-medium",
    md: "text-xs md:text-sm px-4 py-2 rounded-full gap-2 h-10 font-semibold",
    lg: "text-sm md:text-base px-5 py-2.5 rounded-full gap-2.5 h-12 font-semibold",
    icon: "w-9 h-9 rounded-full p-0",
  }[size] || "px-4 py-2 rounded-full";

  const variantStyles = {
    // Direction 4 Primary Action: Navy #1E2A5C
    primary:
      "bg-[#1e2a5c] hover:bg-[#16224a] text-white shadow-sm hover:shadow-card active:scale-[0.98] border border-[#1e2a5c]",
    // Direction 4 Secondary Action: Vivid Orange #FF4D00
    secondary:
      "bg-[#ff4d00] hover:bg-[#e04400] text-white border border-[#e04400]/30 shadow-orange active:scale-[0.98]",
    outline:
      "bg-white hover:bg-[#fdeef3] text-[#1e2a5c] border border-[#1e2a5c] active:scale-[0.98]",
    ghost:
      "bg-transparent hover:bg-[#fdeef3] text-[#4a5170] hover:text-[#1e2a5c]",
    danger:
      "bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 active:scale-[0.98]",
  }[variant] || "";

  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={`${baseStyles} ${sizeStyles} ${variantStyles} ${className}`}
      {...props}
    >
      {loading ? (
        <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
      ) : (
        <>
          {Icon && iconPosition === "left" && <Icon className="w-4 h-4 flex-shrink-0" />}
          {children}
          {Icon && iconPosition === "right" && <Icon className="w-4 h-4 flex-shrink-0" />}
        </>
      )}
    </button>
  );
});
