import { lazy, Suspense } from "react";
import { useLocationSnapshot } from "../router";
import "./design-studio.css";

const HomePage = lazy(() => import("./HomePage"));
const NewRunPage = lazy(() => import("./NewRunPage"));
const RunPage = lazy(() => import("./RunPage"));
const HistoryPage = lazy(() => import("./HistoryPage"));
const ComparePage = lazy(() => import("./ComparePage"));
const SettingsPage = lazy(() => import("./SettingsPage"));

export default function DesignStudio() {
  const location = useLocationSnapshot();
  const [pathname, search = ""] = location.split("?", 2);
  const params = new URLSearchParams(search);
  const parts = pathname.replace(/^\/design-studio\/?/, "").split("/").filter(Boolean);

  let page;
  if (parts[0] === "new") {
    page = <NewRunPage key={search} pipeline={parts[1] ?? params.get("pipeline") ?? "video"} forkOf={params.get("fork")} />;
  } else if (parts[0] === "runs" && parts[1]) {
    page = <RunPage key={parts[1]} runId={parts[1]} review={params.get("review")} />;
  } else if (parts[0] === "history") {
    page = <HistoryPage />;
  } else if (parts[0] === "compare") {
    page = <ComparePage a={params.get("a")} b={params.get("b")} />;
  } else if (parts[0] === "settings") {
    page = <SettingsPage />;
  } else {
    page = <HomePage />;
  }
  return <Suspense fallback={<div className="route-loading">Loading Design Studio…</div>}>{page}</Suspense>;
}
