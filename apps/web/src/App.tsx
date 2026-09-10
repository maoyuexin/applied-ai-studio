import { lazy, Suspense, useEffect } from "react";
import AppShell from "./components/AppShell";
import { navigate, useLocationSnapshot } from "./router";

const AskStudioPage = lazy(() => import("./pages/AskStudioPage"));
const ComplaintsPage = lazy(() => import("./pages/ComplaintsPage"));
const CreditPage = lazy(() => import("./pages/CreditPage"));
const MaintenancePage = lazy(() => import("./pages/MaintenancePage"));
const DemoPlaceholderPage = lazy(() => import("./pages/DemoPlaceholderPage"));
const FitAnalyzerPage = lazy(() => import("./pages/FitAnalyzerPage"));
const ForecastPage = lazy(() => import("./pages/ForecastPage"));
const FraudPage = lazy(() => import("./pages/FraudPage"));
const OnlineOrderPage = lazy(() => import("./pages/OnlineOrderPage"));
const PneumoniaPage = lazy(() => import("./pages/PneumoniaPage"));
const RecommendPage = lazy(() => import("./pages/RecommendPage"));
const ProceduresPage = lazy(() => import("./pages/ProceduresPage"));
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
  const validPath = ["/workflow", "/demo", "/showcase", "/fit", "/ask", "/online-order", "/fraud", "/pneumonia", "/credit", "/complaints", "/maintenance", "/procedures", "/forecast", "/recommendations"].includes(pathname);

  useEffect(() => {
    if (!validPath) navigate("/showcase", { replace: true });
  }, [validPath]);

  const page = pathname === "/workflow"
    ? <WorkflowPage />
    : pathname === "/pneumonia"
      ? <PneumoniaPage />
    : pathname === "/credit"
      ? <CreditPage />
    : pathname === "/complaints"
      ? <ComplaintsPage />
    : pathname === "/maintenance"
      ? <MaintenancePage />
    : pathname === "/procedures"
      ? <ProceduresPage />
    : pathname === "/forecast"
      ? <ForecastPage />
    : pathname === "/recommendations"
      ? <RecommendPage />
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
  const navigationPath = pathname === "/workflow" || pathname === "/demo" || pathname === "/online-order" || pathname === "/fraud" || pathname === "/pneumonia" || pathname === "/credit" || pathname === "/complaints" || pathname === "/maintenance" || pathname === "/procedures" || pathname === "/forecast" || pathname === "/recommendations" ? "/showcase" : pathname;

  return (
    <AppShell pathname={validPath ? navigationPath : "/showcase"}>
      {load(page)}
    </AppShell>
  );
}
