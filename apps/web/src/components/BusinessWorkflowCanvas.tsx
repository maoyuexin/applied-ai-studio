import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  Maximize2,
  Minimize2,
  RotateCcw,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import type {
  CourseCase,
  CourseDecision,
  CourseWorkflowNode,
} from "@applied-ai-studio/contracts";

type LessonPhase = "map" | "judge" | "design";
type FlowView = "documented" | "actual";

interface NodeLayout {
  node: CourseWorkflowNode;
  decision?: CourseDecision;
  x: number;
  y: number;
  width: number;
  height: number;
}

const laneHeight = 112;
const minimumCanvasWidth = 1280;
const normalWidth = 132;
const normalHeight = 52;
const decisionWidth = 108;
const decisionHeight = 78;
const minimumZoom = 0.8;
const maximumZoom = 1.8;
const zoomStep = 0.2;
const fitToPanelBreakpoint = 720;

function wrapLabel(label: string, maxCharacters = 18): string[] {
  const words = label.split(/\s+/);
  const lines: string[] = [];
  let current = "";
  for (const word of words) {
    const candidate = current ? `${current} ${word}` : word;
    if (candidate.length <= maxCharacters || !current) {
      current = candidate;
    } else {
      lines.push(current);
      current = word;
    }
  }
  if (current) lines.push(current);
  return lines.slice(0, 3);
}

function nodeClass(layout: NodeLayout, phase: LessonPhase, selectedDecisionId: string): string {
  const { node, decision } = layout;
  return [
    "svg-course-node",
    `kind-${node.kind}`,
    phase === "map" || !decision ? "" : `verdict-${decision.verdict}`,
    decision?.id === selectedDecisionId ? "selected" : "",
    phase === "design" && decision && !decision.aiRelevant ? "muted" : "",
    node.decisionId ? "has-decision" : "",
  ].filter(Boolean).join(" ");
}

function edgePath(source: NodeLayout, target: NodeLayout): string {
  const sourceX = source.x + source.width;
  const sourceY = source.y + source.height / 2;
  const targetX = target.x;
  const targetY = target.y + target.height / 2;
  const distance = Math.max(42, Math.abs(targetX - sourceX) * 0.42);
  return `M ${sourceX} ${sourceY} C ${sourceX + distance} ${sourceY}, ${targetX - distance} ${targetY}, ${targetX} ${targetY}`;
}

