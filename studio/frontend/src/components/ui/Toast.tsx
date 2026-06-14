import React from "react";
import { CheckCircle2, AlertCircle, Info, AlertTriangle, X } from "lucide-react";
import { useAppStore } from "../../store/app";

export const ToastContainer: React.FC = () => {
  const { toasts, dismissToast } = useAppStore();

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 w-full max-w-sm">
      {toasts.map((t) => {
        const icons = {
          success: <CheckCircle2 className="h-5 w-5 text-pass shrink-0" />,
          error: <AlertCircle className="h-5 w-5 text-fail shrink-0" />,
          info: <Info className="h-5 w-5 text-run shrink-0" />,
          warning: <AlertTriangle className="h-5 w-5 text-warn shrink-0" />,
        };

        const borders = {
          success: "border-pass/20 bg-slate-900/90 text-slate-100",
          error: "border-fail/20 bg-slate-900/90 text-slate-100",
          info: "border-run/20 bg-slate-900/90 text-slate-100",
          warning: "border-warn/20 bg-slate-900/90 text-slate-100",
        };

        return (
          <div
            key={t.id}
            className={`flex items-start gap-3 p-4 rounded-lg border shadow-lg backdrop-blur-md transition-all duration-300 animate-slide-in-up ${borders[t.type]}`}
          >
            {icons[t.type]}
            <div className="grow space-y-0.5">
              {t.title && <h5 className="text-xs font-semibold text-white">{t.title}</h5>}
              <p className="text-xs text-slate-300 leading-normal">{t.message}</p>
            </div>
            <button
              onClick={() => dismissToast(t.id)}
              className="text-slate-400 hover:text-white transition-colors cursor-pointer shrink-0"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        );
      })}
    </div>
  );
};
