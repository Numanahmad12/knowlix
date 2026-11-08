"use client";

export function Card({
  children,
  className = "",
  hoverable = false,
  padding = "p-5",
  onClick,
  ...props
}) {
  return (
    <div
      onClick={onClick}
      className={`rounded-2xl border border-[#e4ebeb] bg-white shadow-card ${
        hoverable
          ? "hover:border-[#a8c9c8] hover:shadow-card-hover transition-all duration-200 cursor-pointer"
          : ""
      } ${padding} ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}
