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
 * App-wide toast store. Deliberately not a new dependency — the app has no
 * toast primitive (see frontend/CLAUDE.md) and callers only need three
 * variants plus auto-dismiss. Lifted to `shared/` so any feature (rules,
 * settings, …) can raise one; `features/rules/components/toast.ts` re-exports
 * this to keep the existing imports working.
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
