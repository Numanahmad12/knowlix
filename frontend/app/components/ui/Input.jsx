"use client";

import { forwardRef } from "react";

export const Input = forwardRef(function Input(
  {
    className = "",
    icon: Icon,
    rightElement,
    error,
    ...props
  },
  ref
) {
  return (
    <div className="relative w-full">
      {Icon && (
        <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[#647474] pointer-events-none">
          <Icon className="w-4 h-4" />
        </div>
      )}
      <input
        ref={ref}
        className={`w-full bg-white text-[#0f1717] placeholder-[#94a3a3] text-xs md:text-sm rounded-xl border border-[#cbd6d6] focus:border-[#a8c9c8] focus:ring-2 focus:ring-[#a8c9c8]/30 outline-none transition-all duration-150 shadow-subtle ${
          Icon ? "pl-10" : "pl-4"
        } ${rightElement ? "pr-10" : "pr-4"} py-2.5 ${
          error ? "border-rose-500 focus:border-rose-500 focus:ring-rose-500" : ""
        } ${className}`}
        {...props}
      />
      {rightElement && (
        <div className="absolute right-3 top-1/2 -translate-y-1/2">
          {rightElement}
        </div>
      )}
    </div>
  );
});
