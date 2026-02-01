interface NodeData {
  id: string;
  type: string;
  label: string;
  color: string;
  size: number;
  data: Record<string, unknown>;
}

interface DetailPanelProps {
  node: NodeData | null;
}

function ProgressBar({ value, color }: { value: number; color: string }) {
  return (
    <div className="w-full h-2 bg-gray-700 rounded-full overflow-hidden">
      <div
        className="h-full progress-bar rounded-full"
        style={{
          width: `${Math.min(100, value * 100)}%`,
          backgroundColor: color,
        }}
      />
    </div>
  );
}

export function DetailPanel({ node }: DetailPanelProps) {
  if (!node) {
    return (
      <div className="flex-1 p-4 border-b border-gray-700">
        <h3 className="text-lg font-semibold text-gray-400 mb-2">Details</h3>
        <p className="text-gray-500 text-sm">Click a node to see details</p>
      </div>
    );
  }

  const renderBranchDetails = () => {
    const data = node.data;
    return (
      <div className="space-y-3">
        <div>
          <label className="text-xs text-gray-500 uppercase">Query</label>
          <p className="text-gray-200 text-sm">{data.query as string}</p>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-gray-500 uppercase">Status</label>
            <p
              className={`text-sm font-medium ${
                data.status === "running"
                  ? "text-cyan-400"
                  : data.status === "completed"
                    ? "text-green-400"
                    : data.status === "paused"
                      ? "text-amber-400"
                      : "text-gray-400"
              }`}
            >
              {data.status as string}
            </p>
          </div>
          <div>
            <label className="text-xs text-gray-500 uppercase">Mode</label>
            <p className="text-gray-200 text-sm">{data.mode as string}</p>
          </div>
        </div>
        <div>
          <label className="text-xs text-gray-500 uppercase mb-1 block">
            Context Used ({((data.contextUtilization as number) * 100).toFixed(1)}%)
          </label>
          <ProgressBar value={data.contextUtilization as number} color="#60a5fa" />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-gray-500 uppercase">Papers</label>
            <p className="text-gray-200 text-lg font-semibold">
              {data.paperCount as number}
            </p>
          </div>
          <div>
            <label className="text-xs text-gray-500 uppercase">Summaries</label>
            <p className="text-gray-200 text-lg font-semibold">
              {data.summaryCount as number}
            </p>
          </div>
        </div>
      </div>
    );
  };

  const renderPaperDetails = () => {
    const data = node.data;
    const authors = data.authors as Array<{ name?: string }>;
    return (
      <div className="space-y-3">
        <div>
          <label className="text-xs text-gray-500 uppercase">Title</label>
          <p className="text-gray-200 text-sm">{data.title as string}</p>
        </div>
        {authors && authors.length > 0 && (
          <div>
            <label className="text-xs text-gray-500 uppercase">Authors</label>
            <p className="text-gray-300 text-sm">
              {authors
                .slice(0, 3)
                .map((a) => a.name)
                .filter(Boolean)
                .join(", ")}
              {authors.length > 3 && ` +${authors.length - 3} more`}
            </p>
          </div>
        )}
        <div className="grid grid-cols-2 gap-3">
          {(data.year as number | undefined) && (
            <div>
              <label className="text-xs text-gray-500 uppercase">Year</label>
              <p className="text-gray-200 text-sm">{data.year as number}</p>
            </div>
          )}
          {(data.citationCount as number | undefined) !== undefined && (
            <div>
              <label className="text-xs text-gray-500 uppercase">Citations</label>
              <p className="text-gray-200 text-sm">{data.citationCount as number}</p>
            </div>
          )}
        </div>
        <div>
          <label className="text-xs text-gray-500 uppercase mb-1 block">
            Groundedness ({((data.groundedness as number) * 100).toFixed(0)}%)
          </label>
          <ProgressBar value={data.groundedness as number} color={node.color} />
        </div>
        {(data.paperId as string | undefined) && (
          <a
            href={`https://www.semanticscholar.org/paper/${data.paperId}`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-block text-sm text-blue-400 hover:text-blue-300"
          >
            View on Semantic Scholar &rarr;
          </a>
        )}
      </div>
    );
  };

  const renderHypothesisDetails = () => {
    const data = node.data;
    const supportingPapers = data.supportingPaperIds as string[];
    return (
      <div className="space-y-3">
        <div>
          <label className="text-xs text-gray-500 uppercase">Hypothesis</label>
          <p className="text-gray-200 text-sm">{data.text as string}</p>
        </div>
        <div>
          <label className="text-xs text-gray-500 uppercase mb-1 block">
            Confidence ({((data.confidence as number) * 100).toFixed(0)}%)
          </label>
          <ProgressBar value={data.confidence as number} color={node.color} />
        </div>
        <div>
          <label className="text-xs text-gray-500 uppercase">Supporting Papers</label>
          <p className="text-gray-200 text-lg font-semibold">
            {supportingPapers?.length ?? 0}
          </p>
        </div>
      </div>
    );
  };

  const typeLabels: Record<string, string> = {
    branch: "Branch",
    paper: "Paper",
    hypothesis: "Hypothesis",
  };

  return (
    <div className="flex-1 p-4 border-b border-gray-700 overflow-y-auto">
      <div className="flex items-center gap-2 mb-4">
        <div
          className="w-3 h-3 rounded-full"
          style={{ backgroundColor: node.color }}
        />
        <h3 className="text-lg font-semibold text-white">
          {typeLabels[node.type]}
        </h3>
      </div>
      {node.type === "branch" && renderBranchDetails()}
      {node.type === "paper" && renderPaperDetails()}
      {node.type === "hypothesis" && renderHypothesisDetails()}
    </div>
  );
}
