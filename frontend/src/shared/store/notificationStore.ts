import { create } from "zustand";
import { notifications as initialNotifications } from "@/features/notifications/data/mockData";
import type { AppNotification } from "@/features/notifications/types";

interface NotificationState {
  notifications: AppNotification[];
  markRead: (id: string) => void;
  markAllRead: () => void;
}

/**
 * Shared so the header bell badge and the notifications page never disagree
 * about the unread count. Mirrors uiStore's shape; no persistence.
 */
export const useNotificationStore = create<NotificationState>((set) => ({
  notifications: initialNotifications,
  markRead: (id) =>
    set((state) => ({
      notifications: state.notifications.map((n) => (n.id === id ? { ...n, read: true } : n)),
    })),
  markAllRead: () =>
    set((state) => ({
      notifications: state.notifications.map((n) => ({ ...n, read: true })),
    })),
}));

export function selectUnreadCount(state: NotificationState): number {
  return state.notifications.filter((n) => !n.read).length;
}
