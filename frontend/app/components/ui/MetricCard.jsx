"use client";

import { Card } from "./Card";

export function MetricCard({
  title,
  value,
  subvalue,
  description,
  icon: Icon,
  trend,
  color = "teal", // "teal" | "orange"
}) {
  const iconColorMap = {
    teal: "text-[#375f5f] bg-[#e5f0f0] border-[#a8c9c8]",
    orange: "text-[#f45b0b] bg-[#fef5f0] border-[rgba(244,91,11,0.25)]",
  }[color] || "text-[#375f5f] bg-[#e5f0f0] border-[#a8c9c8]";

  return (
    <Card className="flex flex-col justify-between">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-[#647474] tracking-wide">{title}</span>
        {Icon && (
          <div className={`w-8 h-8 rounded-xl border flex items-center justify-center ${iconColorMap}`}>
            <Icon className="w-4 h-4" />
          </div>
        )}
      </div>

      <div className="my-3 flex items-baseline gap-2">
        <span className="text-3xl font-extrabold font-mono text-[#0f1717] tracking-tight">{value}</span>
        {subvalue && <span className="text-xs font-mono text-[#647474]">{subvalue}</span>}
      </div>

      <div className="flex items-center justify-between text-xs text-[#647474]">
        <span className="truncate">{description}</span>
        {trend && (
          <span className="font-mono text-[11px] text-[#274141] font-semibold bg-[#e5f0f0] px-2 py-0.5 rounded-full border border-[#a8c9c8]">
            {trend}
          </span>
        )}
      </div>
    </Card>
  );
}
