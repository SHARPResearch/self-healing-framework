import { Plus, Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { ModelStage } from "../types";

export type ModelFilter = "ALL" | ModelStage;

const FILTERS: { value: ModelFilter; label: string }[] = [
  { value: "ALL", label: "All" },
  { value: "STREAMING", label: "Streaming" },
  { value: "WARM_UP", label: "Warm up" },
  { value: "ARCHIVED", label: "Archived" },
];

interface ModelFilterBarProps {
  search: string;
  onSearchChange: (value: string) => void;
  filter: ModelFilter;
  onFilterChange: (value: ModelFilter) => void;
  onDeploy: () => void;
}

export function ModelFilterBar({ search, onSearchChange, filter, onFilterChange, onDeploy }: ModelFilterBarProps) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative">
          <Search className="absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search service or model..."
            className="h-9 w-56 pl-8 text-sm"
          />
        </div>

        <Tabs value={filter} onValueChange={(v) => onFilterChange(v as ModelFilter)}>
          <TabsList>
            {FILTERS.map((f) => (
              <TabsTrigger key={f.value} value={f.value}>
                {f.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      </div>

      <Button size="sm" onClick={onDeploy}>
        <Plus className="mr-1.5 size-3.5" />
        Deploy Model
      </Button>
    </div>
  );
}
