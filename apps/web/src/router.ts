import { useSyncExternalStore } from "react";

const locationValue = (): string => `${window.location.pathname}${window.location.search}`;

const subscribe = (notify: () => void): (() => void) => {
  window.addEventListener("popstate", notify);
  return () => window.removeEventListener("popstate", notify);
};

export function useLocationSnapshot(): string {
  return useSyncExternalStore(subscribe, locationValue, () => "/showcase");
}

export function navigate(path: string, options: { replace?: boolean } = {}): void {
  if (locationValue() === path) return;
  if (options.replace) window.history.replaceState(null, "", path);
  else window.history.pushState(null, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}