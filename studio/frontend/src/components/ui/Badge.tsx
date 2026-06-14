import React from "react";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: "default" | "success" | "warning" | "danger" | "info" | "secondary";
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  className = "",
  variant = "default",
  ...props
}) => {
  const base = "inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border transition-colors";
  
  const variants = {
    default: "bg-slate-800 text-slate-200 border-slate-700",
    secondary: "bg-slate-750 text-slate-300 border-edge/50",
    success: "bg-pass/10 text-pass border-pass/20",
    warning: "bg-warn/10 text-warn border-warn/20",
    danger: "bg-fail/10 text-fail border-fail/20",
    info: "bg-run/10 text-run border-run/20",
  };

  return (
    <span className={`${base} ${variants[variant]} ${className}`} {...props}>
      {children}
    </span>
  );
};

export interface StatusPillProps {
  status: string;
  className?: string;
  healed?: boolean;
}

export const StatusPill: React.FC<StatusPillProps> = ({ status, className = "", healed }) => {
  const norm = status.toLowerCase();
  
  if (healed) {
    return (
      <Badge variant="warning" className={`gap-1.5 uppercase tracking-wider text-[10px] px-2.5 py-1 font-semibold ${className}`}>
        <span className="h-1.5 w-1.5 rounded-full bg-warn animate-pulse" />
        Healed
      </Badge>
    );
  }

  switch (norm) {
    case "passed":
    case "success":
    case "ok":
    case "green":
      return (
        <Badge variant="success" className={`gap-1.5 uppercase tracking-wider text-[10px] px-2.5 py-1 font-semibold ${className}`}>
          <span className="h-1.5 w-1.5 rounded-full bg-pass" />
          Passed
        </Badge>
      );
    case "failed":
    case "failure":
    case "red":
    case "error":
      return (
        <Badge variant="danger" className={`gap-1.5 uppercase tracking-wider text-[10px] px-2.5 py-1 font-semibold ${className}`}>
          <span className="h-1.5 w-1.5 rounded-full bg-fail" />
          Failed
        </Badge>
      );
    case "running":
    case "executing":
    case "active":
      return (
        <Badge variant="info" className={`gap-1.5 uppercase tracking-wider text-[10px] px-2.5 py-1 font-semibold ${className}`}>
          <span className="h-1.5 w-1.5 rounded-full bg-run animate-pulse" />
          Running
        </Badge>
      );
    case "queued":
    case "pending":
    case "scheduled":
      return (
        <Badge variant="secondary" className={`gap-1.5 uppercase tracking-wider text-[10px] px-2.5 py-1 font-semibold ${className}`}>
          <span className="h-1.5 w-1.5 rounded-full bg-slate-400" />
          Queued
        </Badge>
      );
    default:
      return (
        <Badge variant="default" className={`gap-1.5 uppercase tracking-wider text-[10px] px-2.5 py-1 font-semibold ${className}`}>
          {status}
        </Badge>
      );
  }
};
