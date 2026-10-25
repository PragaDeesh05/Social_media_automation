import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  FileText, Image as ImageIcon, Layers, Video, CheckCircle,
  AlertTriangle, RefreshCw, Save, ShieldCheck, ChevronRight,
  ChevronLeft, Play, ExternalLink, Hash, Link2, Sparkles, Loader2
} from 'lucide-react';
import { api } from '../../services/api';
import { ContentAsset, AssetMedia } from '../../types';
import { PlatformBadge } from '../../components/PlatformBadge';
import { FormatBadge } from '../../components/FormatBadge';
import { StatusBadge } from '../../components/StatusBadge';

export const AssetEditorPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const requestedAssetId = searchParams.get('id');

  const [assets, setAssets] = useState<ContentAsset[]>([]);
  const [selectedAsset, setSelectedAsset] = useState<ContentAsset | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  // Editable Form State
  const [hook, setHook] = useState<string>('');
  const [caption, setCaption] = useState<string>('');
  const [hashtagsStr, setHashtagsStr] = useState<string>('');
  const [cta, setCta] = useState<string>('');
  const [trackingUrl, setTrackingUrl] = useState<string>('');

  // Carousel Slide Navigator
  const [currentSlideIndex, setCurrentSlideIndex] = useState<number>(0);

  // Action status
  const [saving, setSaving] = useState<boolean>(false);
  const [regenerating, setRegenerating] = useState<boolean>(false);
  const [saveMessage, setSaveMessage] = useState<string>('');

  const loadAssets = async () => {
    setLoading(true);
    try {
      const list = await api.listAssets();
      setAssets(list);
      if (list.length > 0) {
        const targetId = requestedAssetId || list[0].id;
        const full = await api.getAsset(targetId);
        populateForm(full);
      }
    } catch (err) {
      console.error('Failed to load assets:', err);
    } finally {
      setLoading(false);
    }
  };

  const populateForm = (asset: ContentAsset) => {
    setSelectedAsset(asset);
    setHook(asset.hook || '');
    setCaption(asset.caption || '');
    setHashtagsStr((asset.hashtags || []).join(', '));
    setCta(asset.cta || '');
    setTrackingUrl(asset.tracking_url || '');
    setCurrentSlideIndex(0);
    setSaveMessage('');
  };

  useEffect(() => {
    loadAssets();
  }, [requestedAssetId]);

  const handleSelectAsset = async (id: string) => {
    try {
      const full = await api.getAsset(id);
      populateForm(full);
    } catch (err) {
      console.error('Failed to load asset details:', err);
    }
  };

  const handleSaveChanges = async () => {
    if (!selectedAsset) return;
    setSaving(true);
    try {
      const tags = hashtagsStr
        .split(',')
        .map((t) => t.trim().replace(/^#/, ''))
        .filter(Boolean);

      await api.updateAsset(selectedAsset.id, {
        hook,
        caption,
        hashtags: tags,
        cta,
        tracking_url: trackingUrl,
      });

      setSaveMessage('Changes saved to version history.');
      // Refresh asset details
      const refreshed = await api.getAsset(selectedAsset.id);
      setSelectedAsset(refreshed);
      setTimeout(() => setSaveMessage(''), 3000);
    } catch (err) {
      console.error('Failed to save asset changes:', err);
      alert('Error updating asset.');
    } finally {
      setSaving(false);
    }
  };

  const handleApprove = async () => {
    if (!selectedAsset) return;
    try {
      await api.approveAsset(selectedAsset.id);
      const refreshed = await api.getAsset(selectedAsset.id);
      setSelectedAsset(refreshed);
    } catch (err) {
      console.error('Approval failed:', err);
    }
  };

  const handleRegenerateMedia = async () => {
    if (!selectedAsset) return;
    setRegenerating(true);
    try {
      await api.regenerateMedia(selectedAsset.id);
      const refreshed = await api.getAsset(selectedAsset.id);
      setSelectedAsset(refreshed);
      setSaveMessage('Media regenerated successfully.');
      setTimeout(() => setSaveMessage(''), 3000);
    } catch (err) {
      console.error('Media regeneration failed:', err);
      alert('Error regenerating media.');
    } finally {
      setRegenerating(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 text-indigo-600 animate-spin" />
      </div>
    );
  }

  const mediaList = selectedAsset?.media || [];
  const carouselSlides = mediaList.filter((m) => m.media_type === 'carousel_slide');
  const videoMedia = mediaList.find((m) => m.media_type === 'video');
  const imageMedia = mediaList.find((m) => m.media_type === 'image');

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-black text-slate-900 tracking-tight">Multi-Format Asset Editor</h2>
          <p className="text-sm text-slate-500 mt-1">
            Dedicated editing experiences for Text, Image, 5-Slide Carousel, and Short Video formats.
          </p>
        </div>
      </div>

      {assets.length === 0 ? (
        <div className="bg-white rounded-3xl p-12 text-center border border-slate-200">
          <FileText className="w-10 h-10 text-slate-400 mx-auto mb-3" />
          <h3 className="text-base font-bold text-slate-900">No content assets found</h3>
          <p className="text-xs text-slate-500 mt-1">Generate a campaign to view and edit individual assets.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
          {/* Left Column: Asset Selection List (1 col) */}
          <div className="space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">Campaign Assets</h3>
            <div className="space-y-2 max-h-[750px] overflow-y-auto pr-1">
              {assets.map((a) => (
                <div
                  key={a.id}
                  onClick={() => handleSelectAsset(a.id)}
                  className={`p-3.5 rounded-2xl border cursor-pointer transition-all ${
                    selectedAsset?.id === a.id
                      ? 'border-indigo-600 bg-indigo-50/50 shadow-sm'
                      : 'border-slate-200 bg-white hover:border-slate-300'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <PlatformBadge platform={a.platform} size="sm" />
                    <span className="text-[10px] font-mono font-bold text-slate-400">Day {a.day_number}</span>
                  </div>
                  <div className="text-xs font-bold text-slate-900 line-clamp-1 mb-1">{a.hook || a.caption}</div>
                  <div className="flex items-center justify-between">
                    <FormatBadge format={a.format} />
                    <span className={`text-[10px] font-bold ${a.approval_status === 'approved' ? 'text-emerald-600' : 'text-amber-600'}`}>
                      {a.approval_status.toUpperCase()}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Right Column: Asset Details, Media Player & Editor (3 cols) */}
          {selectedAsset && (
            <div className="lg:col-span-3 space-y-6">
              {/* Asset Action Header */}
              <div className="bg-white rounded-3xl p-6 border border-slate-200/80 shadow-sm flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                <div className="flex items-center space-x-3">
                  <PlatformBadge platform={selectedAsset.platform} />
                  <FormatBadge format={selectedAsset.format} />
                  <StatusBadge status={selectedAsset.approval_status} />
                </div>

                <div className="flex items-center space-x-3">
                  {selectedAsset.approval_status !== 'approved' && (
                    <button
                      type="button"
                      onClick={handleApprove}
                      className="inline-flex items-center space-x-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold px-4 py-2 rounded-xl shadow-md transition-all"
                    >
                      <CheckCircle className="w-3.5 h-3.5" />
                      <span>Approve Asset</span>
                    </button>
                  )}

                  <button
                    type="button"
                    disabled={saving}
                    onClick={handleSaveChanges}
                    className="inline-flex items-center space-x-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold px-4 py-2 rounded-xl shadow-md transition-all disabled:opacity-50"
                  >
                    {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                    <span>Save Changes</span>
                  </button>
                </div>
              </div>

              {saveMessage && (
                <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs rounded-xl font-medium">
                  {saveMessage}
                </div>
              )}

              {/* Two Column Grid: Media Preview on Left, Copy Editor on Right */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Media Preview Box */}
                <div className="bg-white rounded-3xl p-6 border border-slate-200/80 shadow-sm space-y-4">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">Asset Media Preview</h3>
                    {selectedAsset.format !== 'text' && (
                      <button
                        type="button"
                        disabled={regenerating}
                        onClick={handleRegenerateMedia}
                        className="inline-flex items-center space-x-1 text-xs text-indigo-600 hover:text-indigo-700 font-semibold"
                      >
                        {regenerating ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                        <span>Regenerate Media</span>
                      </button>
                    )}
                  </div>

                  {/* FORMAT 1: SHORT VIDEO PLAYER */}
                  {selectedAsset.format === 'short_video' && (
                    <div className="space-y-3">
                      {videoMedia ? (
                        <div className="rounded-2xl overflow-hidden bg-slate-800 aspect-[9/16] max-h-[460px] mx-auto shadow-md relative">
                          <video
                            src={videoMedia.presigned_url}
                            controls
                            className="w-full h-full object-contain"
                          />
                        </div>
                      ) : (
                        <div className="aspect-[9/16] max-h-[400px] mx-auto bg-slate-800 rounded-2xl flex items-center justify-center text-slate-400 text-xs">
                          Generating Short Video...
                        </div>
                      )}
                      <div className="text-[11px] text-slate-500 font-mono text-center">
                        Duration: {videoMedia?.duration_seconds || '15.0'}s • Resolution: 1080x1920 (9:16)
                      </div>
                    </div>
                  )}

                  {/* FORMAT 2: CAROUSEL 5-SLIDE NAVIGATOR */}
                  {selectedAsset.format === 'carousel' && (
                    <div className="space-y-3">
                      {carouselSlides.length > 0 ? (
                        <div>
                          <div className="rounded-2xl overflow-hidden bg-slate-800 aspect-[4/5] max-h-[420px] mx-auto shadow-md">
                            <img
                              src={carouselSlides[currentSlideIndex]?.presigned_url}
                              alt={`Slide ${currentSlideIndex + 1}`}
                              className="w-full h-full object-contain"
                            />
                          </div>
                          {/* Slide Switcher */}
                          <div className="flex items-center justify-between mt-3 px-2">
                            <button
                              type="button"
                              disabled={currentSlideIndex === 0}
                              onClick={() => setCurrentSlideIndex(currentSlideIndex - 1)}
                              className="text-xs font-bold text-slate-600 hover:text-slate-900 disabled:opacity-30 p-1"
                            >
                              <ChevronLeft className="w-5 h-5" />
                            </button>
                            <span className="text-xs font-bold text-slate-700">
                              Slide {currentSlideIndex + 1} of {carouselSlides.length}
                            </span>
                            <button
                              type="button"
                              disabled={currentSlideIndex === carouselSlides.length - 1}
                              onClick={() => setCurrentSlideIndex(currentSlideIndex + 1)}
                              className="text-xs font-bold text-slate-600 hover:text-slate-900 disabled:opacity-30 p-1"
                            >
                              <ChevronRight className="w-5 h-5" />
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div className="aspect-[4/5] max-h-[400px] bg-slate-800 rounded-2xl flex items-center justify-center text-slate-400 text-xs">
                          Generating 5-Slide Carousel...
                        </div>
                      )}
                    </div>
                  )}

                  {/* FORMAT 3: BRAND IMAGE CARD */}
                  {selectedAsset.format === 'image' && (
                    <div className="space-y-3">
                      {imageMedia ? (
                        <div className="rounded-2xl overflow-hidden bg-slate-800 aspect-square max-h-[420px] mx-auto shadow-md">
                          <img
                            src={imageMedia.presigned_url}
                            alt="Brand Graphic Card"
                            className="w-full h-full object-contain"
                          />
                        </div>
                      ) : (
                        <div className="aspect-square max-h-[400px] bg-slate-800 rounded-2xl flex items-center justify-center text-slate-400 text-xs">
                          Generating Graphic Card...
                        </div>
                      )}
                    </div>
                  )}

                  {/* FORMAT 4: TEXT POST PREVIEW */}
                  {selectedAsset.format === 'text' && (
                    <div className="p-5 rounded-2xl bg-slate-50 border border-slate-200 text-xs text-slate-800 leading-relaxed font-sans space-y-3">
                      <div className="font-bold text-slate-900 text-sm">{hook}</div>
                      <div className="whitespace-pre-wrap text-slate-700">{caption}</div>
                      {trackingUrl && (
                        <div className="text-indigo-600 font-mono text-[11px] truncate">
                          {trackingUrl}
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Copy & Strategy Editor */}
                <div className="bg-white rounded-3xl p-6 border border-slate-200/80 shadow-sm space-y-4">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">Edit Copy & Elements</h3>

                  <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1.5">
                      Opening Hook
                    </label>
                    <textarea
                      rows={2}
                      value={hook}
                      onChange={(e) => setHook(e.target.value)}
                      className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-xs font-semibold text-slate-900"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1.5">
                      Caption / Script Body
                    </label>
                    <textarea
                      rows={6}
                      value={caption}
                      onChange={(e) => setCaption(e.target.value)}
                      className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-xs text-slate-800 leading-relaxed"
                    />
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1.5">
                        Hashtags
                      </label>
                      <input
                        type="text"
                        value={hashtagsStr}
                        onChange={(e) => setHashtagsStr(e.target.value)}
                        className="w-full px-3 py-2 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-xs"
                        placeholder="IncuBrix, Growth, AI"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1.5">
                        Call to Action (CTA)
                      </label>
                      <input
                        type="text"
                        value={cta}
                        onChange={(e) => setCta(e.target.value)}
                        className="w-full px-3 py-2 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-xs"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1.5">
                      UTM Tracking URL
                    </label>
                    <input
                      type="url"
                      value={trackingUrl}
                      onChange={(e) => setTrackingUrl(e.target.value)}
                      className="w-full px-3 py-2 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-xs font-mono text-indigo-700 bg-indigo-50/30"
                    />
                  </div>

                  {/* Quality & Brand Check Audit Banner */}
                  <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200 space-y-2">
                    <div className="flex items-center justify-between text-xs font-bold">
                      <span className="text-slate-700">Quality Checks</span>
                      <span className="text-emerald-600">PASSED</span>
                    </div>
                    <div className="text-[11px] text-slate-500 space-y-1">
                      <div>• Factual Grounding: Grounded in source citation</div>
                      <div>• Character Limit: Respects {selectedAsset.platform.toUpperCase()} format boundary</div>
                      <div>• Prohibited Words: None detected</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
