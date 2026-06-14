import React from "react";
import { AlertTriangle } from "lucide-react";
import { Button } from "./Button";

export interface ConfirmDialogProps {
  isOpen: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  isDanger?: boolean;
  loading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
  isOpen,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  isDanger = false,
  loading = false,
  onConfirm,
  onCancel,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-xs transition-opacity"
        onClick={onCancel}
      />

      {/* Modal content */}
      <div className="relative w-full max-w-md bg-surface border border-edge/80 rounded-lg shadow-xl p-6 overflow-hidden animate-slide-in-up">
        <div className="flex gap-4">
          {isDanger && (
            <div className="flex items-center justify-center h-10 w-10 rounded-full bg-fail/10 shrink-0 text-fail">
              <AlertTriangle className="h-5 w-5" />
            </div>
          )}
          <div className="grow space-y-1.5">
            <h3 className="text-base font-semibold text-white">{title}</h3>
            <p className="text-sm text-slate-300 leading-normal">{description}</p>
          </div>
        </div>

        <div className="mt-6 flex justify-end gap-2">
          <Button variant="ghost" onClick={onCancel} disabled={loading} size="sm">
            {cancelLabel}
          </Button>
          <Button
            variant={isDanger ? "danger" : "primary"}
            onClick={onConfirm}
            loading={loading}
            size="sm"
          >
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
};