export default function BusinessWorkflowCanvas({
  courseCase,
  view,
  phase,
  selectedDecisionId,
  onSelectDecision,
}: {
  courseCase: CourseCase;
  view: FlowView;
  phase: LessonPhase;
  selectedDecisionId: string;
  onSelectDecision: (decisionId: string) => void;
}) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const [zoom, setZoom] = useState(1);
  const [baseWidth, setBaseWidth] = useState(1050);
  const [isFullscreen, setIsFullscreen] = useState(false);

  useEffect(() => {
    const element = viewportRef.current;
    if (!element) return;
    const updateWidth = () => setBaseWidth(
      element.clientWidth >= fitToPanelBreakpoint ? element.clientWidth : 1050,
    );
    updateWidth();
    const observer = new ResizeObserver(updateWidth);
    observer.observe(element);
    return () => observer.disconnect();
  }, [isFullscreen]);

  useEffect(() => {
    if (!isFullscreen) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setIsFullscreen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [isFullscreen]);

  const adjustZoom = (delta: number) => {
    setZoom((current) => Math.min(maximumZoom, Math.max(minimumZoom, Number((current + delta).toFixed(1)))));
  };

  const decisionById = useMemo(
    () => new Map(courseCase.decisions.map((decision) => [decision.id, decision])),
    [courseCase.decisions],
  );
  const laneOrder = useMemo(
    () => new Map(courseCase.lanes.map((lane) => [lane.id, lane.order])),
    [courseCase.lanes],
  );
  const layouts = useMemo(() => {
    const values = courseCase.nodes
      .filter((node) => view === "actual" || node.documented)
      .map((node): NodeLayout => {
        const decision = node.decisionId ? decisionById.get(node.decisionId) : undefined;
        const width = node.kind === "decision" ? decisionWidth : normalWidth;
        const height = node.kind === "decision" ? decisionHeight : normalHeight;
        const lane = laneOrder.get(node.lane) ?? 0;
        return {
          node,
          decision,
          x: node.x,
          y: lane * laneHeight + (laneHeight - height) / 2,
          width,
          height,
        };
      });
    return new Map(values.map((layout) => [layout.node.id, layout]));
  }, [courseCase.nodes, decisionById, laneOrder, view]);
  const visibleEdges = courseCase.edges.filter((edge) =>
    (view === "actual" || edge.documented) && layouts.has(edge.from) && layouts.has(edge.to),
  );
  const canvasWidth = Math.max(
    minimumCanvasWidth,
    ...[...layouts.values()].map((layout) => layout.x + layout.width + 32),
  );
  const canvasHeight = courseCase.lanes.length * laneHeight;

  const canvas = (
    <div className={`workflow-canvas-shell ${isFullscreen ? "is-fullscreen" : ""}`}>
      <div className="workflow-canvas-toolbar" role="toolbar" aria-label="Workflow presentation controls">
        <button
          type="button"
          onClick={() => adjustZoom(-zoomStep)}
          disabled={zoom <= minimumZoom}
          title="Zoom out"
          aria-label="Zoom out workflow"
        >
          <ZoomOut size={16} />
        </button>
        <output aria-live="polite" aria-label="Workflow zoom level">{Math.round(zoom * 100)}%</output>
        <button
          type="button"
          onClick={() => adjustZoom(zoomStep)}
          disabled={zoom >= maximumZoom}
          title="Zoom in"
          aria-label="Zoom in workflow"
        >
          <ZoomIn size={16} />
        </button>
        <span className="toolbar-divider" aria-hidden="true" />
        <button
          type="button"
          onClick={() => setZoom(1)}
          disabled={zoom === 1}
          title="Reset zoom"
          aria-label="Reset workflow zoom"
        >
          <RotateCcw size={16} />
        </button>
        <button
          type="button"
          onClick={() => setIsFullscreen((current) => !current)}
          title={isFullscreen ? "Exit full screen" : "Enter full screen"}
          aria-label={isFullscreen ? "Exit workflow full screen" : "Open workflow full screen"}
          aria-pressed={isFullscreen}
        >
          {isFullscreen ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
        </button>
      </div>
      <div ref={viewportRef} className="business-flow-canvas" aria-label={`${courseCase.title} interactive business workflow`}>
        <div className="business-flow-zoom-surface" style={{ width: `${baseWidth * zoom}px` }}>
          <svg
            className="business-flow-svg"
            viewBox={`0 0 ${canvasWidth} ${canvasHeight}`}
            role="img"
            aria-labelledby="course-flow-title course-flow-description"
          >
        <title id="course-flow-title">{courseCase.title} business workflow</title>
        <desc id="course-flow-description">Select any decision diamond to inspect its owner, AI-fit verdict, and solution design.</desc>
        <defs>
          <pattern id="course-grid" width="18" height="18" patternUnits="userSpaceOnUse">
            <circle cx="1" cy="1" r="1" fill="#2e3140" />
          </pattern>
          {(["normal", "exception", "loop"] as const).map((kind) => (
            <marker key={kind} id={`arrow-${kind}`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" className={`arrow-${kind}`} />
            </marker>
          ))}
        </defs>

        <rect width={canvasWidth} height={canvasHeight} fill="url(#course-grid)" />
        {courseCase.lanes.map((lane) => (
          <g key={lane.id} className="svg-flow-lane">
            <rect x="1" y={lane.order * laneHeight + 1} width={canvasWidth - 2} height={laneHeight - 4} rx="4" />
            <text x="12" y={lane.order * laneHeight + 18}>{lane.label}</text>
          </g>
        ))}

        <g className="svg-flow-edges" aria-hidden="true">
          {visibleEdges.map((edge) => {
            const source = layouts.get(edge.from)!;
            const target = layouts.get(edge.to)!;
            const labelX = (source.x + source.width + target.x) / 2 + (edge.labelDx ?? 0);
            const labelY = (source.y + source.height / 2 + target.y + target.height / 2) / 2 - 7 + (edge.labelDy ?? 0);
            return (
              <g key={edge.id} className={`svg-business-edge edge-${edge.kind}`}>
                <path d={edgePath(source, target)} markerEnd={`url(#arrow-${edge.kind})`} />
                {edge.label ? <text x={labelX} y={labelY} textAnchor="middle">{edge.label}</text> : null}
              </g>
            );
          })}
        </g>

        <g className="svg-flow-nodes">
          {[...layouts.values()].map((layout) => {
            const { node, decision, x, y, width, height } = layout;
            const lines = wrapLabel(node.label, node.kind === "decision" ? 16 : 19);
            const firstLineY = height / 2 - ((lines.length - 1) * 6);
            const selectable = Boolean(node.decisionId);
            const selectDecision = () => {
              if (node.decisionId) onSelectDecision(node.decisionId);
            };
            return (
              <g
                key={node.id}
                transform={`translate(${x} ${y})`}
                className={nodeClass(layout, phase, selectedDecisionId)}
                aria-label={selectable ? `${node.label}. ${decision?.verdictLabel}. Select to inspect.` : node.label}
                onClick={selectDecision}
              >
                {node.kind === "decision" ? (
                  <polygon className="svg-node-shape" points={`${width / 2},0 ${width},${height / 2} ${width / 2},${height} 0,${height / 2}`} />
                ) : (
                  <rect className="svg-node-shape" width={width} height={height} rx={node.kind === "start" || node.kind === "outcome" ? height / 2 : 5} />
                )}
                <text className="svg-node-label" x={width / 2} y={firstLineY} textAnchor="middle">
                  {lines.map((line, index) => <tspan key={line} x={width / 2} dy={index === 0 ? 0 : 12}>{line}</tspan>)}
                </text>
                {node.decisionId ? (
                  <text className="svg-node-verdict" x={width / 2} y={height + 12} textAnchor="middle">
                    {phase === "map" ? "decision" : decision?.verdictLabel}
                  </text>
                ) : null}
              </g>
            );
          })}
        </g>
          </svg>
        </div>
      </div>
    </div>
  );

  return isFullscreen ? createPortal(canvas, document.body) : canvas;
}