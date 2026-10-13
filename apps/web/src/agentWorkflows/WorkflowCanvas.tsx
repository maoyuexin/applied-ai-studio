import { Bot, Code2, FileInput, FileOutput, Gavel, Lock, Search, ShieldCheck, Sparkles, User, Wrench, Zap } from "lucide-react";
import type { ReactNode } from "react";
import { stepColor, type ViewState } from "./replay";
import type { ScenarioSpec, ToolSpec } from "./types";

interface Box {
  x: number;
  y: number;
  w: number;
  h: number;
  round: boolean;
}

export type Selection = { kind: "agent" | "tool" | "node"; id: string } | null;

const CHIP_W = 196;
const CHIP_H = 28;
const CHIP_GAP = 6;

function viewBoxFor(scenario: ScenarioSpec, boxes: Record<string, Box>): string {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const [id, box] of Object.entries(boxes)) {
    const agent = scenario.agents.find((item) => item.id === id);
    const chips = agent ? agent.tools.length : 0;
    const below = chips ? 10 + chips * (CHIP_H + CHIP_GAP) : box.round ? 40 : 0;
    minX = Math.min(minX, box.x - Math.max(box.w, chips ? CHIP_W : 0) / 2 - (box.round ? 50 : 0));
    maxX = Math.max(maxX, box.x + Math.max(box.w, chips ? CHIP_W : 0) / 2 + (box.round ? 50 : 0));
    minY = Math.min(minY, box.y - box.h / 2);
    maxY = Math.max(maxY, box.y + box.h / 2 + below);
  }
  const padX = 40;
  const padY = 34;
  return `${minX - padX} ${minY - padY} ${maxX - minX + padX * 2} ${maxY - minY + padY * 2}`;
}

function nodeBoxes(scenario: ScenarioSpec): Record<string, Box> {
  const boxes: Record<string, Box> = {};
  for (const agent of scenario.agents) {
    const [x, y] = scenario.layout[agent.id];
    boxes[agent.id] = agent.kind === "chair" ? { x, y, w: 170, h: 66, round: false } : { x, y, w: 200, h: 84, round: false };
  }
  for (const node of scenario.nodes) {
    const [x, y] = scenario.layout[node.id];
    boxes[node.id] = node.kind === "human" ? { x, y, w: 84, h: 84, round: true } : { x, y, w: 150, h: 70, round: false };
  }
  return boxes;
}

function anchor(box: Box, toward: { x: number; y: number }): { x: number; y: number } {
  const dx = toward.x - box.x;
  const dy = toward.y - box.y;
  if (dx === 0 && dy === 0) return { x: box.x, y: box.y };
  if (box.round) {
    const length = Math.hypot(dx, dy);
    return { x: box.x + (dx / length) * (box.w / 2 + 2), y: box.y + (dy / length) * (box.h / 2 + 2) };
  }
  const scale = Math.min((box.w / 2 + 3) / Math.abs(dx || 1e-9), (box.h / 2 + 3) / Math.abs(dy || 1e-9));
  return { x: box.x + dx * scale, y: box.y + dy * scale };
}

function edgePath(a: Box, b: Box, bend = 0): string {
  const start = anchor(a, b);
  const end = anchor(b, a);
  if (!bend) return `M ${start.x} ${start.y} L ${end.x} ${end.y}`;
  const mx = (start.x + end.x) / 2;
  const my = (start.y + end.y) / 2;
  const length = Math.hypot(end.x - start.x, end.y - start.y) || 1;
  const nx = -(end.y - start.y) / length;
  const ny = (end.x - start.x) / length;
  return `M ${start.x} ${start.y} Q ${mx + nx * bend} ${my + ny * bend} ${end.x} ${end.y}`;
}

function toolIcon(tool: ToolSpec): ReactNode {
  switch (tool.kind) {
    case "model":
      return <Sparkles size={12} />;
    case "action":
      return <Zap size={12} />;
    case "check":
      return <ShieldCheck size={12} />;
    case "code":
      return <Code2 size={12} />;
    case "lookup":
      return <Search size={12} />;
    default:
      return <Wrench size={12} />;
  }
}

const EDGE_COLORS: Record<string, string> = {
  flow: "#5b6075",
  handoff: "#e8913c",
  chair: "#5b6075",
  approval: "#f0b429",
  return: "#f0b429",
};

