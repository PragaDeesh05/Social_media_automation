import React, { useEffect, useState } from 'react';
import {
  Image as ImageIcon, Sparkles, Save, CheckCircle, ExternalLink,
  Download, RefreshCw, Palette, Type, Sliders, Calendar,
  Clock, Check, ZoomIn, Eye
} from 'lucide-react';
import { InstagramIcon, FacebookIcon } from '../../components/SocialIcons';
import { api } from '../../services/api';
import { ContentAsset } from '../../types';

export const PosterGenerationPage: React.FC = () => {
  // Asset list & selection
  const [posterList, setPosterList] = useState<ContentAsset[]>([]);
  const [selectedAssetId, setSelectedAssetId] = useState<string>('');
  const [posterData, setPosterData] = useState<any>(null);
  const [loadingPoster, setLoadingPoster] = useState<boolean>(false);

  // View state
  const [viewFormat, setViewFormat] = useState<'svg' | 'png'>('svg');
  const [downloading, setDownloading] = useState<string | null>(null);

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
  const [genAspect, setGenAspect] = useState<string>('1:1');
  const [genDirection, setGenDirection] = useState<string>('bold, high-contrast and punchy');
  const [genLanguage, setGenLanguage] = useState<string>('English');
  const [genPlatform, setGenPlatform] = useState<string>('instagram');

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

  useEffect(() => {
    fetchPosterList();
  }, []);

  useEffect(() => {
    if (selectedAssetId) {
      loadPosterDetail(selectedAssetId);
    }
  }, [selectedAssetId]);

  const fetchPosterList = async () => {
    try {
      const assets = await api.listAssets();
      const posters = assets.filter(a => {
        const fmt = (a.format || '').toLowerCase();
        return !fmt.includes('video') && !fmt.includes('carousel') && !fmt.includes('short');
      });
      setPosterList(posters);
      if (posters.length > 0 && !selectedAssetId) {
        setSelectedAssetId(posters[0].id);
      }
    } catch (e) {
      console.error('Failed to load poster assets:', e);
    }
  };

  const loadPosterDetail = async (id: string) => {
    setLoadingPoster(true);
    try {
      const data = await api.getAsset(id);
      setPosterData(data);
    } catch (e) {
      console.error('Failed to load poster detail:', e);
    } finally {
      setLoadingPoster(false);
    }
  };

  const handleGeneratePoster = async () => {
    if (!genUseCase.trim()) return;
    setIsGenerating(true);
    setGenStatus('Art Director: Gemini is writing creative brief & layout plan...');
    try {
      const res = await api.generatePoster({
        brand: genBrand,
        goal: genGoal,
        use_case: genUseCase,
        aspect: genAspect,
        direction: genDirection,
        language: genLanguage,
        variants: 1,
        platform: genPlatform,
      });

      setShowGenerateModal(false);
      await fetchPosterList();
      if (res.asset_id) {
        setSelectedAssetId(res.asset_id);
      }
    } catch (e: any) {
      alert('Poster generation failed: ' + (e.response?.data?.detail || e.message));
    } finally {
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
      setPublishMessage(`Published to ${targetPlatform}! Post ID: ${res.post_id || 'OK'}`);
      await loadPosterDetail(selectedAssetId);
    } catch (e: any) {
      alert('Publishing failed: ' + (e.response?.data?.detail || e.message));
    } finally {
      setPublishingPlatform(null);
    }
  };

  const handleSchedulePoster = async () => {
    if (!selectedAssetId || !scheduleDateTime) return;
    setIsScheduling(true);
    try {
      await api.scheduleAssetDirectly(selectedAssetId, scheduleDateTime, genPlatform);
      setShowScheduleModal(false);
      alert('Poster scheduled into Content Calendar!');
      await loadPosterDetail(selectedAssetId);
    } catch (e: any) {
      alert('Scheduling failed: ' + (e.response?.data?.detail || e.message));
    } finally {
      setIsScheduling(false);
    }
  };

  const asset = posterData?.asset || posterData || {};
  const mediaInfo = posterData?.media_info || {};
  const brief = mediaInfo.brief || {};
  const copy = brief.copy || {};
  const ds = brief.design_system || {};
  const palette = ds.palette || {
    bg: '#0F172A',
    bg_alt: '#1E293B',
    primary: '#4F46E5',
    secondary: '#EC4899',
    accent: '#10B981',
    paper: '#F8FAFC',
    ink: '#0F172A',
  };

  const aidName = mediaInfo.aid || (asset as any)?.aid || (asset as any)?.id || 'poster';
  const svgUrl = mediaInfo.svg_url;
  const pngUrl = mediaInfo.png_url || mediaInfo.image_url;
  const currentPreviewUrl = (viewFormat === 'svg' && svgUrl) ? svgUrl : (pngUrl || svgUrl);

  const downloadFile = async (url: string, filename: string) => {
    if (!url) return;
    setDownloading(filename);
    try {
      const resp = await fetch(url);
      if (!resp.ok) throw new Error(`HTTP error ${resp.status}`);
      const blob = await resp.blob();
      const blobUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = blobUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(blobUrl);
    } catch (e) {
      console.warn('Direct blob download failed, falling back to window.open:', e);
      window.open(url, '_blank');
    } finally {
      setDownloading(null);
    }
  };

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-indigo-50 border border-indigo-200 flex items-center justify-center text-indigo-600">
              <ImageIcon className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-bold text-slate-900 tracking-tight">Vector Ad Poster Studio</h2>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-indigo-50 text-indigo-700 border border-indigo-200">
                  Static SVG + Chromium PNG
                </span>
              </div>
              <p className="text-xs text-slate-500">
                Art-directed static vector posters with guaranteed typographic contrast, layout zones, and inlined Google Fonts.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {/* Poster Selector */}
          <select
            value={selectedAssetId}
            onChange={(e) => setSelectedAssetId(e.target.value)}
            className="px-3 py-1.5 text-xs bg-white border border-slate-300 rounded-lg font-mono text-slate-700 focus:outline-none focus:border-indigo-500 shadow-sm"
          >
            {posterList.length > 0 ? (
              posterList.map(p => (
                <option key={p.id} value={p.id}>
                  {p.hook ? (p.hook.slice(0, 32) + '...') : p.id} ({p.platform})
                </option>
              ))
            ) : (
              <option value="">No posters generated yet</option>
            )}
          </select>

          {/* Trigger Generate Modal */}
          <button
            onClick={() => setShowGenerateModal(true)}
            className="px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 shadow-sm"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Generate Ad Poster</span>
          </button>

          <button
            disabled={!currentPreviewUrl || publishingPlatform !== null}
            onClick={() => handlePublishNow('Instagram')}
            className="px-3.5 py-1.5 bg-gradient-to-r from-pink-600 to-rose-600 hover:from-pink-500 hover:to-rose-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 shadow-sm"
          >
            <InstagramIcon className="w-3.5 h-3.5" />
            <span>{publishingPlatform === 'Instagram' ? 'Publishing...' : 'Publish to IG'}</span>
          </button>

          <button
            disabled={!currentPreviewUrl || publishingPlatform !== null}
            onClick={() => handlePublishNow('Facebook')}
            className="px-3.5 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 shadow-sm"
          >
            <FacebookIcon className="w-3.5 h-3.5" />
            <span>{publishingPlatform === 'Facebook' ? 'Publishing...' : 'Publish to FB'}</span>
          </button>

          <button
            disabled={!currentPreviewUrl}
            onClick={() => setShowScheduleModal(true)}
            className="px-3 py-1.5 bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 rounded-lg text-xs font-semibold flex items-center gap-1.5 shadow-sm"
          >
            <Calendar className="w-3.5 h-3.5 text-indigo-600" />
            <span>Schedule Poster</span>
          </button>
        </div>
      </div>

      {publishMessage && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-lg text-xs flex items-center gap-2">
          <Check className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{publishMessage}</span>
        </div>
      )}

      {/* Main Studio Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Canvas Preview (7 cols) */}
        <div className="lg:col-span-7 space-y-4">
          <div className="bg-white p-3 rounded-xl border border-slate-200 flex items-center justify-between text-xs shadow-sm">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setViewFormat('svg')}
                className={`px-3 py-1.5 rounded-lg font-medium transition-colors ${
                  viewFormat === 'svg'
                    ? 'bg-slate-800 text-white'
                    : 'text-slate-600 hover:bg-slate-100'
                }`}
              >
                Vector SVG View
              </button>
              <button
                onClick={() => setViewFormat('png')}
                className={`px-3 py-1.5 rounded-lg font-medium transition-colors ${
                  viewFormat === 'png'
                    ? 'bg-slate-800 text-white'
                    : 'text-slate-600 hover:bg-slate-100'
                }`}
              >
                Chromium PNG View
              </button>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                disabled={!pngUrl || downloading !== null}
                onClick={() => downloadFile(pngUrl, `${aidName}.png`)}
                className="px-2.5 py-1 bg-slate-100 hover:bg-slate-200 disabled:opacity-50 text-slate-700 rounded font-medium flex items-center gap-1 transition-colors cursor-pointer text-xs"
                title="Download high-resolution Chromium PNG"
              >
                <Download className="w-3 h-3 text-indigo-600" />
                <span>{downloading === `${aidName}.png` ? 'Saving...' : 'PNG'}</span>
              </button>
              <button
                type="button"
                disabled={!svgUrl || downloading !== null}
                onClick={() => downloadFile(svgUrl, `${aidName}.svg`)}
                className="px-2.5 py-1 bg-slate-100 hover:bg-slate-200 disabled:opacity-50 text-slate-700 rounded font-medium flex items-center gap-1 transition-colors cursor-pointer text-xs"
                title="Download vector SVG"
              >
                <Download className="w-3 h-3 text-indigo-600" />
                <span>{downloading === `${aidName}.svg` ? 'Saving...' : 'SVG'}</span>
              </button>
            </div>
          </div>

          <div className="bg-slate-900 rounded-xl p-8 border border-slate-800 shadow-sm flex items-center justify-center min-h-[500px]">
            {currentPreviewUrl ? (
              <div className="max-w-[420px] w-full rounded-lg overflow-hidden shadow-2xl border border-slate-800 bg-black flex items-center justify-center">
                {viewFormat === 'svg' ? (
                  <iframe
                    key={svgUrl || currentPreviewUrl}
                    src={svgUrl || currentPreviewUrl}
                    title="Ad Poster SVG"
                    className="w-full aspect-square border-0"
                    sandbox="allow-scripts allow-same-origin"
                  />
                ) : (
                  <img
                    key={pngUrl || currentPreviewUrl}
                    src={pngUrl || currentPreviewUrl}
                    alt="Ad Poster PNG View"
                    className="w-full h-auto object-contain"
                    onError={(e) => {
                      const target = e.currentTarget;
                      if (!target.dataset.tried) {
                        target.dataset.tried = '1';
                        target.src = `/api/v1/media/stream?key=graphics/${aidName}.png`;
                      } else if (target.dataset.tried === '1' && svgUrl) {
                        target.dataset.tried = '2';
                        target.src = svgUrl;
                      }
                    }}
                  />
                )}
              </div>
            ) : (
              <div className="text-center text-slate-500 text-xs p-6 space-y-2">
                <ImageIcon className="w-8 h-8 text-slate-600 mx-auto" />
                <span>No poster selected. Click "Generate Ad Poster" to create vector graphics.</span>
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Design System & Brief Inspector (5 cols) */}
        <div className="lg:col-span-5 space-y-4">
          {/* Creative Brief */}
          <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-3">
            <h3 className="text-xs font-bold text-slate-900 uppercase font-mono tracking-wider">
              Creative Brief & Copy
            </h3>
            <div className="space-y-2.5 text-xs">
              <div>
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Headline</span>
                <p className="font-semibold text-slate-900 mt-0.5">{copy.headline || asset.hook || 'N/A'}</p>
              </div>
              <div>
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Support</span>
                <p className="text-slate-700 mt-0.5">{copy.support || asset.caption || 'N/A'}</p>
              </div>
              <div>
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Call To Action</span>
                <p className="font-mono text-indigo-600 font-bold mt-0.5">{copy.cta || asset.cta || 'N/A'}</p>
              </div>
            </div>
          </div>

          {/* Design System & Palette */}
          <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-3">
            <h3 className="text-xs font-bold text-slate-900 uppercase font-mono tracking-wider">
              Design System Palette
            </h3>
            <div className="grid grid-cols-4 gap-2">
              {Object.entries(palette).map(([name, hex]: [string, any]) => (
                <div key={name} className="p-2 rounded border border-slate-200 bg-slate-50 text-center space-y-1">
                  <div
                    className="w-full h-6 rounded border border-slate-300"
                    style={{ backgroundColor: hex }}
                  />
                  <p className="text-[9px] font-bold text-slate-600 capitalize truncate">{name}</p>
                  <p className="text-[9px] font-mono text-slate-400 truncate">{hex}</p>
                </div>
              ))}
            </div>

            {ds.fonts && (
              <div className="pt-2 border-t border-slate-100 text-xs space-y-1">
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Typography</span>
                <p className="text-slate-800">
                  <span className="font-semibold">Display:</span> {ds.fonts.display || 'Archivo Black'} &bull;{' '}
                  <span className="font-semibold">Body:</span> {ds.fonts.body || 'Inter'}
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* GENERATE POSTER MODAL */}
      {showGenerateModal && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-2xl border border-slate-200 max-w-xl w-full p-6 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-indigo-600" />
                <span>Generate Vector Ad Poster</span>
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
                <label className="block text-xs font-semibold text-slate-700 mb-1">Goal or Campaign Topic</label>
                <input
                  type="text"
                  value={genGoal}
                  onChange={(e) => setGenGoal(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs text-slate-800 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Core Pitch / Use Case</label>
                <textarea
                  rows={3}
                  value={genUseCase}
                  onChange={(e) => setGenUseCase(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs text-slate-800 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Aspect Ratio</label>
                  <select
                    value={genAspect}
                    onChange={(e) => setGenAspect(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs text-slate-800 focus:outline-none focus:border-indigo-500"
                  >
                    <option value="1:1">1:1 Square (Instagram Feed)</option>
                    <option value="4:5">4:5 Portrait (Instagram Portrait)</option>
                    <option value="9:16">9:16 Vertical (Stories)</option>
                    <option value="16:9">16:9 Landscape (LinkedIn Banner)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Art Direction</label>
                  <select
                    value={genDirection}
                    onChange={(e) => setGenDirection(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs text-slate-800 focus:outline-none focus:border-indigo-500"
                  >
                    <option value="bold, high-contrast and punchy">Bold, high-contrast & punchy</option>
                    <option value="warm, premium and elegant">Warm, premium & elegant</option>
                    <option value="playful, colourful and energetic">Playful, colourful & energetic</option>
                    <option value="clean, modern and airy">Clean, modern & airy</option>
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
                onClick={handleGeneratePoster}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>{isGenerating ? 'Rendering...' : 'Generate Poster'}</span>
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
                <span>Schedule Poster Release</span>
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
                onClick={handleSchedulePoster}
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
