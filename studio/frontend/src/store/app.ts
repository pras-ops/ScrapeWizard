import { create } from "zustand";

export interface ToastMessage {
  id: string;
  type: "success" | "error" | "info" | "warning";
  title?: string;
  message: string;
  duration?: number;
}

interface AppState {
  toasts: ToastMessage[];
  pushToast: (toast: Omit<ToastMessage, "id">) => void;
  dismissToast: (id: string) => void;
}

export const useAppStore = create<AppState>((set) => ({
  toasts: [],
  pushToast: (toast) => {
    const id = Math.random().toString(36).substring(2, 9);
    const newToast = { ...toast, id };
    
    set((state) => ({
      toasts: [...state.toasts, newToast],
    }));

    // Auto dismiss
    const duration = toast.duration ?? 4000;
    if (duration > 0) {
      setTimeout(() => {
        set((state) => ({
          toasts: state.toasts.filter((t) => t.id !== id),
        }));
      }, duration);
    }
  },
  dismissToast: (id) =>
    set((state) => ({
      toasts: state.toasts.filter((t) => t.id !== id),
    })),
}));

// Quick access helpers
export const toast = {
  success: (message: string, title?: string) =>
    useAppStore.getState().pushToast({ type: "success", message, title }),
  error: (message: string, title?: string) =>
    useAppStore.getState().pushToast({ type: "error", message, title, duration: 6000 }),
  info: (message: string, title?: string) =>
    useAppStore.getState().pushToast({ type: "info", message, title }),
  warn: (message: string, title?: string) =>
    useAppStore.getState().pushToast({ type: "warning", message, title }),
};
