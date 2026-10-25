import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Calendar, Layers, Video, Share2, AlertCircle, CheckCircle2,
  Clock, ArrowUpRight, Plus, RefreshCw, BarChart2, ShieldAlert
} from 'lucide-react';
import { api } from '../../services/api';
import { Campaign, ScheduledPostItem, ConnectedAccount } from '../../types';
import { PlatformBadge } from '../../components/PlatformBadge';
import { FormatBadge } from '../../components/FormatBadge';
import { StatusBadge } from '../../components/StatusBadge';

export const DashboardPage: React.FC = () => {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [queue, setQueue] = useState<ScheduledPostItem[]>([]);
  const [accounts, setAccounts] = useState<ConnectedAccount[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  const loadData = async () => {
    setLoading(true);
    try {
      const [cRes, qRes, aRes] = await Promise.all([
        api.listCampaigns(),
        api.getPublishingQueue(),
        api.listConnectedAccounts(),
      ]);
      setCampaigns(cRes);
      setQueue(qRes);
      setAccounts(aRes);
    } catch (err) {
      console.error('Failed to load dashboard:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const totalAssets = queue.length;
  const publishedCount = queue.filter((p) => p.status === 'published').length;
  const scheduledCount = queue.filter((p) => p.status === 'scheduled').length;
  const failedCount = queue.filter((p) => p.status === 'failed').length;
  const connectedPlatforms = accounts.filter((a) => a.status === 'connected').length;

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Top Banner / CTA */}
      <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 rounded-3xl p-8 text-white shadow-xl relative overflow-hidden border border-indigo-900/40">
        <div className="relative z-10 max-w-2xl">
          <div className="inline-flex items-center space-x-2 bg-indigo-500/20 text-indigo-300 text-xs px-3 py-1 rounded-full border border-indigo-500/30 mb-4 font-mono font-medium">
            <span>IncuBrix Growth Engine v1.0</span>
          </div>
          <h2 className="text-3xl font-black tracking-tight text-white mb-2">
            Turn 1 input into 30 days of multi-platform social assets.
          </h2>
          <p className="text-slate-300 text-sm leading-relaxed mb-6">
            Autonomous multi-stage AI pipeline converts blogs, podcasts, webinars, and demo recordings into verified text, graphics, 5-slide carousels, and 9:16 short videos with zero hallucination.
          </p>
          <div className="flex items-center space-x-4">
            <Link
              to="/create"
              className="inline-flex items-center space-x-2 bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-sm px-5 py-2.5 rounded-xl shadow-lg shadow-indigo-600/30 transition-all"
            >
              <Plus className="w-4 h-4" />
              <span>Create 30-Day Campaign</span>
            </Link>
            <Link
              to="/calendar"
              className="inline-flex items-center space-x-2 bg-slate-800/80 hover:bg-slate-800 text-slate-200 text-sm font-medium px-4 py-2.5 rounded-xl border border-slate-700 transition-all"
            >
              <Calendar className="w-4 h-4" />
              <span>View Content Calendar</span>
            </Link>
          </div>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <div className="bg-white rounded-2xl p-6 border border-slate-200/80 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Scheduled Assets</span>
            <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center">
              <Calendar className="w-4 h-4" />
            </div>
          </div>
          <div className="text-3xl font-extrabold text-slate-900">{scheduledCount}</div>
          <div className="text-xs text-slate-500 mt-1 flex items-center space-x-1">
            <Clock className="w-3 h-3 text-slate-400" />
            <span>Active in persistent publishing queue</span>
          </div>
        </div>

        <div className="bg-white rounded-2xl p-6 border border-slate-200/80 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Published Posts</span>
            <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
              <CheckCircle2 className="w-4 h-4" />
            </div>
          </div>
          <div className="text-3xl font-extrabold text-slate-900">{publishedCount}</div>
          <div className="text-xs text-emerald-600 mt-1 font-medium">Live on social platforms</div>
        </div>

        <div className="bg-white rounded-2xl p-6 border border-slate-200/80 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Failed / Blocked</span>
            <div className="w-8 h-8 rounded-lg bg-red-50 text-red-600 flex items-center justify-center">
              <AlertCircle className="w-4 h-4" />
            </div>
          </div>
          <div className="text-3xl font-extrabold text-slate-900">{failedCount}</div>
          <div className="text-xs text-slate-500 mt-1">Retryable or missing credentials</div>
        </div>

        <div className="bg-white rounded-2xl p-6 border border-slate-200/80 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Connected Accounts</span>
            <div className="w-8 h-8 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center">
              <Share2 className="w-4 h-4" />
            </div>
          </div>
          <div className="text-3xl font-extrabold text-slate-900">{connectedPlatforms} / 3</div>
          <div className="text-xs text-slate-500 mt-1">YouTube, Facebook, Instagram</div>
        </div>
      </div>

      {/* Two Column Section: Upcoming Slots & Active Campaigns */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column: Upcoming Publishing Queue (2 cols) */}
        <div className="lg:col-span-2 bg-white rounded-3xl p-6 border border-slate-200/80 shadow-sm">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h3 className="text-base font-bold text-slate-900">Upcoming Publishing Slots</h3>
              <p className="text-xs text-slate-500 mt-0.5">Automated queue managed by persistent worker</p>
            </div>
            <Link
              to="/publishing"
              className="text-xs font-semibold text-indigo-600 hover:text-indigo-700 flex items-center space-x-1"
            >
              <span>View All Queue</span>
              <ArrowUpRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          {queue.length === 0 ? (
            <div className="text-center py-12 border-2 border-dashed border-slate-200 rounded-2xl">
              <Clock className="w-8 h-8 text-slate-400 mx-auto mb-3" />
              <div className="text-sm font-semibold text-slate-700">No scheduled posts yet</div>
              <p className="text-xs text-slate-400 max-w-sm mx-auto mt-1 mb-4">
                Upload a source content file and generate your 30-day multi-platform campaign.
              </p>
              <Link
                to="/create"
                className="inline-flex items-center space-x-1.5 bg-indigo-600 text-white text-xs px-4 py-2 rounded-xl font-medium"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Create Campaign</span>
              </Link>
            </div>
          ) : (
            <div className="space-y-3">
              {queue.slice(0, 6).map((post) => (
                <div
                  key={post.scheduled_post_id}
                  className="flex items-center justify-between p-4 rounded-2xl border border-slate-100 hover:border-slate-200 bg-slate-50/50 hover:bg-slate-50 transition-all"
                >
                  <div className="flex items-center space-x-3.5 flex-1 min-w-0 pr-4">
                    <PlatformBadge platform={post.platform} />
                    <FormatBadge format={post.format} />
                    <div className="truncate flex-1">
                      <div className="text-xs font-semibold text-slate-900 truncate">{post.hook || post.caption}</div>
                      <div className="text-[11px] text-slate-500 flex items-center space-x-2 mt-0.5">
                        <span>Day {post.day_number}</span>
                        <span>•</span>
                        <span>{new Date(post.scheduled_utc).toLocaleDateString()} {new Date(post.scheduled_utc).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center space-x-3">
                    <StatusBadge status={post.status} />
                    <Link
                      to={`/assets?id=${post.content_asset_id}`}
                      className="text-xs font-semibold text-slate-600 hover:text-indigo-600 px-2.5 py-1 rounded-lg border border-slate-200 bg-white"
                    >
                      Inspect
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right Column: Connected Accounts & Active Campaigns (1 col) */}
        <div className="space-y-6">
          {/* Connected Accounts Card */}
          <div className="bg-white rounded-3xl p-6 border border-slate-200/80 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-bold text-slate-900">Platform Connections</h3>
              <span className="text-[11px] text-emerald-600 font-semibold bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                Auto-Synced (.env)
              </span>
            </div>
            <div className="space-y-2.5">
              {(['youtube', 'facebook', 'instagram'] as const).map((plat) => {
                const acc = accounts.find((a) => a.platform === plat);
                const isConn = Boolean(acc && acc.status === 'connected');
                return (
                  <div key={plat} className="flex items-center justify-between p-3 rounded-xl border border-slate-100 bg-slate-50">
                    <div className="flex items-center space-x-2">
                      <PlatformBadge platform={plat} size="sm" />
                      <span className="text-xs text-slate-700 font-medium truncate max-w-[120px]">
                        {acc?.account_name || 'Not linked'}
                      </span>
                    </div>
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                      isConn ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-200 text-slate-600'
                    }`}>
                      {isConn ? 'ACTIVE' : 'DISCONNECTED'}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Active Campaigns Card */}
          <div className="bg-white rounded-3xl p-6 border border-slate-200/80 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-bold text-slate-900">Active Campaigns</h3>
              <Link to="/create" className="text-xs text-indigo-600 font-semibold hover:underline">
                + New
              </Link>
            </div>
            {campaigns.length === 0 ? (
              <p className="text-xs text-slate-400">No campaigns created yet.</p>
            ) : (
              <div className="space-y-3">
                {campaigns.slice(0, 4).map((c) => (
                  <div key={c.id} className="p-3 rounded-xl border border-slate-100 bg-slate-50">
                    <div className="flex items-center justify-between">
                      <div className="text-xs font-bold text-slate-900 truncate">{c.name}</div>
                      <StatusBadge status={c.status} />
                    </div>
                    <div className="text-[11px] text-slate-500 mt-1 flex items-center justify-between">
                      <span>{c.duration_days} Days</span>
                      <span>{c.platforms.join(', ')}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
