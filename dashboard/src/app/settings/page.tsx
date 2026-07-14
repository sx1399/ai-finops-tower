"use client";

import React, { useEffect, useState, useCallback } from "react";
import { Key, Plus, Trash2, Copy, Check, RefreshCw, ShieldCheck, AlertTriangle } from "lucide-react";
import { API_BASE } from "@/lib/api";

interface ApiKey {
  id: number;
  name: string;
  prefix: string;
  created_at: string;
  last_used_at: string | null;
  is_active: boolean;
}

interface NewKeyResult {
  key: string;
  prefix: string;
  name: string;
  created_at: string;
}

export default function SettingsPage() {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [newKeyName, setNewKeyName] = useState("");
  const [creating, setCreating] = useState(false);
  const [revokingId, setRevokingId] = useState<number | null>(null);
  const [newKeyResult, setNewKeyResult] = useState<NewKeyResult | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchKeys = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/keys`);
      if (res.ok) setKeys(await res.json());
    } catch {
      setError("Could not load API keys. Is the backend running?");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { 
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchKeys();
    const interval = setInterval(fetchKeys, 3000);
    return () => clearInterval(interval);
  }, [fetchKeys]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newKeyName.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/keys`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newKeyName.trim() }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data: NewKeyResult = await res.json();
      setNewKeyResult(data);
      setNewKeyName("");
      fetchKeys();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create key");
    } finally {
      setCreating(false);
    }
  };

  const handleRevoke = async (id: number) => {
    setRevokingId(id);
    try {
      await fetch(`${API_BASE}/api/keys/${id}`, { method: "DELETE" });
      fetchKeys();
    } finally {
      setRevokingId(null);
    }
  };

  const handleCopy = async (text: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 p-8 font-sans">
      <div className="max-w-3xl mx-auto space-y-8">

        {/* Header */}
        <header className="border-b border-gray-800 pb-6">
          <div className="flex items-center gap-3 mb-1">
            <ShieldCheck className="w-7 h-7 text-blue-500" />
            <h1 className="text-2xl font-bold text-white tracking-tight">API Keys</h1>
          </div>
          <p className="text-sm text-gray-400">
            Generate and manage Gateway API keys. Include a key as a{" "}
            <code className="bg-gray-800 px-1.5 py-0.5 rounded text-blue-300 text-xs">
              Bearer
            </code>{" "}
            token in the <code className="bg-gray-800 px-1.5 py-0.5 rounded text-blue-300 text-xs">Authorization</code> header
            of every request to the proxy.
          </p>
        </header>

        {/* Error banner */}
        {error && (
          <div className="flex items-center gap-2 bg-red-900/30 border border-red-700/50 text-red-300 rounded-xl px-4 py-3 text-sm">
            <AlertTriangle className="w-4 h-4 flex-shrink-0" />
            {error}
          </div>
        )}

        {/* Newly created key banner */}
        {newKeyResult && (
          <div className="bg-green-900/20 border border-green-700/40 rounded-2xl p-5 space-y-3">
            <p className="text-green-300 font-semibold text-sm flex items-center gap-2">
              <Check className="w-4 h-4" /> Key created — copy it now, it won&apos;t be shown again!
            </p>
            <div className="flex items-center gap-2">
              <code className="flex-1 bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-xs text-blue-300 font-mono break-all">
                {newKeyResult.key}
              </code>
              <button
                id="copy-new-key-btn"
                onClick={() => handleCopy(newKeyResult.key)}
                className="p-2 rounded-lg bg-gray-800 hover:bg-gray-700 border border-gray-700 transition-colors"
                title="Copy key"
              >
                {copied ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4 text-gray-300" />}
              </button>
            </div>
            <button
              onClick={() => setNewKeyResult(null)}
              className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Create new key */}
        <div className="bg-gray-900 rounded-2xl border border-gray-800 p-6 shadow-lg">
          <h2 className="text-base font-semibold text-white mb-4 flex items-center gap-2">
            <Plus className="w-4 h-4 text-blue-400" /> Generate New Key
          </h2>
          <form onSubmit={handleCreate} className="flex gap-3">
            <input
              id="key-name-input"
              type="text"
              value={newKeyName}
              onChange={(e) => setNewKeyName(e.target.value)}
              placeholder="Key name (e.g. production-app)"
              className="flex-1 bg-gray-800 border border-gray-700 rounded-xl px-4 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 transition-colors"
              required
            />
            <button
              id="generate-key-btn"
              type="submit"
              disabled={creating || !newKeyName.trim()}
              className="px-5 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:bg-blue-900 disabled:text-blue-600 text-white rounded-xl text-sm font-semibold transition-colors flex items-center gap-2"
            >
              {creating ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Key className="w-4 h-4" />}
              {creating ? "Generating…" : "Generate"}
            </button>
          </form>
        </div>

        {/* Key list */}
        <div className="bg-gray-900 rounded-2xl border border-gray-800 overflow-hidden shadow-lg">
          <div className="p-5 border-b border-gray-800 flex items-center justify-between">
            <h2 className="text-base font-semibold text-white">Active Keys</h2>
            <button
              id="refresh-keys-btn"
              onClick={fetchKeys}
              className="text-gray-400 hover:text-white transition-colors p-1"
              title="Refresh"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>

          {loading ? (
            <p className="text-gray-500 text-sm text-center py-10">Loading…</p>
          ) : keys.filter(k => k.is_active).length === 0 ? (
            <div className="text-center py-12 space-y-2">
              <Key className="w-8 h-8 text-gray-700 mx-auto" />
              <p className="text-gray-500 text-sm">No active keys yet. Generate one above.</p>
              <p className="text-gray-600 text-xs">While no keys exist, all proxy requests are allowed through.</p>
            </div>
          ) : (
            <table className="w-full text-left">
              <thead>
                <tr className="bg-gray-950/60 text-gray-400 text-xs uppercase tracking-wider">
                  <th className="px-5 py-3 font-semibold border-b border-gray-800">Name</th>
                  <th className="px-5 py-3 font-semibold border-b border-gray-800">Prefix</th>
                  <th className="px-5 py-3 font-semibold border-b border-gray-800">Created</th>
                  <th className="px-5 py-3 font-semibold border-b border-gray-800">Last Used</th>
                  <th className="px-5 py-3 font-semibold border-b border-gray-800 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800/50">
                {keys.filter(k => k.is_active).map((key) => (
                  <tr key={key.id} className="hover:bg-gray-800/40 transition-colors">
                    <td className="px-5 py-4 text-sm text-white font-medium">{key.name}</td>
                    <td className="px-5 py-4">
                      <code className="bg-gray-800 border border-gray-700 text-blue-300 text-xs px-2 py-1 rounded-md font-mono">
                        {key.prefix}…
                      </code>
                    </td>
                    <td className="px-5 py-4 text-sm text-gray-400">
                      {new Date(key.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-5 py-4 text-sm text-gray-400">
                      {key.last_used_at ? new Date(key.last_used_at).toLocaleString() : "Never"}
                    </td>
                    <td className="px-5 py-4 text-right">
                      <button
                        id={`revoke-key-${key.id}`}
                        onClick={() => handleRevoke(key.id)}
                        disabled={revokingId === key.id}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-red-900/20 border border-red-700/30 text-red-400 hover:bg-red-900/40 transition-colors disabled:opacity-50"
                      >
                        {revokingId === key.id ? (
                          <RefreshCw className="w-3 h-3 animate-spin" />
                        ) : (
                          <Trash2 className="w-3 h-3" />
                        )}
                        Revoke
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Usage example */}
        <div className="bg-gray-900 rounded-2xl border border-gray-800 p-6 shadow-lg space-y-3">
          <h2 className="text-base font-semibold text-white">Usage Example</h2>
          <p className="text-xs text-gray-400">Point your AI SDK at the gateway and pass your key:</p>
          <pre className="bg-gray-950 border border-gray-800 rounded-xl p-4 text-xs text-green-300 font-mono overflow-x-auto whitespace-pre-wrap">{`curl -X POST http://localhost:8000/openai/v1/chat/completions \\
  -H "Authorization: Bearer gw-<your-key>" \\
  -H "Content-Type: application/json" \\
  -d '{"model":"gpt-4o","messages":[{"role":"user","content":"Hello!"}]}'`}</pre>
        </div>

      </div>
    </div>
  );
}
