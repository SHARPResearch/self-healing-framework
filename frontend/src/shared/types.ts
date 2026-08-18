/**
 * Cross-feature domain types.
 *
 * Severity taxonomy matches root CLAUDE.md's thresholds exactly, used
 * consistently across ml-backend and decision-engine: <0.5 watch, 0.5-0.7 warn,
 * 0.7-0.85 degrade, >0.85 critical.
 *
 * Lives here rather than under features/dashboard/ because it is shared by
 * every feature (services, incidents, dependency graph, models, notifications)
 * and by shared/components/SeverityBadge.
 */
export type Severity = "watch" | "warn" | "degrade" | "critical";
