import React from 'react';
import { Link } from 'react-router-dom';
import { Shield, ArrowLeft, ExternalLink } from 'lucide-react';

export const PrivacyPolicyPage: React.FC = () => {
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
            <Shield className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-3xl font-black text-slate-900 tracking-tight">Privacy Policy</h1>
            <p className="text-xs text-slate-500 mt-1">Last updated: October 24, 2026</p>
          </div>
        </div>
      </div>

      <div className="prose prose-slate max-w-none text-sm space-y-6 text-slate-700 leading-relaxed">
        <section className="space-y-2">
          <h2 className="text-lg font-bold text-slate-900">1. Overview</h2>
          <p>
            IncuBrix Social Media Automation Engine ("IncuBrix", "we", "our", or "us") provides AI-powered content
            repurposing, social calendar scheduling, and automated media publishing across supported platforms
            including YouTube, Facebook, Instagram, and X.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-bold text-slate-900">2. YouTube API Services Notice & Disclosures</h2>
          <div className="p-4 bg-amber-50/80 border border-amber-200 rounded-2xl text-xs text-amber-900 space-y-2">
            <p className="font-bold">Important Notice Regarding YouTube API Services:</p>
            <p>
              IncuBrix uses official <strong>YouTube API Services</strong> to schedule, upload, and publish video content to
              authorized YouTube channels. By using IncuBrix to connect and publish to YouTube, you agree to be bound
              by the{' '}
              <a
                href="https://www.youtube.com/t/terms"
                target="_blank"
                rel="noreferrer"
                className="font-bold underline text-amber-950 inline-flex items-center"
              >
                YouTube Terms of Service <ExternalLink className="w-3 h-3 ml-0.5 inline" />
              </a>{' '}
              and the{' '}
              <a
                href="https://policies.google.com/privacy"
                target="_blank"
                rel="noreferrer"
                className="font-bold underline text-amber-950 inline-flex items-center"
              >
                Google Privacy Policy <ExternalLink className="w-3 h-3 ml-0.5 inline" />
              </a>.
            </p>
          </div>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-bold text-slate-900">3. Data We Collect and Use</h2>
          <p>When you connect your YouTube or social media accounts, IncuBrix accesses and processes:</p>
          <ul className="list-disc pl-6 space-y-1">
            <li><strong>Channel Information:</strong> Channel ID, channel title, handle, and avatar URL to identify destination publishing channels.</li>
            <li><strong>Authentication Tokens:</strong> OAuth 2.0 access tokens and refresh tokens required to perform authorized video uploads on your behalf.</li>
            <li><strong>Uploaded & Generated Media:</strong> User-provided source documents, generated scripts, subtitles, images, and rendered MP4 video files stored in isolated S3 object storage (MinIO).</li>
            <li><strong>Publication Metadata:</strong> Video IDs, publication timestamps, and status metrics returned by the YouTube Data API.</li>
          </ul>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-bold text-slate-900">4. How We Protect and Store Your Data</h2>
          <p>
            All OAuth access and refresh tokens are encrypted at rest using industry-standard <strong>AES-256-GCM authenticated encryption</strong> before storage in PostgreSQL. Encryption keys are securely managed via backend environment variables and are never exposed to the frontend browser or external third parties.
          </p>
          <p>
            IncuBrix does not sell, trade, or rent user data or Google user credentials to any third-party advertisers, data brokers, or AI model providers.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-bold text-slate-900">5. Revocation and Deletion of Access</h2>
          <p>
            You can revoke IncuBrix's access to your YouTube and Google account at any time:
          </p>
          <ul className="list-disc pl-6 space-y-1">
            <li>
              <strong>Directly inside IncuBrix:</strong> Navigate to the <em>Connected Accounts</em> page and click <em>Disconnect</em> on your YouTube channel. This immediately wipes your stored OAuth credentials from our database.
            </li>
            <li>
              <strong>Via Google Account Settings:</strong> You can revoke access directly through Google's official security portal at{' '}
              <a
                href="https://myaccount.google.com/permissions"
                target="_blank"
                rel="noreferrer"
                className="font-bold text-indigo-600 underline inline-flex items-center"
              >
                https://myaccount.google.com/permissions <ExternalLink className="w-3 h-3 ml-0.5 inline" />
              </a>.
            </li>
          </ul>
        </section>

        <section className="space-y-2">
          <h2 className="text-lg font-bold text-slate-900">6. Contact Information</h2>
          <p>
            If you have questions regarding this Privacy Policy or wish to request data deletion, contact us at{' '}
            <a href="mailto:privacy@incubrix.com" className="font-bold text-indigo-600 underline">
              privacy@incubrix.com
            </a>.
          </p>
        </section>
      </div>
    </div>
  );
};
