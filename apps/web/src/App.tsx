import { lazy, Suspense, useEffect } from "react";
import AppShell from "./components/AppShell";
import { navigate, useLocationSnapshot } from "./router";

const AskStudioPage = lazy(() => import("./pages/AskStudioPage"));
const DemoPlaceholderPage = lazy(() => import("./pages/DemoPlaceholderPage"));
const FitAnalyzerPage = lazy(() => import("./pages/FitAnalyzerPage"));
const FraudPage = lazy(() => import("./pages/FraudPage"));
const OnlineOrderPage = lazy(() => import("./pages/OnlineOrderPage"));
const PneumoniaPage = lazy(() => import("./pages/PneumoniaPage"));
const ShowcasePage = lazy(() => import("./pages/ShowcasePage"));
const WorkflowPage = lazy(() => import("./pages/WorkflowPage"));

const load = (page: React.ReactNode) => (
  <Suspense fallback={<div className="route-loading">Loading workspace...</div>}>
    {page}
  </Suspense>
);

export default function App() {
  const location = useLocationSnapshot();
  const pathname = location.split("?", 1)[0];
  const validPath = ["/workflow", "/demo", "/showcase", "/fit", "/ask", "/online-order", "/fraud", "/pneumonia"].includes(pathname);

  useEffect(() => {
    if (!validPath) navigate("/showcase", { replace: true });
  }, [validPath]);

  const page = pathname === "/workflow"
    ? <WorkflowPage />
    : pathname === "/pneumonia"
      ? <PneumoniaPage />
    : pathname === "/fraud"
      ? <FraudPage />
    : pathname === "/online-order"
      ? <OnlineOrderPage />
    : pathname === "/demo"
      ? <DemoPlaceholderPage />
    : pathname === "/fit"
      ? <FitAnalyzerPage />
      : pathname === "/ask"
        ? <AskStudioPage />
        : <ShowcasePage />;
  const navigationPath = pathname === "/workflow" || pathname === "/demo" || pathname === "/online-order" || pathname === "/fraud" || pathname === "/pneumonia" ? "/showcase" : pathname;

  return (
    <AppShell pathname={validPath ? navigationPath : "/showcase"}>
      {load(page)}
    </AppShell>
  );
}
