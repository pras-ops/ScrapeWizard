import React from "react";
import { AlertTriangle, Copy, Check, RefreshCw } from "lucide-react";
import { Button } from "./Button";

export interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description: string;
  action?: {
    label: string;
    onClick: () => void;
    icon?: React.ReactNode;
  };
  className?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon,
  title,
  description,
  action,
  className = "",
}) => {
  return (
    <div className={`flex flex-col items-center justify-center text-center p-8 border border-dashed border-edge/60 rounded-lg bg-surface/30 ${className}`}>
      {icon && <div className="text-text-muted mb-4">{icon}</div>}
      <h3 className="text-sm font-semibold text-white mb-1">{title}</h3>
      <p className="text-xs text-text-muted max-w-xs mb-6">{description}</p>
      {action && (
        <Button onClick={action.onClick} variant="secondary" size="sm" className="gap-1.5">
          {action.icon}
          {action.label}
        </Button>
      )}
    </div>
  );
};

export const LoadingSkeleton: React.FC<{ rows?: number; className?: string }> = ({
  rows = 3,
  className = "",
}) => {
  return (
    <div className={`space-y-4 animate-pulse ${className}`}>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-10 bg-slate-800/60 rounded-md border border-edge/30 w-full" />
      ))}
    </div>
  );
};

export interface ErrorStateProps {
  message: string;
  details?: string;
  onRetry?: () => void;
  className?: string;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  message,
  details,
  onRetry,
  className = "",
}) => {
  const [copied, setCopied] = React.useState(false);

  const copyDetails = () => {
    if (details) {
      navigator.clipboard.writeText(details);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className={`border border-fail/25 bg-fail/5 p-6 rounded-lg ${className}`}>
      <div className="flex items-start gap-3">
        <AlertTriangle className="h-5 w-5 text-fail shrink-0 mt-0.5" />
        <div className="space-y-1 grow">
          <h4 className="text-sm font-semibold text-white">An Error Occurred</h4>
          <p className="text-xs text-slate-300">{message}</p>
          
          {details && (
            <div className="mt-4">
              <div className="flex items-center justify-between text-[10px] font-medium text-text-muted mb-1">
                <span>ERROR DETAILS</span>
                <button
                  onClick={copyDetails}
                  className="flex items-center gap-1 hover:text-white transition-colors cursor-pointer"
                >
                  {copied ? (
                    <>
                      <Check className="h-3 w-3 text-pass" />
                      Copied!
                    </>
                  ) : (
                    <>
                      <Copy className="h-3 w-3" />
                      Copy Trace
                    </>
                  )}
                </button>
              </div>
              <pre className="bg-slate-900 border border-edge/40 rounded-sm p-3 text-[11px] font-mono text-slate-400 overflow-x-auto max-h-40">
                {details}
              </pre>
            </div>
          )}

          {onRetry && (
            <div className="pt-2">
              <Button onClick={onRetry} variant="secondary" size="sm" className="gap-1.5 mt-2">
                <RefreshCw className="h-3.5 w-3.5" />
                Retry
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
