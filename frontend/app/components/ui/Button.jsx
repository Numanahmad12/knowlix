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
    "inline-flex items-center justify-center font-medium transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-500 disabled:opacity-50 disabled:pointer-events-none select-none";

  const sizeStyles = {
    sm: "text-xs px-3 py-1.5 rounded-lg gap-1.5 h-8 font-medium",
    md: "text-xs md:text-sm px-4 py-2 rounded-xl gap-2 h-10 font-semibold",
    lg: "text-sm md:text-base px-5 py-2.5 rounded-xl gap-2.5 h-12 font-semibold",
    icon: "w-9 h-9 rounded-lg p-0",
  }[size] || "px-4 py-2 rounded-xl";

  const variantStyles = {
    // Official Knowlix Primary Action: Vibrant Orange #F45B0B
    primary:
      "bg-[#f45b0b] hover:bg-[#dc4805] text-white shadow-sm hover:shadow-orange active:scale-[0.98] border border-orange-600/30",
    // Official Knowlix Secondary Action: Soft Teal Tint #A8C9C8
    secondary:
      "bg-[#f3f8f8] hover:bg-[#e5f0f0] text-[#274141] border border-[#a8c9c8] shadow-subtle active:scale-[0.98]",
    outline:
      "bg-white hover:bg-[#f3f8f8] text-[#274141] border border-[#a8c9c8] active:scale-[0.98]",
    ghost:
      "bg-transparent hover:bg-[#f3f8f8] text-[#447877] hover:text-[#0f1717]",
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
