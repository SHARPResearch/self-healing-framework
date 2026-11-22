import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  /** Rendered in place of the crashed subtree. Defaults to nothing (silent fallback). */
  fallback?: ReactNode;
  /** Name used in the console warning, so a crash here is easy to place. */
  name: string;
}

interface State {
  hasError: boolean;
}

/**
 * Contains a render crash to the subtree it wraps instead of letting React unmount the whole
 * app (the default with no boundary anywhere: one throw blanks the entire page). Wrap anything
 * that can fail for reasons outside our code -- WebGL/Three.js canvases, third-party widgets --
 * so that failure degrades instead of taking the page down.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`[${this.props.name}] crashed, showing fallback instead of blanking the page:`, error, info);
  }

  render() {
    if (this.state.hasError) return this.props.fallback ?? null;
    return this.props.children;
  }
}
