# Applied AI Studio Web

React 19 and Vite frontend for the workflow-analysis surfaces and executable
Online Order experience.

Run the complete application from the repository root with `npm run dev`. The
Vite development server proxies catalog, agent, and order requests to their
loopback services or to Aspire-provided service references.

Important entry points:

- `src/pages/ShowcasePage.tsx` — industry workflow catalog
- `src/pages/CourseFlowPage.tsx` — detailed workflow analysis
- `src/pages/FitAnalyzerPage.tsx` — deterministic AI fit and solution design
- `src/pages/OnlineOrderPage.tsx` — customer, merchant, and scenario workspaces
- `src/pages/AskStudioPage.tsx` — sandboxed Copilot assistant
- `src/index.css` — shared application and responsive design system

Build only this workspace with:

```bash
npm run build -w @applied-ai-studio/web
```
