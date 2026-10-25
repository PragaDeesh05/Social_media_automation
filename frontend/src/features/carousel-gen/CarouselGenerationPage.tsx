import React, { useEffect, useState } from 'react';
import {
  Layers, Sparkles, ChevronLeft, ChevronRight, Plus, Trash2,
  ArrowLeft, ArrowRight, Save, CheckCircle, Download, ExternalLink,
  RefreshCw, LayoutTemplate, Calendar, Maximize2,
  Clock, Check
} from 'lucide-react';
import { InstagramIcon, FacebookIcon } from '../../components/SocialIcons';
import { api } from '../../services/api';
import { ContentAsset } from '../../types';

interface CarouselSlide {
  slide_idx: number;
  svg_url?: string;
  png_url?: string;
}

export const CarouselGenerationPage: React.FC = () => {
  // Asset list & selection
  const [carouselList, setCarouselList] = useState<ContentAsset[]>([]);
  const [selectedAssetId, setSelectedAssetId] = useState<string>('');
  const [carouselData, setCarouselData] = useState<any>(null);
  const [loadingCarousel, setLoadingCarousel] = useState<boolean>(false);

  // View state
  const [activeSlideIdx, setActiveSlideIdx] = useState<number>(1);
  const [viewMode, setViewMode] = useState<'single' | 'panoramic'>('single');
  const [isNativeSize, setIsNativeSize] = useState<boolean>(false);

  // Generator form
  const [brand, setBrand] = useState<string>('IncuBrix');
  const [goal, setGoal] = useState<string>('Drive LinkedIn & Instagram Thought Leadership');
  const [numSlides, setNumSlides] = useState<number>(5);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [genStatus, setGenStatus] = useState<string>('');

  // Scheduling Modal
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
    fetchCarouselList();
  }, []);

  useEffect(() => {
    if (selectedAssetId) {
      loadCarouselDetail(selectedAssetId);
    }
  }, [selectedAssetId]);

  const fetchCarouselList = async () => {
    try {
      const assets = await api.listAssets();
      const carousels = assets.filter(a => (a.format || '').toLowerCase().includes('carousel'));
      setCarouselList(carousels);
      if (carousels.length > 0 && !selectedAssetId) {
        setSelectedAssetId(carousels[0].id);
      }
    } catch (e) {
      console.error('Failed to load carousels:', e);
    }
  };

  const loadCarouselDetail = async (id: string) => {
    setLoadingCarousel(true);
    try {
      const data = await api.getAsset(id);
      setCarouselData(data);
      setActiveSlideIdx(1);
    } catch (e) {
      console.error('Failed to load carousel detail:', e);
    } finally {
      setLoadingCarousel(false);
    }
  };

  const handleGenerateCarousel = async () => {
    setIsGenerating(true);
    setGenStatus('Director: Gemini is designing seam-crossing slides with CSS motion...');
    try {
      const res = await api.generateCarousel({
        brand,
        goal,
        num_slides: numSlides,
        platform: 'instagram',
      });

      await fetchCarouselList();
      if (res.asset_id) {
        setSelectedAssetId(res.asset_id);
      }
    } catch (e: any) {
      alert('Carousel generation failed: ' + (e.response?.data?.detail || e.message));
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
      await loadCarouselDetail(selectedAssetId);
    } catch (e: any) {
      alert('Publishing failed: ' + (e.response?.data?.detail || e.message));
    } finally {
      setPublishingPlatform(null);
    }
  };

  const handleScheduleCarousel = async () => {
    if (!selectedAssetId || !scheduleDateTime) return;
    setIsScheduling(true);
    try {
      await api.scheduleAssetDirectly(selectedAssetId, scheduleDateTime, 'instagram');
      setShowScheduleModal(false);
      alert('Carousel scheduled into Content Calendar!');
      await loadCarouselDetail(selectedAssetId);
    } catch (e: any) {
      alert('Scheduling failed: ' + (e.response?.data?.detail || e.message));
    } finally {
      setIsScheduling(false);
    }
  };

  const mediaInfo = carouselData?.media_info || {};
  const slides: CarouselSlide[] = mediaInfo.carousel_slides || [];
  const activeSlide = slides.find(s => s.slide_idx === activeSlideIdx) || slides[0];

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-indigo-50 border border-indigo-200 flex items-center justify-center text-indigo-600">
              <Layers className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-bold text-slate-900 tracking-tight">Carousel Creative Studio</h2>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-indigo-50 text-indigo-700 border border-indigo-200">
                  Gemini Animated SVG Engine
                </span>
              </div>
              <p className="text-xs text-slate-500">
                Seamless animated SVGs with 1080px crossing seams, CSS keyframe motion, and multi-page PDF export.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {/* Carousel Selector */}
          <select
            value={selectedAssetId}
            onChange={(e) => setSelectedAssetId(e.target.value)}
            className="px-3 py-1.5 text-xs bg-white border border-slate-300 rounded-lg font-mono text-slate-700 focus:outline-none focus:border-indigo-500 shadow-sm"
          >
            {carouselList.length > 0 ? (
              carouselList.map(c => (
                <option key={c.id} value={c.id}>
                  {c.hook ? (c.hook.slice(0, 32) + '...') : c.id}
                </option>
              ))
            ) : (
              <option value="">No carousels generated yet</option>
            )}
          </select>

          {mediaInfo.pdf_url && (
            <a
              href={mediaInfo.pdf_url}
              download="carousel.pdf"
              className="px-3 py-1.5 bg-white border border-slate-300 text-slate-700 rounded-lg text-xs font-semibold hover:bg-slate-50 flex items-center gap-1.5 shadow-sm"
            >
              <Download className="w-3.5 h-3.5 text-slate-600" />
              <span>Download PDF</span>
            </a>
          )}

          {mediaInfo.preview_player_url && (
            <a
              href={mediaInfo.preview_player_url}
              target="_blank"
              rel="noreferrer"
              className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 shadow-sm"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              <span>Open Live Runner</span>
            </a>
          )}

          <button
            disabled={slides.length === 0 || publishingPlatform !== null}
            onClick={() => handlePublishNow('Instagram')}
            className="px-3.5 py-1.5 bg-gradient-to-r from-pink-600 to-rose-600 hover:from-pink-500 hover:to-rose-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 shadow-sm"
          >
            <InstagramIcon className="w-3.5 h-3.5" />
            <span>{publishingPlatform === 'Instagram' ? 'Publishing...' : 'Publish Carousel (IG)'}</span>
          </button>

          <button
            disabled={slides.length === 0 || publishingPlatform !== null}
            onClick={() => handlePublishNow('Facebook')}
            className="px-3.5 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 shadow-sm"
          >
            <FacebookIcon className="w-3.5 h-3.5" />
            <span>{publishingPlatform === 'Facebook' ? 'Publishing...' : 'Publish to FB'}</span>
          </button>

          <button
            disabled={slides.length === 0}
            onClick={() => setShowScheduleModal(true)}
            className="px-3 py-1.5 bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 rounded-lg text-xs font-semibold flex items-center gap-1.5 shadow-sm"
          >
            <Calendar className="w-3.5 h-3.5 text-indigo-600" />
            <span>Schedule Carousel</span>
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
        {/* Left Panel: Slide Filmstrip & Quick Generator (3 cols) */}
        <div className="lg:col-span-3 space-y-4">
          <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm space-y-3">
            <span className="text-xs font-bold text-slate-900 uppercase font-mono tracking-wider block">
              Slide Sequence ({slides.length} Slides)
            </span>

            {slides.length > 0 ? (
              <div className="space-y-2 max-h-[380px] overflow-y-auto pr-1">
                {slides.map((s) => (
                  <div
                    key={s.slide_idx}
                    onClick={() => setActiveSlideIdx(s.slide_idx)}
                    className={`p-2.5 rounded-lg border text-left cursor-pointer transition-all flex items-center gap-3 ${
                      activeSlideIdx === s.slide_idx
                        ? 'border-indigo-600 bg-indigo-50/60 shadow-sm'
                        : 'border-slate-200 hover:border-slate-300 bg-white'
                    }`}
                  >
                    <div className="w-7 h-7 rounded bg-slate-100 flex items-center justify-center font-mono font-bold text-xs text-slate-600">
                      {s.slide_idx}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-bold text-slate-900 truncate">Slide {s.slide_idx}</p>
                      <p className="text-[10px] text-slate-500 font-mono">1080 &times; 1350 Vector</p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-500 italic">No slides yet. Generate a carousel below.</p>
            )}
          </div>

          {/* Quick Generator Box */}
          <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm space-y-3 text-xs">
            <span className="font-bold text-slate-900 uppercase font-mono block">
              Generate New Carousel
            </span>
            <div>
              <label className="block text-slate-600 font-medium mb-1">Brand Name</label>
              <input
                type="text"
                value={brand}
                onChange={(e) => setBrand(e.target.value)}
                className="w-full px-2.5 py-1.5 border border-slate-300 rounded text-xs text-slate-800 focus:outline-none focus:border-indigo-500"
              />
            </div>
            <div>
              <label className="block text-slate-600 font-medium mb-1">Goal / Topic</label>
              <input
                type="text"
                value={goal}
                onChange={(e) => setGoal(e.target.value)}
                className="w-full px-2.5 py-1.5 border border-slate-300 rounded text-xs text-slate-800 focus:outline-none focus:border-indigo-500"
              />
            </div>
            <div>
              <label className="block text-slate-600 font-medium mb-1">Slide Count (3 - 10)</label>
              <input
                type="number"
                min={3}
                max={10}
                value={numSlides}
                onChange={(e) => setNumSlides(Number(e.target.value))}
                className="w-full px-2.5 py-1.5 border border-slate-300 rounded font-mono text-xs text-slate-800 focus:outline-none focus:border-indigo-500"
              />
            </div>

            {isGenerating && (
              <div className="p-2 bg-indigo-50 border border-indigo-200 rounded text-[11px] text-indigo-900 flex items-center gap-1.5">
                <RefreshCw className="w-3.5 h-3.5 animate-spin text-indigo-600 shrink-0" />
                <span>{genStatus}</span>
              </div>
            )}

            <button
              disabled={isGenerating}
              onClick={handleGenerateCarousel}
              className="w-full py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg font-bold transition-all flex items-center justify-center gap-1.5 shadow-sm"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>{isGenerating ? 'Rendering Engine...' : 'Generate Animated SVGs'}</span>
            </button>
          </div>
        </div>

        {/* Center Panel: Unclipped Canvas & Controls (9 cols) */}
        <div className="lg:col-span-9 space-y-4">
          {/* Controls Bar */}
          <div className="bg-white p-3 rounded-xl border border-slate-200 flex items-center justify-between text-xs shadow-sm">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setViewMode('single')}
                className={`px-3 py-1.5 rounded-lg font-medium transition-colors ${
                  viewMode === 'single'
                    ? 'bg-slate-800 text-white'
                    : 'text-slate-600 hover:bg-slate-100'
                }`}
              >
                Single Slide View
              </button>
              <button
                onClick={() => setViewMode('panoramic')}
                className={`px-3 py-1.5 rounded-lg font-medium transition-colors ${
                  viewMode === 'panoramic'
                    ? 'bg-slate-800 text-white'
                    : 'text-slate-600 hover:bg-slate-100'
                }`}
              >
                Seamless Seam View (1080px Continuity)
              </button>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => setIsNativeSize(!isNativeSize)}
                className={`px-3 py-1.5 rounded-lg border font-medium ${
                  isNativeSize
                    ? 'border-indigo-600 bg-indigo-50 text-indigo-700'
                    : 'border-slate-300 text-slate-600'
                }`}
              >
                {isNativeSize ? 'Fit Scale' : '100% Native (1080x1350)'}
              </button>
            </div>
          </div>

          {/* Main Stage */}
          <div className="bg-slate-900 rounded-xl p-8 border border-slate-800 shadow-sm flex items-center justify-center overflow-auto min-h-[560px]">
            {viewMode === 'single' ? (
              <div
                className={`aspect-[4/5] bg-black shadow-2xl relative transition-all duration-300 rounded-lg overflow-hidden border border-slate-800 ${
                  isNativeSize ? 'w-[1080px] h-[1350px] shrink-0' : 'w-full max-w-[440px]'
                }`}
              >
                {activeSlide ? (
                  <iframe
                    key={`slide-${activeSlide.slide_idx}-${activeSlide.svg_url || activeSlide.png_url}`}
                    src={activeSlide.svg_url || activeSlide.png_url}
                    title={`Slide ${activeSlide.slide_idx}`}
                    className="w-full h-full border-0"
                    sandbox="allow-scripts allow-same-origin"
                  />
                ) : (
                  <div className="w-full h-full flex flex-col items-center justify-center text-slate-500 text-xs p-4 text-center">
                    <Layers className="w-8 h-8 text-slate-600 mb-2" />
                    <span>No slide selected. Generate a carousel to view.</span>
                  </div>
                )}
              </div>
            ) : (
              // Panoramic Seam View (All slides lined up horizontally)
              <div className="flex items-center gap-4 overflow-x-auto py-4 px-2 w-full max-w-full">
                {slides.map(s => (
                  <div
                    key={s.slide_idx}
                    onClick={() => setActiveSlideIdx(s.slide_idx)}
                    className="aspect-[4/5] w-[260px] shrink-0 bg-black rounded-lg overflow-hidden border border-slate-700 cursor-pointer shadow-lg hover:border-indigo-500 transition-all"
                  >
                    <iframe
                      src={s.svg_url || s.png_url}
                      title={`Slide ${s.slide_idx}`}
                      className="w-full h-full pointer-events-none border-0"
                    />
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* SCHEDULE MODAL */}
      {showScheduleModal && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-2xl border border-slate-200 max-w-sm w-full p-5 space-y-4">
            <div className="flex items-center justify-between pb-2 border-b border-slate-100">
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-1.5">
                <Calendar className="w-4 h-4 text-indigo-600" />
                <span>Schedule Carousel Release</span>
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
                onClick={handleScheduleCarousel}
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
