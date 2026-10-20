import { create } from "zustand";

export interface Toast {
  id: number;
  title: string;
  description?: string;
  variant: "default" | "success" | "error";
}

interface ToastState {
  toasts: Toast[];
  push: (t: Omit<Toast, "id">) => void;
  dismiss: (id: number) => void;
}

let seq = 0;

/**
 * Tiny local toast store. Deliberately not a new dependency — the app has no
 * toast primitive (see frontend/CLAUDE.md) and this page only needs three
 * variants plus auto-dismiss.
 */
export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  push: (t) => {
    const id = ++seq;
    set((s) => ({ toasts: [...s.toasts, { ...t, id }] }));
    setTimeout(() => set((s) => ({ toasts: s.toasts.filter((x) => x.id !== id) })), 3500);
  },
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((x) => x.id !== id) })),
}));

export function toast(
  title: string,
  variant: Toast["variant"] = "default",
  description?: string,
) {
  useToastStore.getState().push({ title, variant, description });
}
