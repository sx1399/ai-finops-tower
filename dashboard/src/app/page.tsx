"use client";

import React, { useEffect, useState } from "react";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { Activity, DollarSign, Percent } from "lucide-react";
import { API_BASE } from "@/lib/api";

interface Metrics {
  total_spend: number;
  total_saved: number;
  active_reductions: number;
}

interface ChartData {
  date: string;
  spend: number;
  saved: number;
}

interface Query {
  id: number;
  timestamp: string;
  original_model: string;
  routed_model: string;
  cached: boolean;
  latency: number;
}



export default function Dashboard() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [chartData, setChartData] = useState<ChartData[]>([]);
  const [queries, setQueries] = useState<Query[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [metricsRes, chartRes, queriesRes] = await Promise.all([
          fetch(`${API_BASE}/api/metrics`),
          fetch(`${API_BASE}/api/chart-data`),
          fetch(`${API_BASE}/api/queries`),
        ]);
        
        if (metricsRes.ok) {
          const rawMetrics = await metricsRes.json();
          setMetrics({
            total_spend: parseFloat(rawMetrics.total_spend || 0),
            total_saved: parseFloat(rawMetrics.total_saved || 0),
            active_reductions: parseFloat(rawMetrics.active_reductions || 0)
          });
        }
        if (chartRes.ok) setChartData(await chartRes.json());
        if (queriesRes.ok) setQueries(await queriesRes.json());
      } catch (error) {
        console.error("Failed to fetch data:", error);
      } finally {
        setLoading(false);
      }
    };
    
    fetchData();
    const interval = setInterval(fetchData, 3000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return <div className="min-h-screen flex items-center justify-center bg-gray-950 text-white">Loading dashboard...</div>;
  }

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 p-8 font-sans">
      <div className="max-w-7xl mx-auto space-y-8">
        
        <header className="flex items-center justify-between border-b border-gray-800 pb-6 pt-2">
          <h1 className="text-2xl font-bold text-white tracking-tight">Overview</h1>
          <div className="text-sm text-gray-400 bg-gray-900 px-4 py-2 rounded-full border border-gray-800 shadow-sm">
            Live Telemetry
          </div>
        </header>

        {/* Metrics Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-gray-900 rounded-2xl p-6 border border-gray-800 shadow-lg relative overflow-hidden group">
            <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
              <DollarSign className="w-24 h-24 text-red-400" />
            </div>
            <div className="flex items-center space-x-3 text-gray-400 mb-4 relative z-10">
              <div className="p-2 bg-red-400/10 rounded-lg">
                <DollarSign className="w-5 h-5 text-red-400" />
              </div>
              <h2 className="text-sm font-semibold uppercase tracking-wider">Total AI Spend</h2>
            </div>
            <p className="text-4xl font-bold text-white relative z-10">${Number(metrics?.total_spend || 0).toFixed(2)}</p>
          </div>
          
          <div className="bg-gray-900 rounded-2xl p-6 border border-gray-800 shadow-lg relative overflow-hidden group">
            <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
              <DollarSign className="w-24 h-24 text-green-400" />
            </div>
            <div className="flex items-center space-x-3 text-gray-400 mb-4 relative z-10">
              <div className="p-2 bg-green-400/10 rounded-lg">
                <DollarSign className="w-5 h-5 text-green-400" />
              </div>
              <h2 className="text-sm font-semibold uppercase tracking-wider">Total Saved</h2>
            </div>
            <p className="text-4xl font-bold text-green-400 relative z-10">${Number(metrics?.total_saved || 0).toFixed(2)}</p>
          </div>

          <div className="bg-gray-900 rounded-2xl p-6 border border-gray-800 shadow-lg relative overflow-hidden group">
            <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
              <Percent className="w-24 h-24 text-blue-400" />
            </div>
            <div className="flex items-center space-x-3 text-gray-400 mb-4 relative z-10">
              <div className="p-2 bg-blue-400/10 rounded-lg">
                <Percent className="w-5 h-5 text-blue-400" />
              </div>
              <h2 className="text-sm font-semibold uppercase tracking-wider">Active Reductions</h2>
            </div>
            <p className="text-4xl font-bold text-blue-400 relative z-10">{Number(metrics?.active_reductions || 0).toFixed(1)}%</p>
          </div>
        </div>

        {/* Chart */}
        <div className="bg-gray-900 rounded-2xl p-6 border border-gray-800 shadow-lg">
          <h2 className="text-lg font-semibold text-white mb-6 flex items-center gap-2">
            <Activity className="w-5 h-5 text-gray-400" /> 
            Token Spending vs Savings (7 Days)
          </h2>
          <div className="h-80 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorSpend" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#f87171" stopOpacity={0.4}/>
                    <stop offset="95%" stopColor="#f87171" stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="colorSaved" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#4ade80" stopOpacity={0.4}/>
                    <stop offset="95%" stopColor="#4ade80" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" vertical={false} />
                <XAxis dataKey="date" stroke="#9ca3af" tick={{fill: '#9ca3af'}} tickLine={false} axisLine={false} dy={10} />
                <YAxis stroke="#9ca3af" tick={{fill: '#9ca3af'}} tickLine={false} axisLine={false} dx={-10} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#111827', borderColor: '#374151', color: '#fff', borderRadius: '0.5rem', boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.5)' }}
                  itemStyle={{ color: '#fff', fontWeight: 500 }}
                />
                <Area type="monotone" dataKey="spend" stroke="#f87171" strokeWidth={2} fillOpacity={1} fill="url(#colorSpend)" name="Spend ($)" />
                <Area type="monotone" dataKey="saved" stroke="#4ade80" strokeWidth={2} fillOpacity={1} fill="url(#colorSaved)" name="Saved ($)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Query List */}
        <div className="bg-gray-900 rounded-2xl border border-gray-800 shadow-lg overflow-hidden">
          <div className="p-6 border-b border-gray-800 flex justify-between items-center bg-gray-900/50">
            <h2 className="text-lg font-semibold text-white">Recent Intercepted Queries</h2>
            <span className="text-xs text-gray-400 bg-gray-800 px-2 py-1 rounded-md">Last 50 queries</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-gray-950/80 text-gray-400 text-xs uppercase tracking-wider">
                  <th className="px-6 py-4 font-semibold border-b border-gray-800">Timestamp</th>
                  <th className="px-6 py-4 font-semibold border-b border-gray-800">Original Model</th>
                  <th className="px-6 py-4 font-semibold border-b border-gray-800">Routed Model</th>
                  <th className="px-6 py-4 font-semibold border-b border-gray-800 text-center">Cached</th>
                  <th className="px-6 py-4 font-semibold border-b border-gray-800 text-right">Latency (ms)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800/50">
                {queries.slice(0, 10).map((query) => (
                  <tr key={query.id} className="hover:bg-gray-800/60 transition-colors">
                    <td className="px-6 py-4 text-sm text-gray-300">
                      {new Date(query.timestamp).toLocaleString()}
                    </td>
                    <td className="px-6 py-4 text-sm">
                      <span className="bg-gray-800 border border-gray-700 text-gray-300 px-2.5 py-1 rounded-md text-xs shadow-sm">{query.original_model}</span>
                    </td>
                    <td className="px-6 py-4 text-sm">
                      <span className={`px-2.5 py-1 rounded-md text-xs font-medium shadow-sm ${query.routed_model !== query.original_model ? 'bg-blue-500/10 text-blue-400 border border-blue-500/30' : 'bg-gray-800 border border-gray-700 text-gray-300'}`}>
                        {query.routed_model}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-center">
                      {query.cached ? (
                        <span className="inline-flex items-center justify-center bg-green-500/10 text-green-400 border border-green-500/30 px-2.5 py-1 rounded-md text-xs font-medium shadow-sm">
                          Yes
                        </span>
                      ) : (
                        <span className="inline-flex items-center justify-center bg-gray-800 border border-gray-700 text-gray-500 px-2.5 py-1 rounded-md text-xs shadow-sm">
                          No
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-sm text-right text-gray-300 font-mono">
                      {query.latency}ms
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

      </div>
    </div>
  );
}
