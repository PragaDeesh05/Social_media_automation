import React, { useState, useEffect } from 'react';
import { api } from '../../services/api';
import { BrandProfile } from '../../types';
import { Shield, Sparkles, AlertCircle, CheckCircle2, Save, Palette, BookOpen, AlertTriangle } from 'lucide-react';

export const BrandSettingsPage: React.FC = () => {
  const [profile, setProfile] = useState<BrandProfile>({
    brand_name: 'IncuBrix AI',
    target_audience: 'B2B SaaS Founders, Growth Marketers, Enterprise Content Leads',
    tone_of_voice: 'Authoritative, analytical, actionable, crisp, zero-fluff',
    vocabulary_rules: 'Use data-backed phrases, active voice, and concrete engineering metrics.',
    words_to_avoid: ['synergy', 'revolutionary', 'game-changing', 'disruptive', '10x engineer'],
    default_cta: 'Explore verified growth playbooks at incubrix.com/engine',
    primary_color: '#4F46E5',
    secondary_color: '#06B6D4',
    verified_product_facts: [
      'IncuBrix operates 100% on official Meta Graph v19, YouTube Data v3, and X v2 APIs.',
      'All media is stored in S3/MinIO with presigned cryptographic expiration.',
      'Supports end-to-end 30-day multi-platform generation with verified grounding citations.'
    ],
  });

  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // New item inputs
  const [newAvoidWord, setNewAvoidWord] = useState('');
  const [newFact, setNewFact] = useState('');

  useEffect(() => {
    fetchProfile();
  }, []);

  const fetchProfile = async () => {
    setLoading(true);
    try {
      const profiles = await api.getBrandProfiles();
      if (profiles && profiles.length > 0) {
        setProfile(profiles[0]);
      }
    } catch (err: any) {
      console.warn('Could not load brand profile, using defaults:', err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setFeedback(null);

    try {
      if (profile.id) {
        const updated = await api.updateBrandProfile(profile.id, profile);
        setProfile(updated);
      } else {
        const created = await api.createBrandProfile(profile);
        setProfile(created);
      }
      setFeedback({ type: 'success', message: 'Brand guidelines & compliance rules saved successfully!' });
    } catch (err: any) {
      setFeedback({
        type: 'error',
        message: err.response?.data?.detail || err.message || 'Failed to save brand profile.'
      });
    } finally {
      setSaving(false);
    }
  };

  const addAvoidWord = () => {
    const trimmed = newAvoidWord.trim();
    if (trimmed && !profile.words_to_avoid.includes(trimmed)) {
      setProfile({
        ...profile,
        words_to_avoid: [...profile.words_to_avoid, trimmed]
      });
      setNewAvoidWord('');
    }
  };

  const removeAvoidWord = (word: string) => {
    setProfile({
      ...profile,
      words_to_avoid: profile.words_to_avoid.filter(w => w !== word)
    });
  };

  const addFact = () => {
    const trimmed = newFact.trim();
    if (trimmed && !profile.verified_product_facts.includes(trimmed)) {
      setProfile({
        ...profile,
        verified_product_facts: [...profile.verified_product_facts, trimmed]
      });
      setNewFact('');
    }
  };

  const removeFact = (idx: number) => {
    setProfile({
      ...profile,
      verified_product_facts: profile.verified_product_facts.filter((_, i) => i !== idx)
    });
  };

  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-black text-slate-900 tracking-tight flex items-center gap-2">
          <Shield className="w-6 h-6 text-indigo-600" />
          Brand Governance & Voice Guidelines
        </h2>
        <p className="text-sm text-slate-500 mt-1">
          Configure verified product facts, prohibited terms, design palettes, and voice standards enforced across all AI-generated campaign copy and media.
        </p>
      </div>

      {feedback && (
        <div
          className={`p-4 rounded-2xl flex items-center gap-3 border ${
            feedback.type === 'success'
              ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
              : 'bg-rose-50 border-rose-200 text-rose-800'
          }`}
        >
          {feedback.type === 'success' ? (
            <CheckCircle2 className="w-5 h-5 flex-shrink-0 text-emerald-600" />
          ) : (
            <AlertCircle className="w-5 h-5 flex-shrink-0 text-rose-600" />
          )}
          <span className="text-sm font-medium">{feedback.message}</span>
        </div>
      )}

      {loading ? (
        <div className="p-12 text-center text-slate-400 animate-pulse font-medium">Loading brand guidelines...</div>
      ) : (
        <form onSubmit={handleSave} className="space-y-6">
          {/* Identity & Audience */}
          <div className="bg-white border border-slate-200 rounded-3xl p-6 shadow-sm space-y-5">
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-indigo-600" />
              Brand Identity & Target Market
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-bold text-slate-600 uppercase tracking-wider mb-1.5">
                  Brand Name
                </label>
                <input
                  type="text"
                  value={profile.brand_name}
                  onChange={(e) => setProfile({ ...profile, brand_name: e.target.value })}
                  required
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-sm text-slate-900 focus:outline-none focus:border-indigo-500 focus:bg-white transition-all"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-600 uppercase tracking-wider mb-1.5">
                  Default CTA
                </label>
                <input
                  type="text"
                  value={profile.default_cta}
                  onChange={(e) => setProfile({ ...profile, default_cta: e.target.value })}
                  placeholder="e.g. Try it free at domain.com"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-sm text-slate-900 focus:outline-none focus:border-indigo-500 focus:bg-white transition-all"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-600 uppercase tracking-wider mb-1.5">
                Target Audience Persona
              </label>
              <input
                type="text"
                value={profile.target_audience}
                onChange={(e) => setProfile({ ...profile, target_audience: e.target.value })}
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-sm text-slate-900 focus:outline-none focus:border-indigo-500 focus:bg-white transition-all"
              />
            </div>
          </div>

          {/* Tone & Vocabulary */}
          <div className="bg-white border border-slate-200 rounded-3xl p-6 shadow-sm space-y-5">
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <BookOpen className="w-4 h-4 text-emerald-600" />
              Voice, Tone & Vocabulary Standards
            </h3>

            <div>
              <label className="block text-xs font-bold text-slate-600 uppercase tracking-wider mb-1.5">
                Tone of Voice
              </label>
              <input
                type="text"
                value={profile.tone_of_voice}
                onChange={(e) => setProfile({ ...profile, tone_of_voice: e.target.value })}
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-sm text-slate-900 focus:outline-none focus:border-indigo-500 focus:bg-white transition-all"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-600 uppercase tracking-wider mb-1.5">
                Vocabulary Rules & Style Guide
              </label>
              <textarea
                rows={3}
                value={profile.vocabulary_rules || ''}
                onChange={(e) => setProfile({ ...profile, vocabulary_rules: e.target.value })}
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-sm text-slate-900 focus:outline-none focus:border-indigo-500 focus:bg-white transition-all"
                placeholder="Specific writing rules, formatting guidelines, acronym usage..."
              />
            </div>

            {/* Prohibited words */}
            <div>
              <label className="block text-xs font-bold text-rose-700 uppercase tracking-wider mb-1.5 flex items-center gap-1.5">
                <AlertTriangle className="w-3.5 h-3.5 text-rose-600" />
                Prohibited Buzzwords & Blacklisted Terms
              </label>
              <p className="text-xs text-slate-500 mb-2">
                Any asset generated with these terms will fail automated brand compliance checks.
              </p>

              <div className="flex flex-wrap gap-2 mb-3">
                {profile.words_to_avoid.map((word) => (
                  <span
                    key={word}
                    className="inline-flex items-center gap-1.5 px-3 py-1 bg-rose-50 border border-rose-200 text-rose-700 text-xs font-bold rounded-lg"
                  >
                    {word}
                    <button
                      type="button"
                      onClick={() => removeAvoidWord(word)}
                      className="hover:text-rose-900 text-rose-500 font-black ml-0.5"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>

              <div className="flex gap-2">
                <input
                  type="text"
                  value={newAvoidWord}
                  onChange={(e) => setNewAvoidWord(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      addAvoidWord();
                    }
                  }}
                  placeholder="Add blacklisted word (e.g. guru)..."
                  className="bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-sm text-slate-900 focus:outline-none focus:border-rose-500 focus:bg-white flex-1"
                />
                <button
                  type="button"
                  onClick={addAvoidWord}
                  className="px-4 py-2 bg-slate-100 hover:bg-slate-200 border border-slate-200 text-slate-700 rounded-xl text-xs font-bold transition-colors"
                >
                  Add Term
                </button>
              </div>
            </div>
          </div>

          {/* Visual Palette */}
          <div className="bg-white border border-slate-200 rounded-3xl p-6 shadow-sm space-y-5">
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <Palette className="w-4 h-4 text-cyan-600" />
              Brand Card & Carousel Visual Palette
            </h3>
            <p className="text-xs text-slate-500">
              Configures typography accents, gradient headers, and slide indicator colors rendered in MinIO media generation.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="flex items-center gap-4 p-4 bg-slate-50 rounded-2xl border border-slate-200">
                <input
                  type="color"
                  value={profile.primary_color}
                  onChange={(e) => setProfile({ ...profile, primary_color: e.target.value })}
                  className="w-12 h-12 rounded-xl cursor-pointer bg-transparent border-0"
                />
                <div>
                  <div className="text-xs font-bold text-slate-500 uppercase">Primary Accent</div>
                  <div className="text-sm font-mono text-slate-900 uppercase font-bold">{profile.primary_color}</div>
                </div>
                <div
                  className="ml-auto w-10 h-10 rounded-xl border border-black/10 shadow-sm"
                  style={{ backgroundColor: profile.primary_color }}
                />
              </div>

              <div className="flex items-center gap-4 p-4 bg-slate-50 rounded-2xl border border-slate-200">
                <input
                  type="color"
                  value={profile.secondary_color}
                  onChange={(e) => setProfile({ ...profile, secondary_color: e.target.value })}
                  className="w-12 h-12 rounded-xl cursor-pointer bg-transparent border-0"
                />
                <div>
                  <div className="text-xs font-bold text-slate-500 uppercase">Secondary Accent</div>
                  <div className="text-sm font-mono text-slate-900 uppercase font-bold">{profile.secondary_color}</div>
                </div>
                <div
                  className="ml-auto w-10 h-10 rounded-xl border border-black/10 shadow-sm"
                  style={{ backgroundColor: profile.secondary_color }}
                />
              </div>
            </div>
          </div>

          {/* Ground Truth & Verified Claims */}
          <div className="bg-white border border-slate-200 rounded-3xl p-6 shadow-sm space-y-5">
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <Shield className="w-4 h-4 text-amber-600" />
              Ground Truth & Verified Product Claims
            </h3>
            <p className="text-xs text-slate-500">
              Strict factual statements the AI can rely on without hallucinating or inventing claims.
            </p>

            <div className="space-y-2">
              {profile.verified_product_facts.map((fact, idx) => (
                <div
                  key={idx}
                  className="flex items-start justify-between gap-3 p-3.5 bg-slate-50 rounded-xl border border-slate-200 text-xs text-slate-800"
                >
                  <span className="flex-1 leading-relaxed">
                    <span className="text-indigo-600 font-bold mr-2">#{idx + 1}</span>
                    {fact}
                  </span>
                  <button
                    type="button"
                    onClick={() => removeFact(idx)}
                    className="text-slate-400 hover:text-rose-600 text-xs font-bold ml-2"
                  >
                    Delete
                  </button>
                </div>
              ))}
            </div>

            <div className="flex gap-2">
              <input
                type="text"
                value={newFact}
                onChange={(e) => setNewFact(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    addFact();
                  }
                }}
                placeholder="Add verified factual statement (e.g. 99.9% uptime SLA)..."
                className="bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-sm text-slate-900 focus:outline-none focus:border-indigo-500 focus:bg-white flex-1"
              />
              <button
                type="button"
                onClick={addFact}
                className="px-4 py-2 bg-slate-100 hover:bg-slate-200 border border-slate-200 text-slate-700 rounded-xl text-xs font-bold transition-colors"
              >
                Add Fact
              </button>
            </div>
          </div>

          {/* Submit */}
          <div className="flex justify-end pt-2">
            <button
              type="submit"
              disabled={saving}
              className="flex items-center gap-2 px-6 py-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-2xl font-bold text-sm shadow-lg shadow-indigo-600/20 transition-all disabled:opacity-50"
            >
              <Save className="w-4 h-4" />
              {saving ? 'Saving...' : 'Save Brand Guidelines'}
            </button>
          </div>
        </form>
      )}
    </div>
  );
};
