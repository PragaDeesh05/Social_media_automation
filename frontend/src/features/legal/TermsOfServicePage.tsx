import React from 'react';
import { Link } from 'react-router-dom';
import { FileText, ArrowLeft, ExternalLink } from 'lucide-react';

export const TermsOfServicePage: React.FC = () => {
  return (
    <div className="max-w-4xl mx-auto py-12 px-6 space-y-8 bg-white min-h-screen">
      <Link
        to="/"
        className="inline-flex items-center space-x-2 text-xs font-bold text-indigo-600 hover:text-indigo-800"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Back to IncuBrix Dashboard</span>
      </Link>

      <div className="border-b border-slate-200 pb-6">
        <div className="flex items-center space-x-3">
          <div className="p-3 bg-indigo-50 text-indigo-600 rounded-2xl">
            <FileText className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-3xl font-black text-slate-900 tracking-tight">Terms of Service</h1>
            <p className="text-xs text-slate-500 mt-1">Last updated: October 24, 2026</p>
          </div>
        </div>
      </div>

      <div className="prose prose-slate max-w-none text-sm space-y-6 text-slate-700 leading-relaxed">
        <section className="space-y-2">
          <h2 className="text-lg font-bold text-slate-900">1. Acceptance of Terms</h2>
          <p>
            By accessing or using the IncuBrix Social Media Automation Engine ("IncuBrix"), you agree to comply with
            and be bound by these Terms of Service. If you do not agree, do not access or use our services.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-bold text-slate-900">2. YouTube API Services Agreement</h2>
          <div className="p-4 bg-indigo-50/80 border border-indigo-200 rounded-2xl text-xs text-indigo-900 space-y-2">
            <p className="font-bold">YouTube API Compliance:</p>
            <p>
              IncuBrix connects to official YouTube APIs to publish video content on your behalf. By utilizing our YouTube integration, you acknowledge and agree that your usage is subject to the{' '}
              <a
                href="https://www.youtube.com/t/terms"
                target="_blank"
                rel="noreferrer"
                className="font-bold underline text-indigo-950 inline-flex items-center"
              >
                YouTube Terms of Service <ExternalLink className="w-3 h-3 ml-0.5 inline" />
              </a>.
            </p>
          </div>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-bold text-slate-900">3. User Responsibilities & Content Standards</h2>
          <p>You agree that you will not upload, generate, or publish content that:</p>
          <ul className="list-disc pl-6 space-y-1">
            <li>Infringes on the intellectual property, copyright, or trademark rights of any third party.</li>
            <li>Violates YouTube Community Guidelines, spam policies, or copyright strikes.</li>
            <li>Contains malicious code, deceptive spam, or automated bot abuse.</li>
          </ul>
          <p>
            You retain 100% ownership of all source materials uploaded and media generated through your IncuBrix account.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-bold text-slate-900">4. Third-Party Platform Access and Rate Limits</h2>
          <p>
            Publishing schedules and uploads are subject to official third-party API quotas and limits enforced by YouTube, Meta, and X. IncuBrix employs exponential backoff and rate-limiting algorithms to comply with all provider quotas.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-bold text-slate-900">5. Termination</h2>
          <p>
            You may discontinue use of IncuBrix at any time. We reserve the right to suspend or terminate access to users who violate these Terms or provider API policies.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-bold text-slate-900">6. Contact Us</h2>
          <p>
            For questions regarding these Terms, contact our legal team at{' '}
            <a href="mailto:legal@incubrix.com" className="font-bold text-indigo-600 underline">
              legal@incubrix.com
            </a>.
          </p>
        </section>
      </div>
    </div>
  );
};
