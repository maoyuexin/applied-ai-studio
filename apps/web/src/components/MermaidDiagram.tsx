import { useEffect, useId, useState } from "react";
import mermaid from "mermaid";
import type { WorkflowGraph } from "@applied-ai-studio/contracts";

mermaid.initialize({
  startOnLoad: false,
  securityLevel: "strict",
  theme: "base",
  themeVariables: {
    background: "#181a20",
    primaryColor: "#222530",
    primaryTextColor: "#f5f3f0",
    primaryBorderColor: "#3a3e52",
    lineColor: "#7eaeb8",
    secondaryColor: "#262a35",
    tertiaryColor: "#111318",
    fontFamily: "Inter, sans-serif",
    fontSize: "13px",
  },
  flowchart: { curve: "basis", htmlLabels: false },
});

const safeLabel = (value: string): string => value.replace(/["<>]/g, "").slice(0, 80);
const safeId = (value: string): string => value.replace(/[^a-zA-Z0-9_]/g, "_");

export function graphToMermaid(graph: WorkflowGraph): string {
  const lines = ["flowchart LR"];
  for (const node of graph.nodes) {
    lines.push(`  ${safeId(node.id)}["${safeLabel(node.label)}"]`);
  }
  for (const edge of graph.edges) {
    const label = edge.label ? `|"${safeLabel(edge.label)}"|` : "";
    lines.push(`  ${safeId(edge.from)} -->${label} ${safeId(edge.to)}`);
  }
  for (const node of graph.nodes) {
    lines.push(`  class ${safeId(node.id)} ${node.kind}`);
  }
  lines.push("  classDef input fill:#222530,stroke:#7eaeb8,color:#f5f3f0");
  lines.push("  classDef process fill:#222530,stroke:#8e90a0,color:#f5f3f0");
  lines.push("  classDef ai fill:#33261e,stroke:#e8913c,color:#f5f3f0");
  lines.push("  classDef human fill:#1d3034,stroke:#7eaeb8,color:#f5f3f0");
  lines.push("  classDef system fill:#292735,stroke:#c0527f,color:#f5f3f0");
  lines.push("  classDef output fill:#203027,stroke:#4ade80,color:#f5f3f0");
  return lines.join("\n");
}

export default function MermaidDiagram({ graph, label }: { graph: WorkflowGraph; label: string }) {
  const id = useId().replace(/:/g, "");
  const [svg, setSvg] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const renderId = `flow-${id}-${Date.now()}`;
    void mermaid
      .render(renderId, graphToMermaid(graph))
      .then(({ svg: rendered }) => {
        if (active) {
          setSvg(rendered);
          setError(null);
        }
      })
      .catch(() => {
        if (active) setError("Workflow diagram could not be rendered.");
      });
    return () => {
      active = false;
    };
  }, [graph, id]);

  if (error) return <div className="inline-error">{error}</div>;
  if (!svg) return <div className="diagram-loading">Rendering workflow...</div>;
  return <div className="mermaid-diagram" role="img" aria-label={label} dangerouslySetInnerHTML={{ __html: svg }} />;
}