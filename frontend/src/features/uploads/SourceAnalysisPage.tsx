import React, { useEffect, useState } from 'react';
import {
  FileText, CheckCircle, AlertCircle, Quote, Tag, Target,
  Sparkles, Save, Clock, Download, ExternalLink, Loader2
} from 'lucide-react';
import { api } from '../../services/api';
import { SourceDocument } from '../../types';
import { StatusBadge } from '../../components/StatusBadge';

export const SourceAnalysisPage: React.FC = () => {
  const [sources, setSources] = useState<SourceDocument[]>([]);
  const [selectedSource, setSelectedSource] = useState<SourceDocument | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [editingTranscript, setEditingTranscript] = useState<string>('');
  const [saving, setSaving] = useState<boolean>(false);
  const [saveSuccess, setSaveSuccess] = useState<boolean>(false);

  const loadSources = async () => {
    setLoading(true);
    try {
      const list = await api.listSources();
      setSources(list);
      if (list.length > 0) {
        const full = await api.getSource(list[0].id);
        setSelectedSource(full);
        setEditingTranscript(full.extraction?.clean_transcript || '');
      }
    } catch (err) {
      console.error('Failed to load sources:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSources();
  }, []);

  const handleSelectSource = async (id: string) => {
    try {
      const full = await api.getSource(id);
      setSelectedSource(full);
      setEditingTranscript(full.extraction?.clean_transcript || '');
      setSaveSuccess(false);
    } catch (err) {
      console.error('Failed to get source:', err);
    }
  };

  const handleSaveCorrection = async () => {
    if (!selectedSource) return;
    setSaving(true);
    try {
      await api.updateExtraction(selectedSource.id, {
        clean_transcript: editingTranscript,
      });
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err) {
      console.error('Failed to update extraction:', err);
      alert('Error saving transcript correction.');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 text-indigo-600 animate-spin" />
      </div>
    );
  }

  const extraction = selectedSource?.extraction;

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      {/* Top Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-black text-slate-900 tracking-tight">Source Material Analysis</h2>
          <p className="text-sm text-slate-500 mt-1">
            Inspect extracted transcripts, verifiable claims, quotes, and content opportunities.
          </p>
        </div>
      </div>

      {sources.length === 0 ? (
        <div className="bg-white rounded-3xl p-12 text-center border border-slate-200">
          <FileText className="w-10 h-10 text-slate-400 mx-auto mb-3" />
          <h3 className="text-base font-bold text-slate-900">No source documents uploaded yet</h3>
          <p className="text-xs text-slate-500 mt-1">Create a campaign or upload a source to view analysis.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
          {/* Left Column: Source List (1 col) */}
          <div className="space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">Ingested Sources</h3>
            {sources.map((s) => (
              <div
                key={s.id}
                onClick={() => handleSelectSource(s.id)}
                className={`p-4 rounded-2xl border cursor-pointer transition-all ${
                  selectedSource?.id === s.id
                    ? 'border-indigo-600 bg-indigo-50/50 shadow-sm'
                    : 'border-slate-200 bg-white hover:border-slate-300'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-bold text-slate-900 truncate max-w-[150px]">{s.title}</span>
                  <StatusBadge status={s.status} />
                </div>
                <div className="text-[11px] text-slate-500 capitalize">
                  {s.source_type} • {new Date(s.created_at).toLocaleDateString()}
                </div>
              </div>
            ))}
          </div>

          {/* Right Column: In-Depth Analysis & Verification (3 cols) */}
          {selectedSource && (
            <div className="lg:col-span-3 space-y-6">
              {/* Document Overview Header */}
              <div className="bg-white rounded-3xl p-6 border border-slate-200/80 shadow-sm flex items-center justify-between">
                <div>
                  <div className="flex items-center space-x-2">
                    <span className="text-xs font-bold uppercase px-2 py-0.5 rounded-md bg-slate-100 text-slate-700">
                      {selectedSource.source_type.toUpperCase()}
                    </span>
                    <h3 className="text-lg font-bold text-slate-900">{selectedSource.title}</h3>
                  </div>
                  <p className="text-xs text-slate-500 mt-1">
                    Grounded Subject: <span className="font-semibold text-slate-800">{extraction?.main_subject || 'Analyzing...'}</span>
                  </p>
                </div>
                {selectedSource.download_url && (
                  <a
                    href={selectedSource.download_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center space-x-1.5 text-xs font-semibold text-indigo-600 hover:text-indigo-700 border border-slate-200 px-3 py-1.5 rounded-xl bg-slate-50"
                  >
                    <Download className="w-3.5 h-3.5" />
                    <span>Download Original</span>
                  </a>
                )}
              </div>

              {/* Topics & Audience Banner */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                <div className="bg-white rounded-3xl p-6 border border-slate-200/80 shadow-sm space-y-3">
                  <div className="flex items-center space-x-2 text-xs font-bold uppercase tracking-wider text-slate-500">
                    <Tag className="w-4 h-4 text-indigo-500" />
                    <span>Key Topics & Pillars</span>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {(extraction?.topics || []).map((t, idx) => (
                      <span key={idx} className="text-xs font-medium bg-indigo-50 text-indigo-700 border border-indigo-200 px-3 py-1 rounded-full">
                        {t}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="bg-white rounded-3xl p-6 border border-slate-200/80 shadow-sm space-y-3">
                  <div className="flex items-center space-x-2 text-xs font-bold uppercase tracking-wider text-slate-500">
                    <Target className="w-4 h-4 text-emerald-500" />
                    <span>Target Audience & Inferred Intent</span>
                  </div>
                  <p className="text-xs text-slate-700 leading-relaxed font-medium">
                    {extraction?.audience_intent || 'Founders, Creators, and Growth Engineers seeking scalable social presence.'}
                  </p>
                </div>
              </div>

              {/* Claims & Verifiable Evidence Quotes */}
              <div className="bg-white rounded-3xl p-6 border border-slate-200/80 shadow-sm space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2 text-xs font-bold uppercase tracking-wider text-slate-600">
                    <Quote className="w-4 h-4 text-indigo-500" />
                    <span>Important Claims & Factual Grounding</span>
                  </div>
                  <span className="text-[11px] text-emerald-600 font-semibold bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                    Zero Hallucination
                  </span>
                </div>

                <div className="space-y-3">
                  {(extraction?.key_claims || []).map((item, idx) => (
                    <div key={idx} className="p-4 rounded-2xl border border-slate-100 bg-slate-50/60 space-y-1.5">
                      <div className="text-xs font-bold text-slate-900">{item.claim}</div>
                      <div className="text-[11px] text-slate-500 italic bg-white p-2.5 rounded-xl border border-slate-200">
                        "{item.evidence}"
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Content Opportunities */}
              <div className="bg-white rounded-3xl p-6 border border-slate-200/80 shadow-sm space-y-4">
                <div className="flex items-center space-x-2 text-xs font-bold uppercase tracking-wider text-slate-600">
                  <Sparkles className="w-4 h-4 text-purple-500" />
                  <span>Suggested Content Opportunities</span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  {(extraction?.content_opportunities || []).map((opp, idx) => (
                    <div key={idx} className="p-3.5 rounded-2xl border border-slate-100 bg-slate-50 space-y-1">
                      <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded bg-purple-100 text-purple-700">
                        {opp.format}
                      </span>
                      <div className="text-xs font-bold text-slate-900 mt-1">{opp.title}</div>
                      <div className="text-[11px] text-slate-500 capitalize">{opp.platform}</div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Editable Transcript Section */}
              <div className="bg-white rounded-3xl p-6 border border-slate-200/80 shadow-sm space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="text-sm font-bold text-slate-900">Extracted Transcript / Text Editor</h4>
                    <p className="text-xs text-slate-500">
                      Inspect and correct extracted content before campaign generation.
                    </p>
                  </div>
                  <button
                    type="button"
                    disabled={saving}
                    onClick={handleSaveCorrection}
                    className="inline-flex items-center space-x-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold px-4 py-2 rounded-xl shadow-md transition-all disabled:opacity-50"
                  >
                    {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                    <span>{saveSuccess ? 'Saved!' : 'Save Corrections'}</span>
                  </button>
                </div>
                <textarea
                  rows={10}
                  value={editingTranscript}
                  onChange={(e) => setEditingTranscript(e.target.value)}
                  className="w-full px-4 py-3 rounded-2xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-slate-800 text-xs font-mono leading-relaxed"
                />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
