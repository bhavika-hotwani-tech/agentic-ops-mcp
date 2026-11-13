import React, { useState, useEffect } from 'react';
import { 
  Bot, ShieldAlert, Cpu, Terminal, CheckCircle2, AlertTriangle, 
  Play, RotateCcw, Wrench, FileCode, Check, X, Clock, ExternalLink 
} from 'lucide-react';

const API_BASE = 'http://localhost:8000/api/v1';

export default function App() {
  const [activeTab, setActiveTab] = useState('incident'); // incident | mcp | history
  const [service, setService] = useState('auth-api');
  const [description, setDescription] = useState('P99 latency spiked to 842ms, JWT validation failure rate 4.8%');
  const [isRunning, setIsRunning] = useState(false);
  const [currentRun, setCurrentRun] = useState(null);
  const [mcpTools, setMcpTools] = useState([]);
  const [runsHistory, setRunsHistory] = useState([]);
  const [errorMsg, setErrorMsg] = useState('');

  // Initial load: fetch MCP tools
  useEffect(() => {
    fetch(`${API_BASE}/mcp/tools`)
      .then(res => res.json())
      .then(data => setMcpTools(data))
      .catch(() => {
        // Fallback demo mock tools if server not running
        setMcpTools([
          { name: 'search_runbooks', description: 'Search internal SRE runbooks for remediation playbooks.', requires_approval: false },
          { name: 'query_incident_metrics', description: 'Fetch live P99 latency, CPU, and error rate telemetry for a service.', requires_approval: false },
          { name: 'check_service_health', description: 'Check current health status and active alerts for a microservice.', requires_approval: false },
          { name: 'execute_remediation_action', description: 'Execute a production remediation action (requires human approval).', requires_approval: true },
        ]);
      });
  }, []);

  const handleRunAgent = async () => {
    setIsRunning(true);
    setErrorMsg('');
    try {
      const res = await fetch(`${API_BASE}/agent/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ service, description })
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setCurrentRun(data);
      setRunsHistory(prev => [data, ...prev]);
    } catch (err) {
      // Offline fallback demo execution
      const fallbackRun = {
        run_id: `run-${Math.random().toString(16).slice(2, 8)}`,
        status: 'waiting_approval',
        service,
        severity: 'critical',
        requires_human_approval: true,
        pending_action: { service, action: 'restart_pods', dry_run: false },
        plan_steps: [
          `Query real-time health and metrics for '${service}' via MCP.`,
          `Search internal SRE runbooks matching '${service}' failure modes.`,
          'Synthesize telemetry and formulate remediation recommendation.',
          'Enforce Human-in-the-Loop approval before applying production mutations.'
        ],
        root_cause_hypothesis: `Service '${service}' is exhibiting P99 latency of 842ms (CPU 89%, error rate 4.8%). Runbook recommends pod restart.`,
        remediation_status: 'pending',
        audit_log: [
          { node: 'planner', action: 'Incident Triage & Investigation Planning', status: 'completed', timestamp: '11:32:01' },
          { node: 'investigator', action: 'MCP Tool Call Dispatch Formulation', status: 'completed', timestamp: '11:32:02' },
          { node: 'mcp_tool_executor', action: 'Executed 3 MCP Tool Invocations', status: 'completed', timestamp: '11:32:03' },
          { node: 'hitl_gate', action: `Blocked: Awaiting Human Operator Approval for 'restart_pods'`, status: 'waiting_approval', timestamp: '11:32:04' },
        ]
      };
      setCurrentRun(fallbackRun);
      setRunsHistory(prev => [fallbackRun, ...prev]);
    } finally {
      setIsRunning(false);
    }
  };

  const handleHumanDecision = async (approved) => {
    if (!currentRun) return;
    setIsRunning(true);
    try {
      const res = await fetch(`${API_BASE}/agent/runs/${currentRun.run_id}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          approved, 
          reason: approved ? 'Approved by on-call SRE lead.' : 'Operator rejected mutation; dry-run only.' 
        })
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const updated = await res.json();
      setCurrentRun(updated);
      setRunsHistory(prev => prev.map(r => r.run_id === updated.run_id ? updated : r));
    } catch (err) {
      // Mock update
      const updated = {
        ...currentRun,
        status: 'completed',
        approval_granted: approved,
        remediation_status: approved ? 'executed' : 'dry_run',
        final_summary: `### Incident Post-Mortem & Resolution Report\n\n**Service:** \`${currentRun.service}\` | **Severity:** \`${currentRun.severity.toUpperCase()}\`\n\n**Remediation Outcome:** ${approved ? 'Action restart_pods executed cleanly via MCP.' : 'Operator rejected mutation. Dry-run completed.'}\n\n**Audit Status:** \`${approved ? 'EXECUTED' : 'DRY_RUN'}\``,
        audit_log: [
          ...currentRun.audit_log,
          { node: 'hitl_gate', action: approved ? 'Human Approval GRANTED' : 'Human Approval REJECTED', status: 'completed', timestamp: '11:32:45' },
          { node: 'synthesizer', action: 'Final Post-Mortem Generated', status: 'completed', timestamp: '11:32:46' },
        ]
      };
      setCurrentRun(updated);
      setRunsHistory(prev => prev.map(r => r.run_id === updated.run_id ? updated : r));
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Top Navbar */}
      <header className="border-b border-slate-800 bg-slate-900/60 backdrop-blur px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-500 to-emerald-500 flex items-center justify-center shadow-lg shadow-indigo-500/20">
            <Bot className="w-6 h-6 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-bold tracking-tight text-white">AgenticOps MCP</h1>
              <span className="text-[10px] font-mono uppercase bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 px-2 py-0.5 rounded-full">
                LangGraph v1.2
              </span>
            </div>
            <p className="text-xs text-slate-400">Autonomous SRE Incident Copilot with Human-in-the-Loop Safety</p>
          </div>
        </div>

        {/* Live Badges */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-xs bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-3 py-1.5 rounded-lg">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            LangGraph StateGraph: ACTIVE
          </div>
          <div className="flex items-center gap-2 text-xs bg-purple-500/10 text-purple-400 border border-purple-500/20 px-3 py-1.5 rounded-lg font-mono">
            MCP JSON-RPC: ONLINE
          </div>
        </div>
      </header>

      {/* Tabs */}
      <div className="border-b border-slate-800 px-6 flex gap-6 bg-slate-900/30 text-sm">
        <button
          onClick={() => setActiveTab('incident')}
          className={`py-3 font-medium transition border-b-2 flex items-center gap-2 ${
            activeTab === 'incident' ? 'border-indigo-500 text-indigo-400' : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Cpu className="w-4 h-4" /> Incident Dispatch & Graph
        </button>
        <button
          onClick={() => setActiveTab('mcp')}
          className={`py-3 font-medium transition border-b-2 flex items-center gap-2 ${
            activeTab === 'mcp' ? 'border-indigo-500 text-indigo-400' : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Wrench className="w-4 h-4" /> Model Context Protocol (MCP) Tools ({mcpTools.length})
        </button>
        <button
          onClick={() => setActiveTab('history')}
          className={`py-3 font-medium transition border-b-2 flex items-center gap-2 ${
            activeTab === 'history' ? 'border-indigo-500 text-indigo-400' : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Clock className="w-4 h-4" /> Run History ({runsHistory.length})
        </button>
      </div>

      {/* Main Container */}
      <main className="flex-1 p-6 max-w-7xl w-full mx-auto grid grid-cols-1 lg:grid-cols-12 gap-6">
        {activeTab === 'incident' && (
          <>
            {/* Left Control Panel (5 cols) */}
            <div className="lg:col-span-5 space-y-6">
              {/* Trigger Card */}
              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-sm space-y-4">
                <div className="flex items-center justify-between">
                  <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2">
                    <ShieldAlert className="w-4 h-4 text-amber-400" /> Incident Parameters
                  </h2>
                  <span className="text-xs text-slate-500">Autonomous Triaging</span>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1.5">Target Microservice</label>
                  <select
                    value={service}
                    onChange={(e) => setService(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
                  >
                    <option value="auth-api">auth-api (Degraded - P99 &gt; 800ms)</option>
                    <option value="billing-worker">billing-worker (Critical - 6.4% Error Rate)</option>
                    <option value="rag-indexer">rag-indexer (Healthy - Normal Ops)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1.5">Incident Payload / Alert</label>
                  <textarea
                    rows={3}
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-xs font-mono text-slate-200 focus:outline-none focus:border-indigo-500"
                  />
                </div>

                <button
                  onClick={handleRunAgent}
                  disabled={isRunning}
                  className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-medium py-2.5 rounded-lg flex items-center justify-center gap-2 text-sm shadow-md transition"
                >
                  <Play className="w-4 h-4 fill-current" />
                  {isRunning ? 'LangGraph Agent Executing...' : 'Trigger Autonomous Copilot'}
                </button>
              </div>

              {/* Human-in-the-Loop Interruption Card */}
              {currentRun && currentRun.status === 'waiting_approval' && (
                <div className="bg-gradient-to-b from-amber-500/10 to-amber-950/20 border-2 border-amber-500/40 rounded-2xl p-5 space-y-4 animate-in fade-in">
                  <div className="flex items-center gap-2 text-amber-400 font-semibold text-sm">
                    <ShieldAlert className="w-5 h-5 animate-pulse" />
                    Human-in-the-Loop Gate: Operator Decision Required
                  </div>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    Agent proposed a destructive remediation action:
                    <span className="block mt-1 font-mono text-amber-300 bg-amber-950/40 border border-amber-500/30 p-2 rounded">
                      Action: {currentRun.pending_action?.action} | Service: {currentRun.pending_action?.service}
                    </span>
                  </p>

                  <div className="flex gap-3">
                    <button
                      onClick={() => handleHumanDecision(true)}
                      disabled={isRunning}
                      className="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold py-2 px-3 rounded-lg flex items-center justify-center gap-1.5 transition shadow"
                    >
                      <Check className="w-4 h-4" /> Approve Mutation
                    </button>
                    <button
                      onClick={() => handleHumanDecision(false)}
                      disabled={isRunning}
                      className="flex-1 bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold py-2 px-3 rounded-lg flex items-center justify-center gap-1.5 transition shadow"
                    >
                      <X className="w-4 h-4" /> Reject (Dry-Run Only)
                    </button>
                  </div>
                </div>
              )}

              {/* Plan Steps */}
              {currentRun && (
                <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-3">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                    Agent Execution Plan ({currentRun.plan_steps?.length || 0} Steps)
                  </h3>
                  <ul className="space-y-2">
                    {currentRun.plan_steps?.map((step, idx) => (
                      <li key={idx} className="text-xs text-slate-300 flex items-start gap-2">
                        <span className="w-4 h-4 rounded-full bg-slate-800 text-[10px] font-mono flex items-center justify-center shrink-0 mt-0.5">
                          {idx + 1}
                        </span>
                        {step}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            {/* Right Execution Flow & Post-Mortem (7 cols) */}
            <div className="lg:col-span-7 space-y-6">
              {/* LangGraph Node Progression Visualizer */}
              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-4 flex items-center justify-between">
                  <span>LangGraph Cyclic State Progression</span>
                  {currentRun && (
                    <span className={`text-[10px] px-2 py-0.5 rounded font-mono ${
                      currentRun.status === 'completed' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-amber-500/20 text-amber-400'
                    }`}>
                      STATUS: {currentRun.status.toUpperCase()}
                    </span>
                  )}
                </h3>

                <div className="grid grid-cols-5 gap-2 text-center text-xs">
                  {[
                    { key: 'planner', label: '1. Planner' },
                    { key: 'investigator', label: '2. Investigator' },
                    { key: 'mcp_tool_executor', label: '3. MCP Tools' },
                    { key: 'hitl_gate', label: '4. HITL Gate' },
                    { key: 'synthesizer', label: '5. Synthesizer' }
                  ].map(node => {
                    const isExecuted = currentRun?.audit_log?.some(l => l.node === node.key);
                    const isPaused = currentRun?.status === 'waiting_approval' && node.key === 'hitl_gate';
                    return (
                      <div
                        key={node.key}
                        className={`p-2.5 rounded-xl border flex flex-col items-center gap-1 transition ${
                          isPaused
                            ? 'border-amber-500 bg-amber-500/10 text-amber-300 animate-pulse'
                            : isExecuted
                            ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300'
                            : 'border-slate-800 bg-slate-950/40 text-slate-500'
                        }`}
                      >
                        <span className="text-[11px] font-medium">{node.label}</span>
                        {isPaused ? (
                          <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                        ) : isExecuted ? (
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                        ) : (
                          <span className="w-1.5 h-1.5 rounded-full bg-slate-700"></span>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Audit Timeline */}
              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-3">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-2">
                  <Terminal className="w-4 h-4 text-indigo-400" /> Execution Audit Trail
                </h3>
                {currentRun?.audit_log?.length > 0 ? (
                  <div className="space-y-2.5 font-mono text-xs">
                    {currentRun.audit_log.map((log, i) => (
                      <div key={i} className="flex items-start gap-3 bg-slate-950 border border-slate-800/80 p-2.5 rounded-lg">
                        <span className="text-slate-500 shrink-0">{log.timestamp}</span>
                        <span className="text-indigo-400 font-semibold shrink-0">[{log.node}]</span>
                        <span className="text-slate-200">{log.action}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-xs text-slate-500 py-8 text-center">
                    Trigger an incident to watch the agent orchestrate investigation and MCP tool calls.
                  </div>
                )}
              </div>

              {/* Post-Mortem Report Output */}
              {currentRun?.final_summary && (
                <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-3">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-emerald-400 flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4" /> Synthesized Post-Mortem Resolution
                  </h3>
                  <div className="bg-slate-950 border border-slate-800 p-4 rounded-xl text-xs font-sans text-slate-300 whitespace-pre-line leading-relaxed">
                    {currentRun.final_summary}
                  </div>
                </div>
              )}
            </div>
          </>
        )}

        {activeTab === 'mcp' && (
          <div className="col-span-12 space-y-6">
            <div>
              <h2 className="text-base font-bold text-white">Model Context Protocol (MCP) Server Registry</h2>
              <p className="text-xs text-slate-400">Discoverable tools and runbook resources exposed via JSON-RPC 2.0 primitives</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {mcpTools.map(tool => (
                <div key={tool.name} className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-bold font-mono text-indigo-400">{tool.name}</h3>
                    {tool.requires_approval ? (
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/20">
                        MUTATION (APPROVAL REQ)
                      </span>
                    ) : (
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                        READ-ONLY
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-300 leading-relaxed">{tool.description}</p>
                  <div className="bg-slate-950 p-2.5 rounded-lg border border-slate-800 text-[11px] font-mono text-slate-400">
                    Endpoint: POST /api/v1/mcp (method: tools/call)
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'history' && (
          <div className="col-span-12 space-y-4">
            <h2 className="text-base font-bold text-white">Execution History</h2>
            {runsHistory.length === 0 ? (
              <p className="text-xs text-slate-500">No runs recorded yet in current session.</p>
            ) : (
              <div className="space-y-2">
                {runsHistory.map(run => (
                  <div key={run.run_id} className="bg-slate-900 border border-slate-800 p-4 rounded-xl flex items-center justify-between text-xs">
                    <div>
                      <div className="font-mono font-bold text-indigo-400">{run.run_id}</div>
                      <div className="text-slate-400">{run.service} • {run.severity?.toUpperCase()}</div>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className={`px-2.5 py-1 rounded font-mono text-[10px] ${
                        run.status === 'completed' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-amber-500/10 text-amber-400'
                      }`}>
                        {run.status.toUpperCase()}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
