import { useEffect, useState } from "react";
import { fetchAnomalies, fetchInfra, fetchServices } from "./api";
import { mapLiveServiceData, type LiveServiceData } from "./liveServiceData";

const EMPTY_DATA: LiveServiceData = {
  services: [],
  serviceRows: [],
  incidents: [],
};

export function useLiveServiceData(pollMs = 10_000) {
  const [data, setData] = useState(EMPTY_DATA);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    const load = async () => {
      try {
        const [services, infra, anomalies] = await Promise.all([
          fetchServices(),
          fetchInfra(),
          fetchAnomalies(),
        ]);
        if (!active) return;
        setData(mapLiveServiceData(services, infra, anomalies));
        setError(null);
      } catch (err) {
        if (!active) return;
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        if (active) setLoading(false);
      }
    };

    void load();
    const intervalId = window.setInterval(load, pollMs);
    return () => {
      active = false;
      window.clearInterval(intervalId);
    };
  }, [pollMs]);

  return { ...data, loading, error };
}
