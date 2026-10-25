import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Search, Filter, Plus, Copy, Trash2, Edit3, Eye, Video,
  Layers, Image as ImageIcon, CheckCircle2, Clock,
  AlertCircle, ExternalLink, RefreshCw, Sparkles, Calendar,
  Share2, Check, ArrowRight
} from 'lucide-react';
import { YoutubeIcon, InstagramIcon, FacebookIcon } from '../../components/SocialIcons';
import { api } from '../../services/api';
import { ContentAsset } from '../../types';
import { PlatformBadge } from '../../components/PlatformBadge';
import { FormatBadge } from '../../components/FormatBadge';
import { StatusBadge } from '../../components/StatusBadge';

export const ContentAssetsPage: React.FC = () => {
  const navigate = useNavigate();
  const [assets, setAssets] = useState<ContentAsset[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [platformFilter, setPlatformFilter] = useState<string>('all');
  const [formatTab, setFormatTab] = useState<'all' | 'video' | 'carousel' | 'poster'>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [activeAsset, setActiveAsset] = useState<ContentAsset | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // Fast Publish & Schedule Modal States
  const [scheduleTarget, setScheduleTarget] = useState<ContentAsset | null>(null);
  const [scheduleDateTime, setScheduleDateTime] = useState<string>(() => {
    const d = new Date(Date.now() + 24 * 3600 * 1000);
    return d.toISOString().slice(0, 16);
  });
  const [isScheduling, setIsScheduling] = useState<boolean>(false);
  const [publishMessage, setPublishMessage] = useState<{ id: string; text: string; type: 'success' | 'error' } | null>(null);

  const fetchAssets = async () => {
    setLoading(true);
    try {
      const data = await api.listAssets();
      setAssets(data);
    } catch (err) {
      console.error('Failed to fetch assets:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAssets();
  }, []);

  const handleDuplicate = async (id: string) => {
    setActionLoading(id);
    try {
      await api.duplicateAsset(id);
      await fetchAssets();
    } catch (err) {
      console.error('Failed to clone asset:', err);
    } finally {
      setActionLoading(null);
    }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm('Are you sure you want to delete this asset?')) return;
    setActionLoading(id);
    try {
      await api.deleteAsset(id);
      await fetchAssets();
      if (activeAsset?.id === id) setActiveAsset(null);
    } catch (err) {
      console.error('Failed to delete asset:', err);
    } finally {
      setActionLoading(null);
    }
  };

  const handleQuickPublish = async (asset: ContentAsset, platform?: string) => {
    setActionLoading(asset.id);
    setPublishMessage(null);
    try {
      const res = await api.publishAssetDirectly(asset.id, platform || asset.platform);
      setPublishMessage({
        id: asset.id,
        type: 'success',
        text: `Successfully published to ${res.target_platform || platform || asset.platform}!`,
      });
      await fetchAssets();
    } catch (err: any) {
      setPublishMessage({
        id: asset.id,
        type: 'error',
        text: err.response?.data?.detail || err.message || 'Publishing failed.',
      });
    } finally {
      setActionLoading(null);
    }
  };

  const handleScheduleSubmit = async () => {
    if (!scheduleTarget) return;
    setIsScheduling(true);
    try {
      await api.scheduleAssetDirectly(scheduleTarget.id, scheduleDateTime, scheduleTarget.platform);
      setPublishMessage({
        id: scheduleTarget.id,
        type: 'success',
        text: `Scheduled for ${new Date(scheduleDateTime).toLocaleString()}`,
      });
      setScheduleTarget(null);
      await fetchAssets();
    } catch (err: any) {
      alert('Scheduling failed: ' + (err.response?.data?.detail || err.message));
    } finally {
      setIsScheduling(false);
    }
  };

  // Helper to get destination studio
  const getStudioRoute = (asset: ContentAsset) => {
    const fmt = (asset.format || '').toLowerCase();
    if (fmt.includes('video') || fmt.includes('reel') || fmt.includes('short')) {
      return `/video-gen?id=${asset.id}`;
    }
    if (fmt.includes('carousel')) {
      return `/carousel-gen?id=${asset.id}`;
    }
    return `/poster-gen?id=${asset.id}`;
  };

  const getStudioName = (asset: ContentAsset) => {
    const fmt = (asset.format || '').toLowerCase();
    if (fmt.includes('video') || fmt.includes('reel') || fmt.includes('short')) {
      return 'Video Studio';
    }
    if (fmt.includes('carousel')) {
      return 'Carousel Studio';
    }
    return 'Poster Studio';
  };

  // Filter calculations
  const videoAssets = assets.filter(a => {
    const f = (a.format || '').toLowerCase();
    return f.includes('video') || f.includes('reel') || f.includes('short');
  });

  const carouselAssets = assets.filter(a => {
    const f = (a.format || '').toLowerCase();
    return f.includes('carousel');
  });

  const posterAssets = assets.filter(a => {
    const f = (a.format || '').toLowerCase();
    return !f.includes('video') && !f.includes('reel') && !f.includes('short') && !f.includes('carousel');
  });

  const filteredAssets = assets.filter((asset) => {
    const matchesSearch =
      !searchQuery ||
      (asset.hook || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
      (asset.caption || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
      (asset.platform || '').toLowerCase().includes(searchQuery.toLowerCase());

    const matchesPlatform = platformFilter === 'all' || asset.platform.toLowerCase() === platformFilter.toLowerCase();
    const matchesStatus = statusFilter === 'all' || (asset.approval_status || '').toLowerCase() === statusFilter.toLowerCase();

    let matchesTab = true;
    const fmt = (asset.format || '').toLowerCase();
    if (formatTab === 'video') {
      matchesTab = fmt.includes('video') || fmt.includes('reel') || fmt.includes('short');
    } else if (formatTab === 'carousel') {
      matchesTab = fmt.includes('carousel');
    } else if (formatTab === 'poster') {
      matchesTab = !fmt.includes('video') && !fmt.includes('reel') && !fmt.includes('short') && !fmt.includes('carousel');
    }

    return matchesSearch && matchesPlatform && matchesStatus && matchesTab;
  });

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-slate-200">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Content Assets</h1>
          <p className="text-xs text-slate-500 mt-1">
            Central catalog for all generated video shorts, animated SVG carousels, and vector poster creatives.
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={() => navigate('/create')}
            className="inline-flex items-center space-x-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-xl text-xs font-semibold shadow-sm transition"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Generate 30-Day Campaign</span>
          </button>
        </div>
      </div>

      {/* Format Category Tabs */}
      <div className="flex items-center space-x-2 border-b border-slate-200 pb-3">
        <button
          onClick={() => setFormatTab('all')}
          className={`px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
            formatTab === 'all'
              ? 'bg-indigo-600 text-white shadow-sm'
              : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200'
          }`}
        >
          All Assets ({assets.length})
        </button>
        <button
          onClick={() => setFormatTab('video')}
          className={`inline-flex items-center space-x-1.5 px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
            formatTab === 'video'
              ? 'bg-indigo-600 text-white shadow-sm'
              : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200'
          }`}
        >
          <Video className="w-3.5 h-3.5" />
          <span>Videos & Shorts ({videoAssets.length})</span>
        </button>
        <button
          onClick={() => setFormatTab('carousel')}
          className={`inline-flex items-center space-x-1.5 px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
            formatTab === 'carousel'
              ? 'bg-indigo-600 text-white shadow-sm'
              : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200'
          }`}
        >
          <Layers className="w-3.5 h-3.5" />
          <span>Carousels ({carouselAssets.length})</span>
        </button>
        <button
          onClick={() => setFormatTab('poster')}
          className={`inline-flex items-center space-x-1.5 px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
            formatTab === 'poster'
              ? 'bg-indigo-600 text-white shadow-sm'
              : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200'
          }`}
        >
          <ImageIcon className="w-3.5 h-3.5" />
          <span>Posters & Graphics ({posterAssets.length})</span>
        </button>
      </div>

      {/* Control Bar: Search & Filters */}
      <div className="bg-white p-3.5 rounded-2xl border border-slate-200 shadow-xs flex flex-col md:flex-row gap-3 items-center justify-between">
        <div className="relative flex-1 w-full md:w-auto">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search by hook headline, caption, or platform..."
            className="w-full pl-9 pr-4 py-1.5 border border-slate-200 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2.5 w-full md:w-auto">
          {/* Platform Filter */}
          <select
            value={platformFilter}
            onChange={(e) => setPlatformFilter(e.target.value)}
            className="px-3 py-1.5 border border-slate-200 rounded-lg text-xs bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="all">All Platforms</option>
            <option value="youtube">YouTube</option>
            <option value="facebook">Facebook</option>
            <option value="instagram">Instagram</option>
          </select>

          {/* Status Filter */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-1.5 border border-slate-200 rounded-lg text-xs bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="all">All Statuses</option>
            <option value="approved">Approved</option>
            <option value="draft">Draft</option>
            <option value="rejected">Rejected</option>
          </select>

          <button
            onClick={fetchAssets}
            className="p-1.5 border border-slate-200 text-slate-600 hover:text-slate-900 hover:bg-slate-50 rounded-lg transition"
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Assets Grid */}
      {loading ? (
        <div className="h-64 flex items-center justify-center bg-white rounded-2xl border border-slate-200">
          <div className="flex flex-col items-center space-y-3">
            <RefreshCw className="w-6 h-6 text-indigo-600 animate-spin" />
            <span className="text-xs text-slate-500">Loading content assets...</span>
          </div>
        </div>
      ) : filteredAssets.length === 0 ? (
        <div className="py-16 text-center bg-white rounded-2xl border border-slate-200">
          <Layers className="w-10 h-10 text-slate-300 mx-auto mb-3" />
          <h3 className="text-sm font-semibold text-slate-800">No content assets found</h3>
          <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
            {searchQuery || platformFilter !== 'all' || formatTab !== 'all'
              ? 'Try adjusting your search criteria or category filter.'
              : 'Generate custom videos, carousels, or posters in the Creative Studios to populate your library.'}
          </p>
          <div className="mt-4 flex items-center justify-center space-x-3">
            <button
              onClick={() => navigate('/video-gen')}
              className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-xs font-medium hover:bg-indigo-700"
            >
              <Video className="w-3.5 h-3.5" />
              <span>Create Video</span>
            </button>
            <button
              onClick={() => navigate('/carousel-gen')}
              className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-slate-100 text-slate-700 text-xs font-medium hover:bg-slate-200 border border-slate-200"
            >
              <Layers className="w-3.5 h-3.5" />
              <span>Create Carousel</span>
            </button>
            <button
              onClick={() => navigate('/poster-gen')}
              className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-slate-100 text-slate-700 text-xs font-medium hover:bg-slate-200 border border-slate-200"
            >
              <ImageIcon className="w-3.5 h-3.5" />
              <span>Create Poster</span>
            </button>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredAssets.map((asset) => {
            const isVideo = ['short_video', 'reel', 'shorts', 'video'].includes(asset.format.toLowerCase());
            const isCarousel = asset.format.toLowerCase().includes('carousel');
            const studioPath = getStudioRoute(asset);
            const studioLabel = getStudioName(asset);

            return (
              <div
                key={asset.id}
                className="bg-white rounded-2xl border border-slate-200 shadow-xs hover:shadow-md transition flex flex-col overflow-hidden"
              >
                {/* Media Preview Container */}
                <div className="relative h-48 bg-slate-800 flex items-center justify-center overflow-hidden border-b border-slate-100">
                  {asset.preview_url ? (
                    isVideo ? (
                      <video
                        src={asset.preview_url}
                        className="w-full h-full object-cover opacity-90"
                        muted
                        playsInline
                        onMouseOver={(e) => (e.currentTarget as HTMLVideoElement).play().catch(() => {})}
                        onMouseOut={(e) => (e.currentTarget as HTMLVideoElement).pause()}
                      />
                    ) : (
                      <img
                        src={asset.preview_url}
                        alt={asset.hook || 'Asset preview'}
                        className="w-full h-full object-cover"
                      />
                    )
                  ) : (
                    <div className="flex flex-col items-center justify-center text-slate-400">
                      {isVideo ? <Video className="w-8 h-8 mb-2" /> : isCarousel ? <Layers className="w-8 h-8 mb-2" /> : <ImageIcon className="w-8 h-8 mb-2" />}
                      <span className="text-[11px]">Ready in Studio</span>
                    </div>
                  )}

                  {/* Badges on preview */}
                  <div className="absolute top-3 left-3 flex items-center space-x-2">
                    <PlatformBadge platform={asset.platform} />
                    <FormatBadge format={asset.format} />
                  </div>
                  <div className="absolute top-3 right-3">
                    <StatusBadge status={asset.approval_status} />
                  </div>

                  {asset.day_number && (
                    <div className="absolute bottom-2 left-2 bg-slate-900/70 backdrop-blur text-white text-[10px] px-2 py-0.5 rounded font-mono">
                      Day {asset.day_number}
                    </div>
                  )}
                </div>

                {/* Content Details */}
                <div className="p-4 flex-1 flex flex-col justify-between space-y-4">
                  <div>
                    <h3 className="font-bold text-slate-900 text-sm line-clamp-2 leading-snug">
                      {asset.hook || 'Untitled Content Asset'}
                    </h3>
                    <p className="text-xs text-slate-500 mt-2 line-clamp-3 leading-relaxed">
                      {asset.caption || 'No caption copy available.'}
                    </p>

                    {publishMessage?.id === asset.id && (
                      <div className={`mt-2 p-2 rounded-lg text-xs font-medium flex items-center space-x-1.5 ${
                        publishMessage.type === 'success' ? 'bg-emerald-50 text-emerald-700' : 'bg-rose-50 text-rose-700'
                      }`}>
                        {publishMessage.type === 'success' ? <CheckCircle2 className="w-3.5 h-3.5" /> : <AlertCircle className="w-3.5 h-3.5" />}
                        <span>{publishMessage.text}</span>
                      </div>
                    )}
                  </div>

                  {/* Primary Studio Action */}
                  <div className="space-y-2 pt-2 border-t border-slate-100">
                    <button
                      onClick={() => navigate(studioPath)}
                      className="w-full inline-flex items-center justify-between px-3.5 py-2 bg-slate-50 hover:bg-indigo-50 border border-slate-200 hover:border-indigo-200 text-slate-700 hover:text-indigo-700 rounded-xl text-xs font-semibold transition"
                    >
                      <div className="flex items-center space-x-2">
                        {isVideo ? <Video className="w-3.5 h-3.5 text-indigo-600" /> : isCarousel ? <Layers className="w-3.5 h-3.5 text-indigo-600" /> : <ImageIcon className="w-3.5 h-3.5 text-indigo-600" />}
                        <span>Open in {studioLabel}</span>
                      </div>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </button>

                    {/* Social Publish & Actions Bar */}
                    <div className="flex items-center justify-between pt-1">
                      {/* Social Quick Publish */}
                      <div className="flex items-center space-x-1">
                        {isVideo && (
                          <button
                            disabled={actionLoading === asset.id}
                            onClick={() => handleQuickPublish(asset, 'youtube')}
                            className="p-1.5 rounded-lg border border-slate-200 text-rose-600 hover:bg-rose-50 transition"
                            title="Publish to YouTube Shorts"
                          >
                            <YoutubeIcon className="w-3.5 h-3.5" />
                          </button>
                        )}
                        <button
                          disabled={actionLoading === asset.id}
                          onClick={() => handleQuickPublish(asset, 'facebook')}
                          className="p-1.5 rounded-lg border border-slate-200 text-blue-600 hover:bg-blue-50 transition"
                          title="Publish to Facebook"
                        >
                          <FacebookIcon className="w-3.5 h-3.5" />
                        </button>
                        <button
                          disabled={actionLoading === asset.id}
                          onClick={() => handleQuickPublish(asset, 'instagram')}
                          className="p-1.5 rounded-lg border border-slate-200 text-pink-600 hover:bg-pink-50 transition"
                          title="Publish to Instagram"
                        >
                          <InstagramIcon className="w-3.5 h-3.5" />
                        </button>

                        <button
                          onClick={() => setScheduleTarget(asset)}
                          className="inline-flex items-center space-x-1 px-2 py-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 text-[11px] font-medium transition"
                          title="Schedule this asset"
                        >
                          <Calendar className="w-3 h-3 text-slate-500" />
                          <span>Schedule</span>
                        </button>
                      </div>

                      {/* Management Actions */}
                      <div className="flex items-center space-x-1">
                        <button
                          onClick={() => handleDuplicate(asset.id)}
                          disabled={actionLoading === asset.id}
                          className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition"
                          title="Duplicate Asset"
                        >
                          <Copy className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleDelete(asset.id)}
                          disabled={actionLoading === asset.id}
                          className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition"
                          title="Delete Asset"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => setActiveAsset(asset)}
                          className="p-1.5 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition"
                          title="Full Preview"
                        >
                          <Eye className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Schedule Modal */}
      {scheduleTarget && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center space-x-2">
                <Calendar className="w-5 h-5 text-indigo-600" />
                <h3 className="font-bold text-slate-900 text-sm">Schedule Content Slot</h3>
              </div>
              <button onClick={() => setScheduleTarget(null)} className="text-slate-400 hover:text-slate-600">✕</button>
            </div>

            <div className="py-4 space-y-4">
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                <div className="text-xs font-semibold text-slate-800 line-clamp-1">{scheduleTarget.hook}</div>
                <div className="text-[11px] text-slate-500 mt-1 flex items-center space-x-2">
                  <PlatformBadge platform={scheduleTarget.platform} size="sm" />
                  <FormatBadge format={scheduleTarget.format} />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1.5">Publish Date & Time (UTC)</label>
                <input
                  type="datetime-local"
                  value={scheduleDateTime}
                  onChange={(e) => setScheduleDateTime(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-xl text-xs focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                />
              </div>

              <div className="text-[11px] text-slate-500 bg-blue-50 text-blue-700 p-2.5 rounded-xl border border-blue-100">
                This post will be enqueued in the persistent background worker and dispatched automatically to {scheduleTarget.platform}.
              </div>
            </div>

            <div className="flex justify-end space-x-2 pt-3 border-t border-slate-100">
              <button
                onClick={() => setScheduleTarget(null)}
                className="px-4 py-2 border border-slate-200 rounded-xl text-xs font-medium text-slate-600 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                disabled={isScheduling}
                onClick={handleScheduleSubmit}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-semibold shadow-sm transition disabled:opacity-50"
              >
                {isScheduling ? 'Scheduling...' : 'Confirm Schedule'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Quick Preview Modal */}
      {activeAsset && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto shadow-2xl p-6 border border-slate-200">
            <div className="flex items-center justify-between pb-4 border-b border-slate-200">
              <div className="flex items-center space-x-2">
                <PlatformBadge platform={activeAsset.platform} />
                <FormatBadge format={activeAsset.format} />
                <span className="text-xs font-bold text-slate-900">Asset Preview & Details</span>
              </div>
              <button
                onClick={() => setActiveAsset(null)}
                className="text-slate-400 hover:text-slate-600 p-1 text-sm font-bold"
              >
                ✕
              </button>
            </div>

            <div className="py-4 space-y-4">
              {activeAsset.preview_url && (
                <div className="bg-slate-900 rounded-xl overflow-hidden max-h-80 flex items-center justify-center">
                  {['short_video', 'reel', 'shorts', 'video'].includes(activeAsset.format.toLowerCase()) ? (
                    <video src={activeAsset.preview_url} controls className="max-h-80 w-auto" />
                  ) : (
                    <img src={activeAsset.preview_url} alt="" className="max-h-80 w-auto object-contain" />
                  )}
                </div>
              )}

              <div>
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Hook / Headline</label>
                <div className="text-sm font-bold text-slate-900 mt-1">{activeAsset.hook}</div>
              </div>

              <div>
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Caption Copy</label>
                <div className="text-xs text-slate-700 bg-slate-50 p-3.5 rounded-xl border border-slate-100 mt-1 whitespace-pre-wrap font-sans leading-relaxed">
                  {activeAsset.caption}
                </div>
              </div>

              {activeAsset.cta && (
                <div>
                  <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Call to Action (CTA)</label>
                  <div className="text-xs text-indigo-600 font-semibold mt-1">{activeAsset.cta}</div>
                </div>
              )}

              {activeAsset.tracking_url && (
                <div>
                  <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">UTM Attribution Link</label>
                  <div className="text-xs font-mono text-slate-500 mt-1 truncate bg-slate-50 p-2 rounded-lg border border-slate-100">
                    {activeAsset.tracking_url}
                  </div>
                </div>
              )}
            </div>

            <div className="flex justify-between items-center pt-4 border-t border-slate-100">
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => {
                    const a = activeAsset;
                    setActiveAsset(null);
                    setScheduleTarget(a);
                  }}
                  className="px-3 py-2 border border-slate-200 rounded-xl text-xs font-semibold text-slate-700 hover:bg-slate-50 inline-flex items-center space-x-1"
                >
                  <Calendar className="w-3.5 h-3.5" />
                  <span>Schedule</span>
                </button>
              </div>

              <div className="flex items-center space-x-2">
                <button
                  onClick={() => setActiveAsset(null)}
                  className="px-4 py-2 border border-slate-200 rounded-xl text-xs font-medium text-slate-600 hover:bg-slate-50"
                >
                  Close
                </button>
                <button
                  onClick={() => {
                    const id = activeAsset.id;
                    const path = getStudioRoute(activeAsset);
                    setActiveAsset(null);
                    navigate(path);
                  }}
                  className="px-4 py-2 bg-indigo-600 text-white rounded-xl text-xs font-semibold hover:bg-indigo-700 shadow-sm"
                >
                  Open in {getStudioName(activeAsset)}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};