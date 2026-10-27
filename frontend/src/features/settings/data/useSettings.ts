import { useCallback, useEffect, useState } from "react";
import {
  fetchSettings,
  updateSettings,
  reloadSettings,
  fetchSettingsAudit,
  fetchNotifications,
  PREMIUM_ACTOR,
  type ApiEngineSetting,
  type ApiSettingsAuditEntry,
  type ApiNotificationEntry,
} from "@/lib/api";

export function useSettings(pollMs = 0) {
  const [settings, setSettings] = useState<ApiEngineSetting[]>([]);
  const [groups, setGroups] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  const refetch = useCallback(() => setTick((n) => n + 1), []);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const data = await fetchSettings();
        if (!alive) return;
        setSettings(data.settings);
        setGroups(data.groups);
        setError(null);
      } catch (e: unknown) {
        if (!alive) return;
        setError(String((e as Error)?.message ?? e));
      } finally {
        if (alive) setLoading(false);
      }
    };
    load();
    if (pollMs > 0) {
      const id = setInterval(load, pollMs);
      return () => {
        alive = false;
        clearInterval(id);
      };
    }
    return () => {
      alive = false;
    };
  }, [pollMs, tick]);

  const save = useCallback(
    async (patch: Record<string, number | boolean | string>, actor = PREMIUM_ACTOR) => {
      const result = await updateSettings(patch, actor);
      setSettings(result.settings);
      return result;
    },
    [],
  );

  const reload = useCallback(async (actor = PREMIUM_ACTOR) => {
    await reloadSettings(actor);
    setTick((n) => n + 1);
  }, []);

  return { settings, groups, loading, error, refetch, save, reload };
}

export function useSettingsAudit(pollMs = 0) {
  const [entries, setEntries] = useState<ApiSettingsAuditEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const list = await fetchSettingsAudit(50);
        if (!alive) return;
        setEntries(list);
      } catch {
        /* keep previous */
      } finally {
        if (alive) setLoading(false);
      }
    };
    load();
    if (pollMs > 0) {
      const id = setInterval(load, pollMs);
      return () => {
        alive = false;
        clearInterval(id);
      };
    }
    return () => {
      alive = false;
    };
  }, [pollMs]);

  return { entries, loading };
}

export function useNotifications(pollMs = 5000) {
  const [entries, setEntries] = useState<ApiNotificationEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const list = await fetchNotifications(50);
        if (!alive) return;
        setEntries(list);
      } catch {
        /* keep previous */
      } finally {
        if (alive) setLoading(false);
      }
    };
    load();
    if (pollMs > 0) {
      const id = setInterval(load, pollMs);
      return () => {
        alive = false;
        clearInterval(id);
      };
    }
    return () => {
      alive = false;
    };
  }, [pollMs]);

  return { entries, loading };
}
