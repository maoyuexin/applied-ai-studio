import { lazy, Suspense, useEffect } from "react";
import AppShell from "./components/AppShell";
import { navigate, useLocationSnapshot } from "./router";

const AskStudioPage = lazy(() => import("./pages/AskStudioPage"));
const ComplaintsPage = lazy(() => import("./pages/ComplaintsPage"));
const CreditPage = lazy(() => import("./pages/CreditPage"));
const MaintenancePage = lazy(() => import("./pages/MaintenancePage"));
const MaintenanceSimulatorPage = lazy(() => import("./pages/MaintenanceSimulatorPage"));
const DemoPlaceholderPage = lazy(() => import("./pages/DemoPlaceholderPage"));
const DesignStudio = lazy(() => import("./design/DesignStudio"));
const FitAnalyzerPage = lazy(() => import("./pages/FitAnalyzerPage"));
const ForecastPage = lazy(() => import("./pages/ForecastPage"));
const FraudPage = lazy(() => import("./pages/FraudPage"));
const OnlineOrderPage = lazy(() => import("./pages/OnlineOrderPage"));
const PneumoniaPage = lazy(() => import("./pages/PneumoniaPage"));
const PromoStudioPage = lazy(() => import("./pages/PromoStudioPage"));
const RecommendPage = lazy(() => import("./pages/RecommendPage"));
const RetailDemoPage = lazy(() => import("./pages/RetailDemoPage"));
const TransportationLabPage = lazy(() => import("./pages/TransportationLabPage"));
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
  const validPath = ["/workflow", "/demo", "/showcase", "/fit", "/ask", "/online-order", "/fraud", "/pneumonia", "/credit", "/complaints", "/maintenance", "/maintenance-simulator", "/procedures", "/forecast", "/recommendations", "/forecast-simulator", "/recommendations-simulator", "/forecast-reference", "/recommendations-reference", "/warehouse-robot", "/traffic-signal", "/ride-hail", "/promo-studio"].includes(pathname) || pathname === "/design-studio" || pathname.startsWith("/design-studio/");
  const designStudio = pathname === "/design-studio" || pathname.startsWith("/design-studio/");
  const transportationLab = pathname === "/warehouse-robot" ? "warehouse-robot"
    : pathname === "/traffic-signal" ? "traffic-signal"
    : pathname === "/ride-hail" ? "ride-hail" : null;

  useEffect(() => {
    if (!validPath) navigate("/showcase", { replace: true });
  }, [validPath]);

  if (pathname === "/maintenance-simulator") {
    return load(<MaintenanceSimulatorPage />);
  }
  if (pathname === "/forecast-simulator" || pathname === "/recommendations-simulator") {
    const kind = pathname === "/forecast-simulator" ? "forecast" : "recommendations";
    return load(<RetailDemoPage key={kind} kind={kind} standalone />);
  }

  const page = designStudio
    ? <DesignStudio />
    : pathname === "/workflow"
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
      ? <RetailDemoPage key="forecast" kind="forecast" />
    : pathname === "/recommendations"
      ? <RetailDemoPage key="recommendations" kind="recommendations" />
    : transportationLab
      ? <TransportationLabPage key={transportationLab} lab={transportationLab} />
    : pathname === "/promo-studio"
      ? <PromoStudioPage />
    : pathname === "/forecast-reference"
      ? <ForecastPage />
    : pathname === "/recommendations-reference"
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
  const navigationPath = pathname === "/workflow" || pathname === "/demo" || pathname === "/online-order" || pathname === "/fraud" || pathname === "/pneumonia" || pathname === "/credit" || pathname === "/complaints" || pathname === "/maintenance" || pathname === "/procedures" || pathname === "/forecast" || pathname === "/recommendations" || pathname === "/forecast-reference" || pathname === "/recommendations-reference" || pathname === "/promo-studio" || transportationLab ? "/showcase" : designStudio ? "/design-studio" : pathname;

  return (
    <AppShell pathname={validPath ? navigationPath : "/showcase"}>
      {load(page)}
    </AppShell>
  );
}
