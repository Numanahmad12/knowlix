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
      className={`rounded-2xl border border-[#e8dfe4] bg-white shadow-card ${
        hoverable
          ? "hover:border-[#f3b8ca] hover:shadow-card-hover transition-[border-color,box-shadow] duration-200 cursor-pointer"
          : ""
      } ${padding} ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}