export default function WorkflowCanvas({
  scenario,
  view,
  selection,
  onSelect,
}: {
  scenario: ScenarioSpec;
  view: ViewState;
  selection: Selection;
  onSelect: (selection: Selection) => void;
}) {
  const boxes = nodeBoxes(scenario);
  const tools = Object.fromEntries(scenario.tools.map((tool) => [tool.id, tool]));
  const edgeKey = (a: string, b: string) => `${a}->${b}`;
  const edgeKinds = new Map(scenario.edges.map((edge) => [edgeKey(edge.source, edge.target), edge.kind]));
  const bendFor = (source: string, target: string, kind: string) =>
    kind === "handoff" && edgeKinds.has(edgeKey(target, source)) ? 34 : kind === "handoff" ? 18 : 0;

  const transition = view.transition;
  let transitionPath: string | null = null;
  if (transition && boxes[transition.from] && boxes[transition.to]) {
    const kind = edgeKinds.get(edgeKey(transition.from, transition.to));
    const reverse = edgeKinds.get(edgeKey(transition.to, transition.from));
    if (kind) transitionPath = edgePath(boxes[transition.from], boxes[transition.to], bendFor(transition.from, transition.to, kind));
    else if (reverse) transitionPath = edgePath(boxes[transition.from], boxes[transition.to], -bendFor(transition.to, transition.from, reverse));
    else transitionPath = edgePath(boxes[transition.from], boxes[transition.to]);
  }
  const transitionColor = transition ? EDGE_COLORS[transition.kind] === "#5b6075" ? "#f5f3f0" : EDGE_COLORS[transition.kind] : "#fff";
  const pendingHuman = view.pendingApproval ? scenario.nodes.find((node) => node.kind === "human")?.id : null;

  return (
    <svg className="aw-canvas-svg" viewBox={viewBoxFor(scenario, boxes)} preserveAspectRatio="xMidYMid meet" role="img" aria-label={`${scenario.title} workflow diagram`}>
      <defs>
        {Object.entries(EDGE_COLORS).map(([kind, color]) => (
          <marker key={kind} id={`aw-arrow-${kind}`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill={color} />
          </marker>
        ))}
        <filter id="aw-glow" x="-30%" y="-30%" width="160%" height="160%">
          <feGaussianBlur stdDeviation="6" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {scenario.edges.map((edge) => {
        const a = boxes[edge.source];
        const b = boxes[edge.target];
        if (!a || !b) return null;
        const d = edgePath(a, b, bendFor(edge.source, edge.target, edge.kind));
        const live = transition && transition.from === edge.source && transition.to === edge.target;
        return (
          <g key={edgeKey(edge.source, edge.target)} className={`aw-edge aw-edge-${edge.kind}${live ? " is-live" : ""}`}>
            <path
              d={d}
              fill="none"
              stroke={EDGE_COLORS[edge.kind]}
              strokeWidth={edge.kind === "chair" ? 1.5 : 2}
              strokeDasharray={edge.kind === "approval" ? "6 5" : edge.kind === "chair" ? "2 5" : undefined}
              markerEnd={edge.kind === "chair" ? undefined : `url(#aw-arrow-${edge.kind})`}
            />
            {edge.label ? (
              <text className="aw-edge-label" x={(a.x + b.x) / 2} y={(a.y + b.y) / 2 - (edge.kind === "handoff" ? 22 : 8)} textAnchor="middle">
                {edge.label}
              </text>
            ) : null}
          </g>
        );
      })}

      {transitionPath ? (
        <g key={`t-${transition?.seq}`} className="aw-transition">
          <path d={transitionPath} fill="none" stroke={transitionColor} strokeWidth={3} className="aw-transition-trail" />
          <circle r={7} fill={transitionColor} filter="url(#aw-glow)">
            <animateMotion dur="0.85s" fill="freeze" path={transitionPath} />
          </circle>
        </g>
      ) : null}

      {scenario.agents.map((agent) => {
        const box = boxes[agent.id];
        const active = view.activeNode === agent.id;
        const visited = view.visited.has(agent.id);
        const chips = agent.tools.map((id) => tools[id]).filter(Boolean);
        return (
          <g key={agent.id} className={`aw-node aw-agent${active ? " is-active" : ""}${visited ? " is-visited" : ""}${selection?.id === agent.id ? " is-selected" : ""}`}>
            <foreignObject
              x={box.x - box.w / 2}
              y={box.y - box.h / 2}
              width={box.w}
              height={box.h}
              onClick={() => onSelect({ kind: "agent", id: agent.id })}
            >
              <button type="button" className={`aw-agent-card${agent.kind === "chair" ? " is-chair" : ""}`} style={{ ["--agent" as string]: agent.color }} aria-label={`${agent.label}: ${agent.role}`}>
                <span className="aw-agent-icon">{agent.kind === "chair" ? <Gavel size={15} /> : <Bot size={15} />}</span>
                <span className="aw-agent-text">
                  <strong>{agent.label}</strong>
                  <small>{agent.role}</small>
                </span>
              </button>
            </foreignObject>
            <g key={view.modelPulse?.agent === agent.id ? `p-${view.modelPulse.seq}` : "p"} className={view.modelPulse?.agent === agent.id ? "aw-model-badge is-pulsing" : "aw-model-badge"}>
              <circle cx={box.x + box.w / 2 - 4} cy={box.y - box.h / 2 + 4} r={12} />
              <text x={box.x + box.w / 2 - 4} y={box.y - box.h / 2 + 8} textAnchor="middle">AI</text>
            </g>
            {chips.map((tool, index) => {
              const top = box.y + box.h / 2 + 10 + index * (CHIP_H + CHIP_GAP);
              const calling = view.activeTool?.agent === agent.id && view.activeTool.tool === tool.id;
              const used = view.usedTools.has(tool.id);
              return (
                <g key={tool.id} className={`aw-chip${calling ? " is-calling" : ""}${used ? " is-used" : ""}${selection?.id === tool.id ? " is-selected" : ""}`}>
                  {calling ? (
                    <line key={`c-${view.activeTool?.seq}`} className="aw-chip-link" x1={box.x} y1={box.y + box.h / 2} x2={box.x} y2={top} stroke={stepColor(tool.step)} />
                  ) : null}
                  <foreignObject x={box.x - CHIP_W / 2} y={top} width={CHIP_W} height={CHIP_H} onClick={() => onSelect({ kind: "tool", id: tool.id })}>
                    <button type="button" className="aw-chip-card" style={{ ["--step" as string]: stepColor(tool.step) }} aria-label={`Tool ${tool.label}`}>
                      {toolIcon(tool)}
                      <span>{tool.label}</span>
                      {tool.approval ? <Lock size={11} className="aw-chip-lock" /> : null}
                    </button>
                  </foreignObject>
                </g>
              );
            })}
          </g>
        );
      })}

      {scenario.nodes.map((node) => {
        const box = boxes[node.id];
        const active = view.activeNode === node.id;
        const visited = view.visited.has(node.id);
        const waiting = pendingHuman === node.id;
        const icon =
          node.kind === "human" ? <User size={20} /> : node.kind === "input" ? <FileInput size={15} /> : node.kind === "output" ? <FileOutput size={15} /> : <Code2 size={15} />;
        return (
          <g key={node.id} className={`aw-node aw-${node.kind}${active ? " is-active" : ""}${visited ? " is-visited" : ""}${waiting ? " is-waiting" : ""}${selection?.id === node.id ? " is-selected" : ""}`}>
            {node.kind === "human" && waiting ? <circle className="aw-waiting-ring" cx={box.x} cy={box.y} r={box.w / 2 + 8} /> : null}
            <foreignObject x={box.x - box.w / 2 - (node.kind === "human" ? 50 : 0)} y={box.y - box.h / 2} width={box.w + (node.kind === "human" ? 100 : 0)} height={box.h + (node.kind === "human" ? 34 : 0)} onClick={() => onSelect({ kind: "node", id: node.id })}>
              <button type="button" className={`aw-node-card aw-node-${node.kind}`} aria-label={`${node.label}: ${node.detail}`}>
                <span className="aw-node-icon">{icon}</span>
                <span className="aw-node-label">{node.label}</span>
              </button>
            </foreignObject>
          </g>
        );
      })}
    </svg>
  );
}
