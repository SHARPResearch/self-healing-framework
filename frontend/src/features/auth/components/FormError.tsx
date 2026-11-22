import { AlertCircle } from "lucide-react";

/** The one line of feedback under an auth form: what went wrong, in the auth service's words. */
export function FormError({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p role="alert" className="flex items-start gap-2 text-sm text-status-critical">
      <AlertCircle className="mt-0.5 size-4 shrink-0" />
      {message}
    </p>
  );
}
