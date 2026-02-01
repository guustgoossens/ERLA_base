import { useCallback, useRef, useEffect, useState } from "react";
import { useQuery } from "convex/react";
import ForceGraph3D from "react-force-graph-3d";
import * as THREE from "three";
import { api } from "../../convex/_generated/api";
import { Id } from "../../convex/_generated/dataModel";
import { DetailPanel } from "./DetailPanel";
import { EventFeed } from "./EventFeed";
import { StatsPanel } from "./StatsPanel";

interface ResearchGraphProps {
  sessionId: Id<"sessions">;
  onBack: () => void;
}

type NodeData = {
  id: string;
  type: string;
  label: string;
  color: string;
  size: number;
  data: Record<string, unknown>;
  x?: number;
  y?: number;
  z?: number;
};

type LinkData = {
  source: string | NodeData;
  target: string | NodeData;
  type: string;
};

export function ResearchGraph({ sessionId, onBack }: ResearchGraphProps) {
  const graphData = useQuery(api.graph.getFullGraph, { sessionId });
  const session = useQuery(api.sessions.getById, { id: sessionId });
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const fgRef = useRef<any>(null);
  const [selectedNode, setSelectedNode] = useState<NodeData | null>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });

  useEffect(() => {
    const updateDimensions = () => {
      const graphContainer = document.getElementById("graph-container");
      if (graphContainer) {
        setDimensions({
          width: graphContainer.clientWidth,
          height: graphContainer.clientHeight,
        });
      }
    };
    updateDimensions();
    window.addEventListener("resize", updateDimensions);
    return () => window.removeEventListener("resize", updateDimensions);
  }, []);

  const handleNodeClick = useCallback(
    (node: NodeData) => {
      setSelectedNode(node);
      // Focus camera on node
      if (fgRef.current && node.x !== undefined) {
        const distance = 150;
        const distRatio = 1 + distance / Math.hypot(node.x, node.y ?? 0, node.z ?? 0);
        fgRef.current.cameraPosition(
          {
            x: node.x * distRatio,
            y: (node.y ?? 0) * distRatio,
            z: (node.z ?? 0) * distRatio,
          },
          { x: node.x, y: node.y ?? 0, z: node.z ?? 0 },
          1000
        );
      }
    },
    [fgRef]
  );

  const nodeThreeObject = useCallback((node: NodeData) => {
    const group = new THREE.Group();

    if (node.type === "branch") {
      // Branch: Large sphere with optional glow
      const geometry = new THREE.SphereGeometry(node.size / 2);
      const material = new THREE.MeshLambertMaterial({
        color: node.color,
        transparent: true,
        opacity: 0.9,
      });
      const sphere = new THREE.Mesh(geometry, material);
      group.add(sphere);

      // Add glow for running branches
      if ((node.data.status as string) === "running") {
        const glowGeometry = new THREE.SphereGeometry(node.size / 2 + 2);
        const glowMaterial = new THREE.MeshBasicMaterial({
          color: node.color,
          transparent: true,
          opacity: 0.3,
        });
        const glow = new THREE.Mesh(glowGeometry, glowMaterial);
        group.add(glow);
      }
    } else if (node.type === "paper") {
      // Paper: Colored sphere based on groundedness
      const geometry = new THREE.SphereGeometry(node.size / 2);
      const material = new THREE.MeshLambertMaterial({
        color: node.color,
        transparent: true,
        opacity: 0.85,
      });
      const sphere = new THREE.Mesh(geometry, material);
      group.add(sphere);
    } else if (node.type === "hypothesis") {
      // Hypothesis: Sphere with ring
      const geometry = new THREE.SphereGeometry(node.size / 2);
      const material = new THREE.MeshLambertMaterial({
        color: node.color,
        transparent: true,
        opacity: 0.9,
      });
      const sphere = new THREE.Mesh(geometry, material);
      group.add(sphere);

      // Add ring
      const ringGeometry = new THREE.TorusGeometry(node.size / 2 + 1, 0.3, 8, 32);
      const ringMaterial = new THREE.MeshBasicMaterial({
        color: "#ffffff",
        transparent: true,
        opacity: 0.4,
      });
      const ring = new THREE.Mesh(ringGeometry, ringMaterial);
      ring.rotation.x = Math.PI / 2;
      group.add(ring);
    }

    return group;
  }, []);

  const linkColor = useCallback((link: LinkData) => {
    switch (link.type) {
      case "branch_split":
        return "#60a5fa";
      case "paper_in_branch":
        return "#4ade80";
      case "hypothesis_from_branch":
        return "#c084fc";
      case "hypothesis_support":
        return "#f472b6";
      default:
        return "#6b7280";
    }
  }, []);

  const nodeLabel = useCallback((node: NodeData) => {
    const typeLabels: Record<string, string> = {
      branch: "Branch",
      paper: "Paper",
      hypothesis: "Hypothesis",
    };
    const iterationNumber = node.data.iterationNumber as number | undefined;
    const iterationBadge = iterationNumber !== undefined
      ? `<span style="background: #1e3a5f; color: #60a5fa; padding: 2px 6px; border-radius: 10px; font-size: 10px; margin-left: 8px;">Iter ${iterationNumber}</span>`
      : "";
    const groundedness = node.type === "paper" ? node.data.groundedness as number | undefined : undefined;
    const groundednessBadge = groundedness !== undefined
      ? `<div style="color: #9ca3af; font-size: 10px; margin-top: 4px;">Groundedness: ${(groundedness * 100).toFixed(0)}%</div>`
      : "";
    const confidence = node.type === "hypothesis" ? node.data.confidence as number | undefined : undefined;
    const confidenceBadge = confidence !== undefined
      ? `<div style="color: #9ca3af; font-size: 10px; margin-top: 4px;">Confidence: ${(confidence * 100).toFixed(0)}%</div>`
      : "";
    return `<div style="background: rgba(0,0,0,0.9); padding: 10px 14px; border-radius: 8px; max-width: 320px; border: 1px solid #374151;">
      <div style="color: ${node.color}; font-weight: bold; margin-bottom: 4px; display: flex; align-items: center;">${typeLabels[node.type]}${iterationBadge}</div>
      <div style="color: white; font-size: 12px; line-height: 1.4;">${node.label}</div>
      ${groundednessBadge}${confidenceBadge}
    </div>`;
  }, []);

  if (!graphData || !session) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-900">
        <div className="text-xl text-gray-400">Loading graph...</div>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-gray-900">
      {/* Left sidebar - Stats */}
      <div className="w-64 border-r border-gray-700 flex flex-col">
        <div className="p-4 border-b border-gray-700">
          <button
            onClick={onBack}
            className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors"
          >
            <span>&larr;</span>
            <span>Back to Sessions</span>
          </button>
        </div>
        <div className="p-4 border-b border-gray-700">
          <h2 className="text-lg font-semibold text-white truncate">
            {session.initialQuery}
          </h2>
          <div
            className={`inline-flex items-center gap-2 mt-2 px-2 py-1 rounded text-sm ${
              session.status === "running"
                ? "bg-cyan-900 text-cyan-300 status-running"
                : session.status === "completed"
                  ? "bg-green-900 text-green-300"
                  : session.status === "failed"
                    ? "bg-red-900 text-red-300"
                    : "bg-gray-700 text-gray-300"
            }`}
          >
            <span
              className={`w-2 h-2 rounded-full ${
                session.status === "running"
                  ? "bg-cyan-400"
                  : session.status === "completed"
                    ? "bg-green-400"
                    : session.status === "failed"
                      ? "bg-red-400"
                      : "bg-gray-400"
              }`}
            />
            {session.status}
          </div>
        </div>
        <StatsPanel stats={graphData.stats} />
      </div>

      {/* Main graph area */}
      <div className="flex-1 flex flex-col">
        <div id="graph-container" className="flex-1 relative">
          <ForceGraph3D
            ref={fgRef}
            width={dimensions.width}
            height={dimensions.height}
            graphData={{
              nodes: graphData.nodes as NodeData[],
              links: graphData.links as LinkData[],
            }}
            nodeThreeObject={nodeThreeObject}
            nodeLabel={nodeLabel}
            linkColor={linkColor}
            linkWidth={1.5}
            linkDirectionalParticles={2}
            linkDirectionalParticleSpeed={0.005}
            linkDirectionalParticleWidth={2}
            onNodeClick={handleNodeClick}
            backgroundColor="#111827"
            d3AlphaDecay={0.02}
            d3VelocityDecay={0.4}
            warmupTicks={100}
            cooldownTicks={200}
            cooldownTime={3000}
            enablePointerInteraction={true}
          />
        </div>
      </div>

      {/* Right sidebar - Details & Events */}
      <div className="w-80 border-l border-gray-700 flex flex-col">
        <DetailPanel node={selectedNode} />
        <EventFeed sessionId={sessionId} />
      </div>
    </div>
  );
}
