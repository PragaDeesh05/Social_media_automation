import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Video, Sparkles, Play, RefreshCw, Save, CheckCircle,
  AlertCircle, ChevronRight, Layers, FileText, Plus, Trash2,
  Sliders, ArrowUp, ArrowDown, ExternalLink, Download, Calendar,
  Share2, Clock, Film
} from 'lucide-react';
import { YoutubeIcon, InstagramIcon, FacebookIcon } from '../../components/SocialIcons';
import { api } from '../../services/api';
import { ContentAsset, AssetMedia, Platform } from '../../types';
import { PlatformBadge } from '../../components/PlatformBadge';
import { FormatBadge } from '../../components/FormatBadge';
import { StatusBadge } from '../../components/StatusBadge';

interface SceneDetail {
  scene_idx?: number;
  duration_s?: number;
  narration?: string;
  on_screen_headline?: string;
  visual_beats?: string[];
}

export const VideoGenerationPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const urlAssetId = searchParams.get('id');

  // Studio Mode: 'studio' (Player & Storyboard) | 'editor' (Copy & Metadata)
  const [activeTab, setActiveTab] = useState<'studio' | 'editor'>('studio');

  // Asset list & selection
  const [videoList, setVideoList] = useState<ContentAsset[]>([]);
  const [selectedAssetId, setSelectedAssetId] = useState<string>('');
  const [currentAssetData, setCurrentAssetData] = useState<any>(null);
  const [loadingAsset, setLoadingAsset] = useState<boolean>(false);

  // Generation Modal States
  const [showGenerateModal, setShowGenerateModal] = useState<boolean>(false);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [genStatus, setGenStatus] = useState<string>('');

  // Generation Form Fields
  const [genBrand, setGenBrand] = useState<string>('IncuBrix');
  const [genGoal, setGenGoal] = useState<string>('Drive CreatorOps Trial Signups');
  const [genUseCase, setGenUseCase] = useState<string>(
    'Why solo creators burn out in 2026: paying $100/mo across 4 fragmented tools instead of one unified CreatorOps studio.'
  );
  const [genScenesCount, setGenScenesCount] = useState<number>(3);
  const [genVoice, setGenVoice] = useState<string>(''); // empty = autonomous director selection
  const [genAspect, setGenAspect] = useState<string>('9:16');
  const [genPlatform, setGenPlatform] = useState<string>('youtube');

  // Scheduling Modal State
  const [showScheduleModal, setShowScheduleModal] = useState<boolean>(false);
  const [scheduleDateTime, setScheduleDateTime] = useState<string>(() => {
    const d = new Date(Date.now() + 24 * 3600 * 1000);
    return d.toISOString().slice(0, 16);
  });
  const [isScheduling, setIsScheduling] = useState<boolean>(false);

  // Direct Publishing State
  const [publishingPlatform, setPublishingPlatform] = useState<string | null>(null);
  const [publishMessage, setPublishMessage] = useState<string>('');

  // Asset Editor States
  const [editorHook, setEditorHook] = useState<string>('');
  const [editorCaption, setEditorCaption] = useState<string>('');
  const [editorHashtags, setEditorHashtags] = useState<string>('');
  const [editorCta, setEditorCta] = useState<string>('');
  const [editorSaving, setEditorSaving] = useState<boolean>(false);

  useEffect(() => {
    fetchVideoList();
  }, []);

  useEffect(() => {
    if (urlAssetId) {
      setSelectedAssetId(urlAssetId);
    }
  }, [urlAssetId]);

  useEffect(() => {
    if (selectedAssetId) {
      loadVideoDetail(selectedAssetId);
    }
  }, [selectedAssetId]);

  const fetchVideoList = async () => {
    try {
      const assets = await api.listAssets();
      const vids = assets.filter(a => {
        const fmt = (a.format || '').toLowerCase();
        return fmt.includes('video') || fmt.includes('reel') || fmt.includes('short');
      });
      setVideoList(vids);
      if (vids.length > 0 && !selectedAssetId) {
        setSelectedAssetId(vids[0].id);
      }
    } catch (e) {
      console.error('Failed to load video assets:', e);
    }
  };

  const loadVideoDetail = async (id: string) => {
    setLoadingAsset(true);
    try {
      const data: any = await api.getAsset(id);
      setCurrentAssetData(data);
      setEditorHook(data.asset?.hook || data.hook || '');
      setEditorCaption(data.asset?.caption || data.caption || '');
      setEditorHashtags(((data.asset?.hashtags || data.hashtags) || []).join(', '));
      setEditorCta(data.asset?.cta || data.cta || '');
    } catch (e) {
      console.error('Failed to load video detail:', e);
    } finally {
      setLoadingAsset(false);
    }
  };

  const handleGenerateVideo = async () => {
    if (!genUseCase.trim()) return;
    setIsGenerating(true);
    setGenStatus('Director: Gemini is developing narrative arc & visual storyboard...');

    const timer1 = setTimeout(() => {
      setGenStatus('Voice: Synthesizing narration with Google Cloud TTS (Chirp 3 HD)...');
    }, 5000);

    const timer2 = setTimeout(() => {
      setGenStatus('Animator: Writing animated vector SVGs with CSS keyframes...');
    }, 12000);

    const timer3 = setTimeout(() => {
      setGenStatus('Renderer: Playwright Chromium is stepping frames at 30 FPS...');
    }, 25000);

    const timer4 = setTimeout(() => {
      setGenStatus('Assembler: FFmpeg joining scenes with seamless xfade transitions...');
    }, 45000);

    try {
      const res = await api.generateVideo({
        brand: genBrand,
        goal: genGoal,
        use_case: genUseCase,
        scenes_count: genScenesCount,
        voice: genVoice || undefined,
        aspect: genAspect,
        platform: genPlatform,
      });

      setShowGenerateModal(false);
      await fetchVideoList();
      if (res.asset_id) {
        setSelectedAssetId(res.asset_id);
      }
    } catch (e: any) {
      alert('Video generation failed: ' + (e.response?.data?.detail || e.message));
    } finally {
      clearTimeout(timer1);
      clearTimeout(timer2);
      clearTimeout(timer3);
      clearTimeout(timer4);
      setIsGenerating(false);
      setGenStatus('');
    }
  };

  const handlePublishNow = async (targetPlatform: string) => {
    if (!selectedAssetId) return;
    setPublishingPlatform(targetPlatform);
    setPublishMessage('');
    try {
      const res = await api.publishAssetDirectly(selectedAssetId, targetPlatform);
      setPublishMessage(`Successfully published! Post ID: ${res.post_id || 'OK'}`);
      await loadVideoDetail(selectedAssetId);
    } catch (e: any) {
      alert('Publishing failed: ' + (e.response?.data?.detail || e.message));
    } finally {
      setPublishingPlatform(null);
    }
  };

  const handleScheduleVideo = async () => {
    if (!selectedAssetId || !scheduleDateTime) return;
    setIsScheduling(true);
    try {
      await api.scheduleAssetDirectly(selectedAssetId, scheduleDateTime, genPlatform);
      setShowScheduleModal(false);
      alert('Video successfully scheduled into Content Calendar!');
      await loadVideoDetail(selectedAssetId);
    } catch (e: any) {
      alert('Scheduling failed: ' + (e.response?.data?.detail || e.message));
    } finally {
      setIsScheduling(false);
    }
  };

  const handleSaveEditorChanges = async () => {
    if (!selectedAssetId) return;
    setEditorSaving(true);
    try {
      const tags = editorHashtags.split(',').map(t => t.trim().replace(/^#/, '')).filter(Boolean);
      await api.updateAsset(selectedAssetId, {
        hook: editorHook,
        caption: editorCaption,
        hashtags: tags,
        cta: editorCta,
      });
      alert('Video copy successfully updated!');
      await loadVideoDetail(selectedAssetId);
    } catch (e: any) {
      alert('Failed to update asset: ' + e.message);
    } finally {
      setEditorSaving(false);
    }
  };

  const asset = currentAssetData?.asset || currentAssetData || {};
  const mediaInfo = currentAssetData?.media_info || {};
  const scenes: SceneDetail[] = mediaInfo.scenes || mediaInfo.storyboard?.scenes || [];
  const videoStreamUrl = mediaInfo.stream_url || (currentAssetData?.media && currentAssetData.media[0]?.presigned_url);

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-indigo-50 border border-indigo-200 flex items-center justify-center text-indigo-600">
              <Film className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-bold text-slate-900 tracking-tight">Video Generation Studio</h2>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-indigo-50 text-indigo-700 border border-indigo-200">
                  Animated SVG + GCP Chirp 3 HD
                </span>
              </div>
              <p className="text-xs text-slate-500">
                Deterministic frame-by-frame rendered 9:16 vertical videos with burned-in subtitles, AI voiceover, and FFmpeg transitions.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {/* Video Selector */}
          <select
            value={selectedAssetId}
            onChange={(e) => setSelectedAssetId(e.target.value)}
            className="px-3 py-1.5 text-xs bg-white border border-slate-300 rounded-lg font-mono text-slate-700 focus:outline-none focus:border-indigo-500 shadow-sm"
          >
            {videoList.length > 0 ? (
              videoList.map(v => (
                <option key={v.id} value={v.id}>
                  {v.hook ? (v.hook.slice(0, 32) + '...') : v.id} ({v.platform})
                </option>
              ))
            ) : (
              <option value="">No videos generated yet</option>
            )}
          </select>

          {/* Trigger Generate Modal */}
          <button
            onClick={() => setShowGenerateModal(true)}
            className="px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 shadow-sm transition-all"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Generate Animated Video</span>
          </button>
        </div>
      </div>

      {/* Mode Navigation Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-200 pb-2">
        <button
          onClick={() => setActiveTab('studio')}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors flex items-center gap-1.5 ${
            activeTab === 'studio'
              ? 'bg-slate-800 text-white'
              : 'text-slate-600 hover:bg-slate-100'
          }`}
        >
          <Play className="w-3.5 h-3.5" />
          <span>Video Player & Storyboard</span>
        </button>
        <button
          onClick={() => setActiveTab('editor')}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors flex items-center gap-1.5 ${
            activeTab === 'editor'
              ? 'bg-slate-800 text-white'
              : 'text-slate-600 hover:bg-slate-100'
          }`}
        >
          <FileText className="w-3.5 h-3.5" />
          <span>Asset Copy & Metadata Editor</span>
        </button>
      </div>

      {publishMessage && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-lg text-xs flex items-center gap-2">
          <CheckCircle className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{publishMessage}</span>
        </div>
      )}

      {/* STUDIO VIEW */}
      {activeTab === 'studio' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Column: Player & Action Deck (5 cols) */}
          <div className="lg:col-span-5 bg-slate-900 p-6 rounded-xl border border-slate-800 shadow-sm flex flex-col items-center">
            {/* 9:16 Video Canvas */}
            <div className="w-full max-w-[280px] aspect-[9/16] bg-black rounded-lg overflow-hidden shadow-2xl relative border border-slate-800">
              {videoStreamUrl ? (
                <video
                  key={videoStreamUrl}
                  src={videoStreamUrl}
                  controls
                  autoPlay
                  loop
                  playsInline
                  className="w-full h-full object-cover"
                />
              ) : (
                <div className="w-full h-full flex flex-col items-center justify-center text-slate-500 text-xs p-4 text-center space-y-2">
                  <Film className="w-8 h-8 text-slate-600" />
                  <span>No video selected or rendered yet. Click "Generate Animated Video" to create one.</span>
                </div>
              )}
            </div>

            {/* Video Specs Strip */}
            <div className="flex items-center justify-between w-full max-w-[280px] text-[11px] text-slate-400 font-mono mt-3">
              <span>1080 &times; 1920</span>
              <span className="text-indigo-400 font-semibold">{mediaInfo.voice_name || 'GCP Chirp 3 HD'}</span>
              <span>30 FPS</span>
            </div>

            {/* Direct Publishing Deck */}
            <div className="w-full max-w-[280px] space-y-2 mt-4 pt-3 border-t border-slate-800">
              <button
                disabled={!videoStreamUrl || publishingPlatform !== null}
                onClick={() => handlePublishNow('YouTube Shorts')}
                className="w-full py-2 bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white rounded-lg text-xs font-bold flex items-center justify-center gap-2 shadow-sm transition-all"
                title="Publish directly as a YouTube Short"
              >
                <YoutubeIcon className="w-4 h-4" />
                <span>{publishingPlatform === 'YouTube Shorts' ? 'Publishing...' : 'Publish to YouTube Shorts'}</span>
              </button>

              <button
                disabled={!videoStreamUrl || publishingPlatform !== null}
                onClick={() => handlePublishNow('YouTube Video')}
                className="w-full py-2 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-slate-200 rounded-lg text-xs font-semibold flex items-center justify-center gap-2 border border-slate-700 transition-all"
              >
                <YoutubeIcon className="w-3.5 h-3.5 text-red-400" />
                <span>{publishingPlatform === 'YouTube Video' ? 'Publishing...' : 'Publish as YouTube Video'}</span>
              </button>

              <div className="grid grid-cols-2 gap-2">
                <button
                  disabled={!videoStreamUrl || publishingPlatform !== null}
                  onClick={() => handlePublishNow('Instagram')}
                  className="py-2 bg-gradient-to-r from-pink-600 to-rose-600 hover:from-pink-500 hover:to-rose-500 disabled:opacity-50 text-white rounded-lg text-xs font-bold flex items-center justify-center gap-1.5 shadow-sm transition-all"
                >
                  <InstagramIcon className="w-3.5 h-3.5" />
                  <span>{publishingPlatform === 'Instagram' ? '...' : 'IG Reels'}</span>
                </button>

                <button
                  disabled={!videoStreamUrl || publishingPlatform !== null}
                  onClick={() => handlePublishNow('Facebook')}
                  className="py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg text-xs font-bold flex items-center justify-center gap-1.5 shadow-sm transition-all"
                >
                  <FacebookIcon className="w-3.5 h-3.5" />
                  <span>{publishingPlatform === 'Facebook' ? '...' : 'FB Video'}</span>
                </button>
              </div>

              <div className="grid grid-cols-2 gap-2 pt-1">
                <button
                  disabled={!videoStreamUrl}
                  onClick={() => setShowScheduleModal(true)}
                  className="py-1.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-slate-200 border border-slate-700 rounded-lg text-[11px] font-semibold flex items-center justify-center gap-1.5 transition-all"
                >
                  <Calendar className="w-3 h-3 text-indigo-400" />
                  <span>Schedule</span>
                </button>

                {videoStreamUrl && (
                  <a
                    href={videoStreamUrl}
                    download="incubrix_video.mp4"
                    className="py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-lg text-[11px] font-semibold flex items-center justify-center gap-1.5 transition-all"
                  >
                    <Download className="w-3 h-3 text-emerald-400" />
                    <span>Download</span>
                  </a>
                )}
              </div>
            </div>
          </div>

          {/* Right Column: Storyboard Scene Breakdown (7 cols) */}
          <div className="lg:col-span-7 space-y-4">
            <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                <div>
                  <h3 className="text-sm font-bold text-slate-900">Director Storyboard Breakdown</h3>
                  <p className="text-xs text-slate-500">Autonomous multi-scene narration script with burned-in captions</p>
                </div>
                <span className="text-xs font-mono font-bold text-indigo-600 bg-indigo-50 px-2.5 py-1 rounded-md border border-indigo-100">
                  {scenes.length} Scenes
                </span>
              </div>

              {scenes.length > 0 ? (
                <div className="space-y-3">
                  {scenes.map((s, idx) => (
                    <div
                      key={idx}
                      className="p-3.5 rounded-lg border border-slate-200 bg-slate-50/60 hover:bg-slate-50 transition-colors space-y-2"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-mono font-bold text-slate-700">
                          Scene {s.scene_idx || idx + 1}
                        </span>
                        <span className="text-[10px] font-mono px-2 py-0.5 bg-white border border-slate-200 rounded text-slate-600">
                          {s.duration_s ? `${s.duration_s.toFixed(1)}s` : 'Beat'}
                        </span>
                      </div>

                      {s.on_screen_headline && (
                        <div>
                          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                            On-Screen Headline
                          </span>
                          <p className="text-xs font-semibold text-slate-900 mt-0.5">
                            {s.on_screen_headline}
                          </p>
                        </div>
                      )}

                      {s.narration && (
                        <div>
                          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
                            Voiceover Narration
                          </span>
                          <p className="text-xs text-slate-700 mt-0.5 italic">
                            "{s.narration}"
                          </p>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="p-8 text-center text-slate-500 text-xs">
                  Select a generated video or create a new one to view scene breakdown.
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ASSET EDITOR VIEW */}
      {activeTab === 'editor' && (
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm space-y-5">
          <div>
            <h3 className="text-sm font-bold text-slate-900">Edit Asset Copy & Social Captions</h3>
            <p className="text-xs text-slate-500">
              Customize headline hooks, multi-line captions, call-to-actions, and platform hashtags.
            </p>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Headline Hook</label>
              <input
                type="text"
                value={editorHook}
                onChange={(e) => setEditorHook(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs text-slate-800 focus:outline-none focus:border-indigo-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Full Caption</label>
              <textarea
                rows={4}
                value={editorCaption}
                onChange={(e) => setEditorCaption(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs text-slate-800 focus:outline-none focus:border-indigo-500"
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Call To Action (CTA)</label>
                <input
                  type="text"
                  value={editorCta}
                  onChange={(e) => setEditorCta(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs text-slate-800 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Hashtags (Comma Separated)</label>
                <input
                  type="text"
                  value={editorHashtags}
                  onChange={(e) => setEditorHashtags(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs text-slate-800 focus:outline-none focus:border-indigo-500"
                />
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <button
                disabled={editorSaving}
                onClick={handleSaveEditorChanges}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 shadow-sm"
              >
                <Save className="w-3.5 h-3.5" />
                <span>{editorSaving ? 'Saving Version...' : 'Save Revisions'}</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* GENERATE VIDEO MODAL */}
      {showGenerateModal && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-2xl border border-slate-200 max-w-xl w-full p-6 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-indigo-600" />
                <span>Generate Animated Ad Video</span>
              </h3>
              <button
                disabled={isGenerating}
                onClick={() => setShowGenerateModal(false)}
                className="text-slate-400 hover:text-slate-600 font-bold"
              >
                &times;
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Brand Name</label>
                <input
                  type="text"
                  value={genBrand}
                  onChange={(e) => setGenBrand(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs text-slate-800 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Goal or Topic</label>
                <input
                  type="text"
                  value={genGoal}
                  onChange={(e) => setGenGoal(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs text-slate-800 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Core Narrative / Use Case</label>
                <textarea
                  rows={3}
                  value={genUseCase}
                  onChange={(e) => setGenUseCase(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs text-slate-800 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Scene Count</label>
                  <input
                    type="number"
                    min={2}
                    max={5}
                    value={genScenesCount}
                    onChange={(e) => setGenScenesCount(Number(e.target.value))}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs text-slate-800 focus:outline-none focus:border-indigo-500 font-mono"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Voice Narrator</label>
                  <select
                    value={genVoice}
                    onChange={(e) => setGenVoice(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs text-slate-800 focus:outline-none focus:border-indigo-500"
                  >
                    <option value="">Autonomous Director Selection</option>
                    <option value="Kore">Kore (Confident, energetic, upbeat)</option>
                    <option value="Aoede">Aoede (Warm, breezy storyteller)</option>
                    <option value="Puck">Puck (Upbeat, playful, lively)</option>
                    <option value="Fenrir">Fenrir (Excitable, high-energy)</option>
                    <option value="Orus">Orus (Firm, authoritative, bold)</option>
                    <option value="Leda">Leda (Youthful, bright)</option>
                    <option value="Charon">Charon (Smooth, informative)</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Aspect Ratio</label>
                  <select
                    value={genAspect}
                    onChange={(e) => setGenAspect(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs text-slate-800 focus:outline-none focus:border-indigo-500"
                  >
                    <option value="9:16">9:16 Vertical (Shorts & Reels)</option>
                    <option value="16:9">16:9 Widescreen (YouTube Video)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Target Platform</label>
                  <select
                    value={genPlatform}
                    onChange={(e) => setGenPlatform(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs text-slate-800 focus:outline-none focus:border-indigo-500"
                  >
                    <option value="youtube">YouTube Shorts</option>
                    <option value="instagram">Instagram Reels</option>
                    <option value="facebook">Facebook Video</option>
                  </select>
                </div>
              </div>
            </div>

            {isGenerating && (
              <div className="p-3 bg-indigo-50 border border-indigo-200 rounded-lg text-xs text-indigo-900 flex items-center gap-2">
                <RefreshCw className="w-4 h-4 animate-spin text-indigo-600 shrink-0" />
                <span className="font-medium">{genStatus}</span>
              </div>
            )}

            <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
              <button
                disabled={isGenerating}
                onClick={() => setShowGenerateModal(false)}
                className="px-3 py-1.5 border border-slate-300 hover:bg-slate-50 text-slate-700 rounded-lg text-xs font-semibold"
              >
                Cancel
              </button>
              <button
                disabled={isGenerating}
                onClick={handleGenerateVideo}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>{isGenerating ? 'Rendering...' : 'Generate Video'}</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* SCHEDULE MODAL */}
      {showScheduleModal && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-2xl border border-slate-200 max-w-sm w-full p-5 space-y-4">
            <div className="flex items-center justify-between pb-2 border-b border-slate-100">
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-1.5">
                <Calendar className="w-4 h-4 text-indigo-600" />
                <span>Schedule Video Release</span>
              </h3>
              <button onClick={() => setShowScheduleModal(false)} className="text-slate-400 font-bold">&times;</button>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Release Date & Time</label>
              <input
                type="datetime-local"
                value={scheduleDateTime}
                onChange={(e) => setScheduleDateTime(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs font-mono text-slate-800 focus:outline-none focus:border-indigo-500"
              />
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setShowScheduleModal(false)}
                className="px-3 py-1.5 border border-slate-300 hover:bg-slate-50 text-slate-700 rounded-lg text-xs font-semibold"
              >
                Cancel
              </button>
              <button
                disabled={isScheduling}
                onClick={handleScheduleVideo}
                className="px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5"
              >
                <Clock className="w-3.5 h-3.5" />
                <span>{isScheduling ? 'Scheduling...' : 'Confirm Schedule'}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
