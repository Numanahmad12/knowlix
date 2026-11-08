"use client";

import { Button } from "./Button";

export function EmptyState({
  icon: Icon,
  title,
  description,
  actionLabel,
  onAction,
  actionIcon,
}) {
  return (
    <div className="flex flex-col items-center justify-center text-center p-8 md:p-12 border border-dashed border-[#a8c9c8] rounded-2xl bg-[#fdfefe]">
      {Icon && (
        <div className="w-12 h-12 rounded-2xl bg-[#e5f0f0] border border-[#a8c9c8] text-[#375f5f] flex items-center justify-center mb-4 shadow-subtle">
          <Icon className="w-6 h-6" />
        </div>
      )}
      <h3 className="text-base font-bold text-[#0f1717] mb-1.5">{title}</h3>
      <p className="text-xs md:text-sm text-[#647474] max-w-md leading-relaxed mb-6">
        {description}
      </p>
      {actionLabel && onAction && (
        <Button onClick={onAction} icon={actionIcon} size="md">
          {actionLabel}
        </Button>
      )}
    </div>
  );
}
