import { useEffect, useState } from "react";
import { AppShell } from "@/shared/layout/AppShell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FileText, Loader2 } from "lucide-react";

interface PostMortemReport {
  decision_id: string;
  service: string;
  status: string;
  generated_at: string;
}

export function PostMortemsPage() {
  const [reports, setReports] = useState<PostMortemReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedReport, setSelectedReport] =
    useState<PostMortemReport | null>(null);
  const [reportDetails, setReportDetails] = useState("");
  const [detailsLoading, setDetailsLoading] = useState(false);

  useEffect(() => {
    const controller = new AbortController();

    const fetchReports = async () => {
      try {
        const response = await fetch(
          "http://localhost:8004/api/postmortem",
          { signal: controller.signal }
        );

        if (!response.ok) {
          throw new Error(`HTTP error: ${response.status}`);
        }

        const data = await response.json();

        const reportsArray: PostMortemReport[] = Array.isArray(
          data.reports
        )
          ? data.reports
          : [];

        setReports(reportsArray);
      } catch (error) {
        if (error instanceof Error && error.name === "AbortError") {
          return;
        }

        console.error("Failed to fetch post-mortems:", error);
        setReports([]);
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    };

    fetchReports();

    return () => controller.abort();
  }, []);

  const handleSelectReport = async (
    report: PostMortemReport
  ) => {
    setSelectedReport(report);
    setReportDetails("");
    setDetailsLoading(true);

    try {
      const response = await fetch(
        `http://localhost:8004/api/postmortem/${encodeURIComponent(
          report.decision_id
        )}`
      );

      if (!response.ok) {
        throw new Error(`HTTP error: ${response.status}`);
      }

      const data = await response.json();

      setReportDetails(
        data.markdown_report || "No details available."
      );
    } catch (error) {
      console.error("Failed to fetch report details:", error);
      setReportDetails("Failed to load report details. Please try again.");
    } finally {
      setDetailsLoading(false);
    }
  };

  return (
    <AppShell pageTitle="Post-Mortems">
      <div className="flex h-full min-h-0 flex-col gap-6 p-6 md:flex-row">
        {/* Generated Reports Sidebar */}
        <aside className="w-full shrink-0 space-y-4 overflow-y-auto md:w-1/3">
          <h2 className="text-lg font-semibold">
            Generated Reports
          </h2>

          {loading ? (
            <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading reports...
            </div>
          ) : reports.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No reports generated yet.
            </p>
          ) : (
            reports.map((report) => (
              <Card
                key={report.decision_id}
                role="button"
                tabIndex={0}
                className={`cursor-pointer transition-colors hover:bg-accent ${
                  selectedReport?.decision_id === report.decision_id
                    ? "ring-2 ring-primary"
                    : ""
                }`}
                onClick={() => handleSelectReport(report)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    handleSelectReport(report);
                  }
                }}
              >
                <CardHeader className="pb-2">
                  <CardTitle className="break-all text-sm font-medium">
                    {report.decision_id}
                  </CardTitle>
                </CardHeader>

                <CardContent className="space-y-2 text-xs text-muted-foreground">
                  <div className="flex items-center gap-2">
                    <FileText className="h-3 w-3 shrink-0" />
                    <span>{report.service}</span>
                  </div>

                  <div>
                    {report.generated_at
                      ? new Date(report.generated_at).toLocaleString()
                      : "Date unavailable"}
                  </div>

                  {report.status && (
                    <div>
                      Status: {report.status}
                    </div>
                  )}
                </CardContent>
              </Card>
            ))
          )}
        </aside>

        {/* Report Details Panel */}
        <section className="flex min-h-[400px] min-w-0 flex-1 flex-col overflow-hidden rounded-xl border bg-card md:min-h-0">
          {selectedReport ? (
            <>
              {/* Report Header */}
              <div className="shrink-0 border-b p-4">
                <h3 className="break-all text-lg font-semibold">
                  {selectedReport.decision_id}
                </h3>

                <p className="text-sm text-muted-foreground">
                  Service: {selectedReport.service}
                </p>

                {selectedReport.status && (
                  <p className="mt-1 text-xs text-muted-foreground">
                    Status: {selectedReport.status}
                  </p>
                )}
              </div>

              {/* Report Content */}
              <div className="min-h-0 flex-1 overflow-y-auto p-6">
                {detailsLoading ? (
                  <div className="flex items-center justify-center gap-2 py-10 text-muted-foreground">
                    <Loader2 className="h-5 w-5 animate-spin" />
                    Loading report details...
                  </div>
                ) : (
                  <pre className="whitespace-pre-wrap break-words font-mono text-sm leading-relaxed">
                    {reportDetails}
                  </pre>
                )}
              </div>
            </>
          ) : (
            <div className="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center text-muted-foreground">
              <FileText className="h-10 w-10 opacity-50" />

              <p className="text-sm">
                Select a report to view details
              </p>
            </div>
          )}
        </section>
      </div>
    </AppShell>
  );
}