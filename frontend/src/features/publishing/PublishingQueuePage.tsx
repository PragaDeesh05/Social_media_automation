import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Clock, RefreshCw, AlertCircle, CheckCircle2, Play,
  XCircle, ExternalLink, Filter, Loader2, X, Video
} from 'lucide-react';
import { api } from '../../services/api';
import { ScheduledPostItem, PublishingStatus } from '../../types';
import { PlatformBadge } from '../../components/PlatformBadge';
import { FormatBadge } from '../../components/FormatBadge';
import { StatusBadge } from '../../components/StatusBadge';

export const PublishingQueuePage: React.FC = () => {
  const [queue, setQueue] = useState<ScheduledPostItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [filter, setFilter] = useState<string>('all');
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [notice, setNotice] = useState<{
    type: 'success' | 'error' | 'warning';
    message: string;
    url?: string;
    platform?: string;
  } | null>(null);

  const loadQueue = async () => {
    setLoading(true);
    try {
      const data = await api.getPublishingQueue(filter === 'all' ? undefined : filter);
      setQueue(data);
    } catch (err) {
      console.error('Failed to load publishing queue:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadQueue();
  }, [filter]);

  const handlePublishNow = async (postId: string) => {
    setActionLoading(postId);
    setNotice(null);
    try {
      const res = await api.publishNow(postId);
      if (res.success) {
        setNotice({
          type: 'success',
          message: 'Post published successfully!',
          url: res.url
        });
      } else {
        setNotice({
          type: 'error',
          message: res.error || 'Failed to publish post.',
          platform: res.error?.includes('OAuth') ? 'account' : undefined
        });
      }
      await loadQueue();
    } catch (err: any) {
      setNotice({
        type: 'error',
        message: err.response?.data?.detail || err.message || 'Error occurred while publishing.'
      });
    } finally {
      setActionLoading(null);
    }
  };

  const handleRetry = async (postId: string) => {
    setActionLoading(postId);
    setNotice(null);
    try {
      await api.retryPost(postId);
      setNotice({
        type: 'success',
        message: 'Post schedule reset. Queue worker will process this slot in the next run.'
      });
      await loadQueue();
    } catch (err) {
      console.error('Retry failed:', err);
      setNotice({ type: 'error', message: 'Failed to reset post schedule.' });
    } finally {
      setActionLoading(null);
    }
  };

  const handleCancel = async (postId: string) => {
    if (!confirm('Are you sure you want to cancel this scheduled publication?')) return;
    setActionLoading(postId);
    setNotice(null);
    try {
      await api.cancelPost(postId);
      setNotice({ type: 'success', message: 'Scheduled post has been cancelled.' });
      await loadQueue();
    } catch (err) {
      console.error('Cancel failed:', err);
      setNotice({ type: 'error', message: 'Failed to cancel post.' });
    } finally {
      setActionLoading(null);
    }
  };

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-black text-slate-900 tracking-tight">Publishing Queue</h2>
          <p className="text-sm text-slate-500 mt-1">
            Real-time status, atomic lock claims, and bounded retry recovery for scheduled posts.
          </p>
        </div>

        {/* Status Filters */}
        <div className="flex flex-wrap gap-2">
          {['all', 'scheduled', 'publishing', 'published', 'failed', 'cancelled'].map((st) => (
            <button
              key={st}
              onClick={() => setFilter(st)}
              className={`px-3 py-1.5 rounded-xl text-xs font-bold capitalize transition-all ${
                filter === st
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'bg-white border border-slate-200 text-slate-600 hover:text-slate-900'
              }`}
            >
              {st}
            </button>
          ))}
        </div>
      </div>

      {/* Action Notification Banner */}
      {notice && (
        <div
          className={`p-4 rounded-2xl border flex items-start justify-between gap-3 animate-in fade-in duration-200 ${
            notice.type === 'success'
              ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
              : 'bg-rose-50 border-rose-200 text-rose-900'
          }`}
        >
          <div className="flex items-start space-x-3">
            {notice.type === 'success' ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0 mt-0.5" />
            ) : (
              <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
            )}
            <div>
              <p className="text-xs font-bold">{notice.message}</p>
              {notice.url && (
                <a
                  href={notice.url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center space-x-1 text-xs font-bold text-emerald-700 hover:underline mt-1"
                >
                  <span>Open published post</span>
                  <ExternalLink className="w-3.5 h-3.5" />
                </a>
              )}
              {notice.platform === 'account' && (
                <div className="mt-2">
                  <Link
                    to="/connected-accounts"
                    className="inline-flex items-center space-x-1 text-xs font-bold px-3 py-1 bg-rose-600 text-white rounded-lg hover:bg-rose-700 shadow-sm"
                  >
                    <span>Go to Connected Accounts</span>
                  </Link>
                </div>
              )}
            </div>
          </div>
          <button
            type="button"
            onClick={() => setNotice(null)}
            className="text-slate-400 hover:text-slate-600 p-1 rounded-lg"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 text-indigo-600 animate-spin" />
        </div>
      ) : queue.length === 0 ? (
        <div className="bg-white rounded-2xl p-16 text-center border border-slate-200 shadow-sm space-y-3">
          <div className="w-16 h-16 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center mx-auto">
            <Clock className="w-8 h-8" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-slate-900">Publishing Queue is Empty</h3>
            <p className="text-sm text-slate-500 mt-1 max-w-md mx-auto">
              Posts only appear in this queue when you actively schedule them. Use the Content Calendar to schedule posts.
            </p>
          </div>
          <Link
            to="/calendar"
            className="inline-flex items-center space-x-2 bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-2.5 rounded-xl text-sm font-semibold shadow-sm transition"
          >
            <span>Go to Content Calendar</span>
          </Link>
        </div>
      ) : (
        /* Queue Table */
        <div className="bg-white rounded-3xl border border-slate-200/80 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  <th className="py-3.5 px-6">Scheduled Time</th>
                  <th className="py-3.5 px-4">Platform & Format</th>
                  <th className="py-3.5 px-6">Content Hook / Copy</th>
                  <th className="py-3.5 px-4">Status & Retries</th>
                  <th className="py-3.5 px-6 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-xs">
                {queue.map((item) => (
                  <tr key={item.scheduled_post_id} className="hover:bg-slate-50/60 transition-colors">
                    {/* Time */}
                    <td className="py-4 px-6 whitespace-nowrap">
                      <div className="font-bold text-slate-900">
                        {new Date(item.scheduled_utc).toLocaleDateString()}
                      </div>
                      <div className="text-[11px] text-slate-500 flex items-center space-x-1 mt-0.5">
                        <Clock className="w-3 h-3" />
                        <span>{new Date(item.scheduled_utc).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} UTC</span>
                      </div>
                    </td>

                    {/* Platform & Format */}
                    <td className="py-4 px-4 whitespace-nowrap">
                      <div className="space-y-1">
                        <div><PlatformBadge platform={item.platform} size="sm" /></div>
                        <div><FormatBadge format={item.format} /></div>
                      </div>
                    </td>

                    {/* Content Hook / Copy */}
                    <td className="py-4 px-6 max-w-md">
                      <div className="font-bold text-slate-900 line-clamp-1">{item.hook}</div>
                      <div className="text-slate-500 line-clamp-2 mt-0.5">{item.caption}</div>
                      {item.last_error && (
                        <div className="mt-1.5 p-2 rounded-lg bg-red-50 text-red-700 text-[11px] font-mono border border-red-100">
                          {item.last_error}
                        </div>
                      )}
                    </td>

                    {/* Status */}
                    <td className="py-4 px-4 whitespace-nowrap">
                      <div className="space-y-1">
                        <div><StatusBadge status={item.status} /></div>
                        <div className="text-[10px] text-slate-400 font-mono">
                          Retries: {item.retry_count}/{item.max_retries}
                        </div>
                      </div>
                    </td>

                    {/* Actions */}
                    <td className="py-4 px-6 text-right whitespace-nowrap">
                      <div className="flex items-center justify-end space-x-2">
                        {item.published_post_url ? (
                          <a
                            href={item.published_post_url}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center space-x-1.5 text-xs font-bold text-emerald-700 hover:text-emerald-800 border border-emerald-300 bg-emerald-50 px-3 py-1.5 rounded-xl shadow-sm hover:shadow transition-all"
                          >
                            <ExternalLink className="w-3.5 h-3.5" />
                            <span>Live Post</span>
                          </a>
                        ) : (
                          <>
                            {item.status !== 'published' && (
                              <button
                                type="button"
                                disabled={actionLoading === item.scheduled_post_id}
                                onClick={() => handlePublishNow(item.scheduled_post_id)}
                                className="inline-flex items-center space-x-1 text-xs font-bold text-indigo-600 hover:text-indigo-700 border border-indigo-200 bg-indigo-50 px-3 py-1.5 rounded-xl disabled:opacity-50"
                              >
                                <Play className="w-3 h-3" />
                                <span>Publish Now</span>
                              </button>
                            )}

                            {item.status === 'failed' && (
                              <button
                                type="button"
                                disabled={actionLoading === item.scheduled_post_id}
                                onClick={() => handleRetry(item.scheduled_post_id)}
                                className="inline-flex items-center space-x-1 text-xs font-bold text-amber-600 hover:text-amber-700 border border-amber-200 bg-amber-50 px-3 py-1.5 rounded-xl disabled:opacity-50"
                              >
                                <RefreshCw className="w-3 h-3" />
                                <span>Retry</span>
                              </button>
                            )}

                            {item.status === 'scheduled' && (
                              <button
                                type="button"
                                disabled={actionLoading === item.scheduled_post_id}
                                onClick={() => handleCancel(item.scheduled_post_id)}
                                className="text-slate-400 hover:text-red-500 p-1.5"
                                title="Cancel Scheduled Post"
                              >
                                <XCircle className="w-4 h-4" />
                              </button>
                            )}
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
