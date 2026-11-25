import type { ReactNode } from "react";
import { ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight, Search, X } from "lucide-react";
import { cn } from "@/lib/utils";

export type SortDirection = "asc" | "desc";

export interface ListColumn<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  sortValue?: (row: T) => string | number | null;
  className?: string;
  headerClassName?: string;
}

export interface SortState {
  key: string;
  direction: SortDirection;
}

export interface ListTableProps<T> {
  columns: ListColumn<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  loading?: boolean;
  error?: string | null;
  emptyMessage?: string;
  sort?: SortState | null;
  onSortChange?: (sort: SortState) => void;
  onRowClick?: (row: T) => void;
  selectedKey?: string | null;
  maxHeight?: string;
}

export function ListTable<T>({
  columns,
  rows,
  rowKey,
  loading = false,
  error = null,
  emptyMessage = "No records found",
  sort = null,
  onSortChange,
  onRowClick,
  selectedKey,
  maxHeight,
}: ListTableProps<T>) {
  const colSpan = columns.length;

  const toggleSort = (column: ListColumn<T>) => {
    if (!column.sortValue || !onSortChange) return;
    const direction =
      sort?.key === column.key && sort.direction === "asc" ? "desc" : "asc";
    onSortChange({ key: column.key, direction });
  };

  return (
    <div
      className={cn("overflow-auto rounded-lg border border-border/60", maxHeight)}
      style={maxHeight ? { maxHeight } : undefined}
    >
      <table className="w-full text-sm">
        <thead className="sticky top-0 z-10 bg-muted/60 text-[10px] uppercase tracking-wider text-muted-foreground">
          <tr>
            {columns.map((column) => (
              <th
                key={column.key}
                className={cn(
                  "px-3 py-2 text-left font-medium",
                  column.sortValue && onSortChange && "cursor-pointer select-none hover:text-foreground",
                  column.headerClassName,
                )}
                onClick={() => toggleSort(column)}
              >
                <span className="inline-flex items-center gap-1">
                  {column.header}
                  {column.sortValue && onSortChange && (
                    <SortIcon active={sort?.key === column.key} direction={sort?.direction} />
                  )}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <tr>
              <td colSpan={colSpan} className="px-3 py-10 text-center text-muted-foreground">
                Loading...
              </td>
            </tr>
          ) : error ? (
            <tr>
              <td colSpan={colSpan} className="px-3 py-10 text-center text-destructive">
                {error}
              </td>
            </tr>
          ) : rows.length === 0 ? (
            <tr>
              <td colSpan={colSpan} className="px-3 py-10 text-center text-muted-foreground">
                {emptyMessage}
              </td>
            </tr>
          ) : (
            rows.map((row) => {
              const key = rowKey(row);
              return (
                <tr
                  key={key}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                  className={cn(
                    "border-t border-border/60 transition-colors",
                    onRowClick && "cursor-pointer hover:bg-accent/50",
                    selectedKey === key && "bg-accent/60",
                  )}
                >
                  {columns.map((column) => (
                    <td key={column.key} className={cn("px-3 py-2 align-middle", column.className)}>
                      {column.render(row)}
                    </td>
                  ))}
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}

function SortIcon({ active, direction }: { active: boolean; direction?: SortDirection }) {
  if (!active) return <ArrowUpDown className="size-3 opacity-40" />;
  return direction === "asc" ? (
    <ArrowUp className="size-3" />
  ) : (
    <ArrowDown className="size-3" />
  );
}

export interface TableToolbarProps {
  search: string;
  onSearchChange: (value: string) => void;
  placeholder?: string;
  dateFrom?: string;
  dateTo?: string;
  onDateFromChange?: (value: string) => void;
  onDateToChange?: (value: string) => void;
  children?: ReactNode;
}

export function TableToolbar({
  search,
  onSearchChange,
  placeholder = "Search...",
  dateFrom = "",
  dateTo = "",
  onDateFromChange,
  onDateToChange,
  children,
}: TableToolbarProps) {
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border/60 bg-muted/20 p-2">
      <div className="relative min-w-[220px] flex-1">
        <Search className="absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
        <input
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder={placeholder}
          className="h-8 w-full rounded-md border border-border/60 bg-background/70 pl-8 pr-8 text-xs outline-none placeholder:text-muted-foreground focus:border-primary/50"
        />
        {search && (
          <button
            type="button"
            onClick={() => onSearchChange("")}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            aria-label="Clear search"
          >
            <X className="size-3.5" />
          </button>
        )}
      </div>
      {(onDateFromChange || onDateToChange) && (
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <span>From</span>
          <input
            type="datetime-local"
            value={dateFrom}
            onChange={(event) => onDateFromChange?.(event.target.value)}
            className="h-8 rounded-md border border-border/60 bg-background/70 px-2 text-xs outline-none focus:border-primary/50"
          />
          <span>To</span>
          <input
            type="datetime-local"
            value={dateTo}
            onChange={(event) => onDateToChange?.(event.target.value)}
            className="h-8 rounded-md border border-border/60 bg-background/70 px-2 text-xs outline-none focus:border-primary/50"
          />
        </div>
      )}
      {children}
    </div>
  );
}

export interface PaginationProps {
  page: number;
  pageCount: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: number) => void;
}

export function Pagination({
  page,
  pageCount,
  pageSize,
  total,
  onPageChange,
  onPageSizeChange,
}: PaginationProps) {
  const start = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);
  const pages = Array.from({ length: Math.max(1, pageCount) }, (_, i) => i + 1).slice(
    0,
    7,
  );

  return (
    <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
      <div className="flex items-center gap-2">
        <span>
          Showing {start}-{end} of {total}
        </span>
        <select
          value={pageSize}
          onChange={(event) => onPageSizeChange(Number(event.target.value))}
          className="h-7 rounded-md border border-border/60 bg-background/70 px-1.5 text-xs outline-none"
        >
          {[10, 25, 50, 100].map((size) => (
            <option key={size} value={size}>
              {size}/page
            </option>
          ))}
        </select>
      </div>
      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={() => onPageChange(Math.max(1, page - 1))}
          disabled={page <= 1}
          className="inline-flex size-7 items-center justify-center rounded-md border border-border/60 disabled:opacity-40 hover:bg-accent/50"
          aria-label="Previous page"
        >
          <ChevronLeft className="size-3.5" />
        </button>
        {pages.map((value) => (
          <button
            key={value}
            type="button"
            onClick={() => onPageChange(value)}
            className={cn(
              "size-7 rounded-md border text-xs",
              value === page
                ? "border-primary/40 bg-primary/10 text-primary"
                : "border-border/60 hover:bg-accent/50",
            )}
          >
            {value}
          </button>
        ))}
        <button
          type="button"
          onClick={() => onPageChange(Math.min(pageCount, page + 1))}
          disabled={page >= pageCount}
          className="inline-flex size-7 items-center justify-center rounded-md border border-border/60 disabled:opacity-40 hover:bg-accent/50"
          aria-label="Next page"
        >
          <ChevronRight className="size-3.5" />
        </button>
      </div>
    </div>
  );
}

export function useListControls<T>(options: {
  rows: T[];
  search?: string;
  searchValues?: (row: T) => string[];
  dateField?: (row: T) => string | null | undefined;
  dateFrom?: string;
  dateTo?: string;
  sort?: SortState | null;
  sortValue?: (row: T, key: string) => string | number | null;
  page: number;
  pageSize: number;
}) {
  const {
    rows,
    search = "",
    searchValues,
    dateField,
    dateFrom,
    dateTo,
    sort,
    sortValue,
    page,
    pageSize,
  } = options;

  const needle = search.trim().toLowerCase();
  const from = dateFrom ? new Date(dateFrom).getTime() : null;
  const to = dateTo ? new Date(dateTo).getTime() : null;

  let filtered = rows.filter((row) => {
    if (needle && searchValues) {
      const haystack = searchValues(row).join(" ").toLowerCase();
      if (!haystack.includes(needle)) return false;
    }
    if (dateField && (from !== null || to !== null)) {
      const raw = dateField(row);
      if (!raw) return false;
      const time = new Date(raw).getTime();
      if (Number.isNaN(time)) return false;
      if (from !== null && time < from) return false;
      if (to !== null && time > to) return false;
    }
    return true;
  });

  if (sort) {
    filtered = [...filtered].sort((a, b) => {
      const get = (row: T): string | number | null => {
        if (sortValue) return sortValue(row, sort.key);
        const candidate = row as Record<string, unknown>;
        const value = candidate[sort.key];
        return typeof value === "number" || typeof value === "string" ? value : null;
      };
      const left = get(a);
      const right = get(b);
      if (left === null && right === null) return 0;
      if (left === null) return 1;
      if (right === null) return -1;
      const result =
        typeof left === "number" && typeof right === "number"
          ? left - right
          : String(left).localeCompare(String(right));
      return sort.direction === "asc" ? result : -result;
    });
  }

  const total = filtered.length;
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const safePage = Math.min(page, pageCount);
  const visibleRows = filtered.slice((safePage - 1) * pageSize, safePage * pageSize);
  return { visibleRows, total, pageCount, safePage };
}
