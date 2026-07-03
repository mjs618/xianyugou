import { create } from 'zustand';
import type { Settings } from '@/types';
import { DEFAULT_SETTINGS } from '@/types';
import { getSettings } from '@/services/settingsService';
import { getUnreadCount, getPendingSummary } from '@/services/notificationService';

interface AppState {
  settings: Settings;
  unreadCount: number;
  pendingSummary: { warrantyUrgent: number; afterSalesPending: number; rebatePending: number };
  collapsed: boolean;
  setCollapsed: (v: boolean) => void;
  loadSettings: () => Promise<void>;
  loadNotifications: () => Promise<void>;
  refreshAll: () => Promise<void>;
}

export const useAppStore = create<AppState>((set) => ({
  settings: DEFAULT_SETTINGS,
  unreadCount: 0,
  pendingSummary: { warrantyUrgent: 0, afterSalesPending: 0, rebatePending: 0 },
  collapsed: false,
  setCollapsed: (v) => set({ collapsed: v }),
  loadSettings: async () => {
    const settings = await getSettings();
    set({ settings });
  },
  loadNotifications: async () => {
    const [unreadCount, pendingSummary] = await Promise.all([getUnreadCount(), getPendingSummary()]);
    set({ unreadCount, pendingSummary });
  },
  refreshAll: async () => {
    const settings = await getSettings();
    const [unreadCount, pendingSummary] = await Promise.all([getUnreadCount(), getPendingSummary()]);
    set({ settings, unreadCount, pendingSummary });
  },
}));
