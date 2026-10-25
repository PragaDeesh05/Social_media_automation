import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Upload, Link as LinkIcon, FileText, CheckCircle2,
  Calendar, Layers, Video, Sparkles, ArrowRight, ArrowLeft, Loader2
} from 'lucide-react';
import { api } from '../../services/api';
import { Platform, ContentFormat } from '../../types';

export const CreateCampaignPage: React.FC = () => {
  const navigate = useNavigate();
  const [step, setStep] = useState<number>(1);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [uploadProgress, setUploadProgress] = useState<number>(0);

  // Form State
  const [campaignName, setCampaignName] = useState<string>('Q4 Global Content Engine');
  const [durationDays, setDurationDays] = useState<number>(30);
  const [timezone, setTimezone] = useState<string>('UTC');
  const [destinationUrl, setDestinationUrl] = useState<string>('https://incubrix.com/start');

  // Source Ingestion Mode
  const [sourceMode, setSourceMode] = useState<'upload' | 'url' | 'text'>('text');
  const [sourceFile, setSourceFile] = useState<File | null>(null);
  const [sourceUrl, setSourceUrl] = useState<string>('');
  const [sourceText, setSourceText] = useState<string>(
    `IncuBrix is an AI-powered social media content and repurposing platform.
It transforms a single core input—such as a podcast, blog post, product demo, or webinar—into a complete 30-day social media campaign across Instagram, Facebook, YouTube, and X.
Manual content repurposing currently consumes more than 10 hours each week for small content teams and creators.
By automating the conversion into platform-native formats (including 5-slide carousels, 9:16 short videos under 60 seconds with narration, and punchy text posts), IncuBrix ensures consistent daily posting without sacrificing brand authority.
Every hook and claim is grounded directly in verified source citations, eliminating AI hallucination.`
  );

  // Platform & Format selection
  const [selectedPlatforms, setSelectedPlatforms] = useState<Platform[]>(['youtube', 'facebook', 'instagram']);
  const [selectedFormats, setSelectedFormats] = useState<ContentFormat[]>(['short_video', 'image', 'carousel']);

  const togglePlatform = (p: Platform) => {
    if (selectedPlatforms.includes(p)) {
      if (selectedPlatforms.length > 1) {
        setSelectedPlatforms(selectedPlatforms.filter((x) => x !== p));
      }
    } else {
      setSelectedPlatforms([...selectedPlatforms, p]);
    }
  };

  const toggleFormat = (f: ContentFormat) => {
    if (selectedFormats.includes(f)) {
      if (selectedFormats.length > 1) {
        setSelectedFormats(selectedFormats.filter((x) => x !== f));
      }
    } else {
      setSelectedFormats([...selectedFormats, f]);
    }
  };

  const handleLaunchCampaign = async () => {
    setSubmitting(true);
    try {
      // 1. Ingest Source
      let sourceId: string | undefined = undefined;
      if (sourceMode === 'upload' && sourceFile) {
        const upRes = await api.uploadSourceFile(sourceFile, campaignName, setUploadProgress);
        sourceId = upRes.id;
      } else if (sourceMode === 'url' && sourceUrl) {
        const textRes = await api.ingestText({
          title: campaignName,
          url: sourceUrl,
          source_type: 'url',
        });
        sourceId = textRes.id;
      } else {
        const textRes = await api.ingestText({
          title: campaignName,
          text_content: sourceText,
          source_type: 'article',
        });
        sourceId = textRes.id;
      }

      // 2. Create Campaign
      const campRes = await api.createCampaign({
        name: campaignName,
        source_document_id: sourceId,
        duration_days: durationDays,
        platforms: selectedPlatforms,
        formats: selectedFormats,
        timezone_name: timezone,
      });

      // 3. Plan Campaign (creates schedule matrix)
      await api.planCampaign(campRes.id);

      // 4. Trigger Asset Generation
      await api.generateAssets(campRes.id);

      // 5. Navigate to Calendar
      navigate(`/calendar?campaign_id=${campRes.id}`);
    } catch (err: any) {
      console.error('Campaign creation failed:', err);
      alert(`Error launching campaign: ${err.response?.data?.detail || err.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-black text-slate-900 tracking-tight">Create 30-Day Campaign</h2>
        <p className="text-sm text-slate-500 mt-1">
          Turn your long-form content into platform-specific social posts, graphics, carousels, and videos.
        </p>
      </div>

      {/* Stepper Indicator */}
      <div className="grid grid-cols-4 gap-3">
        {[
          { num: 1, label: 'Details' },
          { num: 2, label: 'Source Material' },
          { num: 3, label: 'Platforms & Formats' },
          { num: 4, label: 'Review & Launch' },
        ].map((s) => (
          <div
            key={s.num}
            className={`p-3.5 rounded-2xl border text-center transition-all ${
              step === s.num
                ? 'bg-indigo-600 text-white border-indigo-600 shadow-md shadow-indigo-600/20'
                : step > s.num
                ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                : 'bg-white text-slate-400 border-slate-200'
            }`}
          >
            <div className="text-xs font-bold uppercase tracking-wider">Step 0{s.num}</div>
            <div className="text-sm font-semibold truncate mt-0.5">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Wizard Card Container */}
      <div className="bg-white rounded-3xl p-8 border border-slate-200/80 shadow-sm space-y-6">
        {/* STEP 1: CAMPAIGN DETAILS */}
        {step === 1 && (
          <div className="space-y-6">
            <h3 className="text-lg font-bold text-slate-900 border-b border-slate-100 pb-3">Campaign Parameters</h3>

            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-2">
                Campaign Name
              </label>
              <input
                type="text"
                value={campaignName}
                onChange={(e) => setCampaignName(e.target.value)}
                className="w-full px-4 py-3 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-900 text-sm font-medium"
                placeholder="e.g. Q4 Global Growth Teardown"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-2">
                  Duration (Calendar Days)
                </label>
                <input
                  type="number"
                  min={1}
                  max={90}
                  value={durationDays}
                  onChange={(e) => setDurationDays(Number(e.target.value))}
                  className="w-full px-4 py-3 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-900 text-sm font-medium"
                />
                <span className="text-xs text-slate-400 mt-1 block">Default: 30 days</span>
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-2">
                  Timezone
                </label>
                <select
                  value={timezone}
                  onChange={(e) => setTimezone(e.target.value)}
                  className="w-full px-4 py-3 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-900 text-sm font-medium bg-white"
                >
                  <option value="UTC">UTC (Coordinated Universal Time)</option>
                  <option value="America/New_York">Eastern Time (US & Canada)</option>
                  <option value="America/Los_Angeles">Pacific Time (US & Canada)</option>
                  <option value="Asia/Kolkata">India Standard Time (IST)</option>
                  <option value="Europe/London">London (GMT/BST)</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-2">
                Destination CTA Link
              </label>
              <input
                type="url"
                value={destinationUrl}
                onChange={(e) => setDestinationUrl(e.target.value)}
                className="w-full px-4 py-3 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-900 text-sm font-medium"
                placeholder="https://yourbrand.com/offer"
              />
              <span className="text-xs text-slate-400 mt-1 block">
                Automatic UTM tracking parameters will be appended for each platform and format.
              </span>
            </div>
          </div>
        )}

        {/* STEP 2: SOURCE INPUT */}
        {step === 2 && (
          <div className="space-y-6">
            <h3 className="text-lg font-bold text-slate-900 border-b border-slate-100 pb-3">Input Source Content</h3>

            {/* Source Mode Tabs */}
            <div className="flex space-x-2 bg-slate-100 p-1.5 rounded-2xl">
              <button
                type="button"
                onClick={() => setSourceMode('text')}
                className={`flex-1 py-2.5 rounded-xl text-xs font-bold transition-all flex items-center justify-center space-x-2 ${
                  sourceMode === 'text' ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                <FileText className="w-4 h-4" />
                <span>Text / Markdown</span>
              </button>
              <button
                type="button"
                onClick={() => setSourceMode('upload')}
                className={`flex-1 py-2.5 rounded-xl text-xs font-bold transition-all flex items-center justify-center space-x-2 ${
                  sourceMode === 'upload' ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                <Upload className="w-4 h-4" />
                <span>Upload File (PDF, Video, Audio)</span>
              </button>
              <button
                type="button"
                onClick={() => setSourceMode('url')}
                className={`flex-1 py-2.5 rounded-xl text-xs font-bold transition-all flex items-center justify-center space-x-2 ${
                  sourceMode === 'url' ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                <LinkIcon className="w-4 h-4" />
                <span>Web Article URL</span>
              </button>
            </div>

            {sourceMode === 'text' && (
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-2">
                  Article / Transcript Body
                </label>
                <textarea
                  rows={9}
                  value={sourceText}
                  onChange={(e) => setSourceText(e.target.value)}
                  className="w-full px-4 py-3 rounded-2xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-800 text-xs font-mono leading-relaxed"
                  placeholder="Paste article, webinar transcript, interview notes..."
                />
              </div>
            )}

            {sourceMode === 'upload' && (
              <div className="space-y-4">
                <div className="border-2 border-dashed border-slate-300 rounded-3xl p-8 text-center hover:border-indigo-500 transition-all bg-slate-50/50">
                  <Upload className="w-10 h-10 text-indigo-600 mx-auto mb-3" />
                  <div className="text-sm font-bold text-slate-900">
                    {sourceFile ? sourceFile.name : 'Choose a file to analyze'}
                  </div>
                  <p className="text-xs text-slate-500 mt-1 mb-4">
                    Supports PDF, DOCX, TXT, MP3, WAV, M4A, MP4, MOV (up to 150MB)
                  </p>
                  <label className="inline-flex items-center space-x-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs px-4 py-2.5 rounded-xl font-semibold cursor-pointer shadow-md">
                    <span>Browse Files</span>
                    <input
                      type="file"
                      className="hidden"
                      accept=".pdf,.docx,.doc,.txt,.md,.mp3,.wav,.m4a,.mp4,.mov"
                      onChange={(e) => {
                        if (e.target.files && e.target.files[0]) {
                          setSourceFile(e.target.files[0]);
                        }
                      }}
                    />
                  </label>
                </div>
                {uploadProgress > 0 && (
                  <div className="w-full bg-slate-100 rounded-full h-2.5 overflow-hidden">
                    <div
                      className="bg-indigo-600 h-2.5 rounded-full transition-all duration-300"
                      style={{ width: `${uploadProgress}%` }}
                    />
                  </div>
                )}
              </div>
            )}

            {sourceMode === 'url' && (
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-2">
                  Public Blog / Article URL
                </label>
                <input
                  type="url"
                  value={sourceUrl}
                  onChange={(e) => setSourceUrl(e.target.value)}
                  className="w-full px-4 py-3 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-900 text-sm font-medium"
                  placeholder="https://techcrunch.com/2026/10/example-article"
                />
              </div>
            )}
          </div>
        )}

        {/* STEP 3: PLATFORMS & FORMATS */}
        {step === 3 && (
          <div className="space-y-6">
            <h3 className="text-lg font-bold text-slate-900 border-b border-slate-100 pb-3">Distribution Channels</h3>

            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-3">
                Target Platforms
              </label>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                {[
                  { id: 'youtube', label: 'YouTube Shorts', sub: 'Vertical <=60s Videos' },
                  { id: 'facebook', label: 'Facebook', sub: 'Pages, Videos, Posts' },
                  { id: 'instagram', label: 'Instagram', sub: 'Reels, Carousels, Cards' },
                ].map((p) => {
                  const selected = selectedPlatforms.includes(p.id as Platform);
                  return (
                    <div
                      key={p.id}
                      onClick={() => togglePlatform(p.id as Platform)}
                      className={`p-4 rounded-2xl border-2 cursor-pointer transition-all ${
                        selected
                          ? 'border-indigo-600 bg-indigo-50/40 shadow-sm'
                          : 'border-slate-200 bg-white hover:border-slate-300'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-bold text-sm text-slate-900">{p.label}</span>
                        <div className={`w-4 h-4 rounded-full flex items-center justify-center ${selected ? 'bg-indigo-600 text-white' : 'border border-slate-300'}`}>
                          {selected && <CheckCircle2 className="w-3.5 h-3.5" />}
                        </div>
                      </div>
                      <p className="text-[11px] text-slate-500 leading-tight">{p.sub}</p>
                    </div>
                  );
                })}
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-3">
                Content Formats to Generate
              </label>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                {[
                  { id: 'short_video', label: 'Videos (<=60s)', desc: 'Vertical 9:16 narrated videos' },
                  { id: 'image', label: 'Posters', desc: 'Vector typography social graphics' },
                  { id: 'carousel', label: 'Carousels', desc: 'Multi-slide narrative PDFs/PNGs' },
                ].map((f) => {
                  const selected = selectedFormats.includes(f.id as ContentFormat);
                  return (
                    <div
                      key={f.id}
                      onClick={() => toggleFormat(f.id as ContentFormat)}
                      className={`p-4 rounded-2xl border-2 cursor-pointer transition-all ${
                        selected
                          ? 'border-indigo-600 bg-indigo-50/40 shadow-sm'
                          : 'border-slate-200 bg-white hover:border-slate-300'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-bold text-sm text-slate-900">{f.label}</span>
                        <div className={`w-4 h-4 rounded-full flex items-center justify-center ${selected ? 'bg-indigo-600 text-white' : 'border border-slate-300'}`}>
                          {selected && <CheckCircle2 className="w-3.5 h-3.5" />}
                        </div>
                      </div>
                      <p className="text-[11px] text-slate-500 leading-tight">{f.desc}</p>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* STEP 4: REVIEW & LAUNCH */}
        {step === 4 && (
          <div className="space-y-6">
            <h3 className="text-lg font-bold text-slate-900 border-b border-slate-100 pb-3">Strategy Review</h3>

            <div className="bg-slate-50 rounded-2xl p-6 border border-slate-200/80 space-y-4">
              <div className="flex justify-between items-center text-sm">
                <span className="text-slate-500">Campaign Name:</span>
                <span className="font-bold text-slate-900">{campaignName}</span>
              </div>
              <div className="flex justify-between items-center text-sm">
                <span className="text-slate-500">Duration:</span>
                <span className="font-bold text-slate-900">{durationDays} Days</span>
              </div>
              <div className="flex justify-between items-center text-sm">
                <span className="text-slate-500">Target Platforms:</span>
                <span className="font-bold text-slate-900 uppercase">{selectedPlatforms.join(', ')}</span>
              </div>
              <div className="flex justify-between items-center text-sm">
                <span className="text-slate-500">Calculated Slots:</span>
                <span className="font-bold text-indigo-600">{durationDays * selectedPlatforms.length} Total Scheduled Assets</span>
              </div>
              <div className="flex justify-between items-center text-sm">
                <span className="text-slate-500">Content Pillars:</span>
                <span className="font-bold text-slate-900">5 Grounded Pillars (Edu, How-To, Proof, Insights, CTA)</span>
              </div>
            </div>

            <div className="p-4 rounded-2xl bg-indigo-50/60 border border-indigo-200/80 text-xs text-indigo-900 flex items-start space-x-3">
              <Sparkles className="w-4 h-4 text-indigo-600 mt-0.5 flex-shrink-0" />
              <div>
                <span className="font-bold">Autonomous Multi-Stage Pipeline:</span> Clicking launch triggers semantic source chunking, structured extraction, 30-day matrix planning, graphic card rendering, 5-slide carousel generation, and &le;60s narrated video assembly in the background with persistent MinIO and PostgreSQL storage.
              </div>
            </div>
          </div>
        )}

        {/* Wizard Footer Controls */}
        <div className="flex items-center justify-between pt-4 border-t border-slate-100">
          {step > 1 ? (
            <button
              type="button"
              onClick={() => setStep(step - 1)}
              className="inline-flex items-center space-x-2 text-slate-600 hover:text-slate-900 text-xs font-bold px-4 py-2.5 rounded-xl border border-slate-200"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Back</span>
            </button>
          ) : <div />}

          {step < 4 ? (
            <button
              type="button"
              onClick={() => setStep(step + 1)}
              className="inline-flex items-center space-x-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold px-5 py-2.5 rounded-xl shadow-md shadow-indigo-600/20"
            >
              <span>Continue</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          ) : (
            <button
              type="button"
              disabled={submitting}
              onClick={handleLaunchCampaign}
              className="inline-flex items-center space-x-2 bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-500 hover:to-indigo-400 text-white text-sm font-bold px-6 py-3 rounded-xl shadow-lg shadow-indigo-600/30 disabled:opacity-50"
            >
              {submitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Launching Pipeline...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  <span>Launch 30-Day Campaign</span>
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
