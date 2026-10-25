import React, { useEffect, useState } from 'react';
import {
  Image as ImageIcon, Video, Layers, Download, ExternalLink,
  Eye, Search, Loader2, Play
} from 'lucide-react';
import { api } from '../../services/api';
import { PlatformBadge } from '../../components/PlatformBadge';
import { FormatBadge } from '../../components/FormatBadge';

export const MediaLibraryPage: React.FC = () => {
  const [mediaItems, setMediaItems] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [filterType, setFilterType] = useState<string>('all');
  const [search, setSearch] = useState<string>('');
  const [previewModal, setPreviewModal] = useState<any | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  const downloadMediaItem = async (item: any) => {
    if (!item) return;
    setDownloadingId(item.id);
    const filename = item.file_name || 'download';
    const targetUrl = item.stream_url || item.presigned_url || `/api/v1/media/stream?key=${encodeURIComponent(item.minio_object_key || item.file_name)}`;

    try {
      const resp = await fetch(targetUrl);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const blob = await resp.blob();
      const blobUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = blobUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(blobUrl);
    } catch (err) {
      console.warn('Direct blob fetch failed, falling back to download stream endpoint:', err);
      const dlUrl = `/api/v1/media/stream?key=${encodeURIComponent(item.minio_object_key || '')}&download=1&filename=${encodeURIComponent(filename)}`;
      window.open(dlUrl, '_blank');
    } finally {
      setDownloadingId(null);
    }
  };

  const loadMedia = async () => {
    setLoading(true);
    try {
      const data = await api.listMedia({
        media_type: filterType === 'all' ? undefined : filterType,
      });
      setMediaItems(data);
    } catch (err) {
      console.error('Failed to load media:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadMedia();
  }, [filterType]);

  const filtered = mediaItems.filter((m) => {
    if (search && !m.file_name.toLowerCase().includes(search.toLowerCase())) {
      return false;
    }
    return true;
  });

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-black text-slate-900 tracking-tight">MinIO Object Storage Library</h2>
          <p className="text-sm text-slate-500 mt-1">
            Authenticated S3-compatible media assets: final graphics, 5-slide carousels, and &le;60s vertical videos.
          </p>
        </div>

        {/* Filter controls */}
        <div className="flex items-center space-x-3">
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-3 top-3 text-slate-400" />
            <input
              type="text"
              placeholder="Search filename..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-8 pr-3 py-1.5 rounded-xl border border-slate-200 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500 w-44"
            />
          </div>

          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="px-3 py-1.5 rounded-xl border border-slate-200 text-xs font-medium text-slate-700 bg-white"
          >
            <option value="all">All Media</option>
            <option value="image">Posters & Brand Graphics</option>
            <option value="carousel_slide">Carousel Slides</option>
            <option value="video">Short Videos</option>
          </select>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 text-indigo-600 animate-spin" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="bg-white rounded-2xl p-16 text-center border border-slate-200 shadow-sm space-y-3">
          <div className="w-16 h-16 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center mx-auto">
            <ImageIcon className="w-8 h-8" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-slate-900">Media Library is Empty</h3>
            <p className="text-sm text-slate-500 mt-1 max-w-md mx-auto">
              Media files only appear here when you create videos, carousels, or posters, or upload assets to the Content Calendar.
            </p>
          </div>
        </div>
      ) : (
        /* Media Grid */
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
          {filtered.map((item) => {
            const isVideo = item.media_type === 'video';
            const primaryUrl = item.fallback_url || item.stream_url || item.presigned_url;
            return (
              <div
                key={item.id}
                className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden flex flex-col justify-between group hover:shadow-md transition-all"
              >
                {/* Visual Thumbnail */}
                <div
                  onClick={() => setPreviewModal(item)}
                  className="bg-slate-800 aspect-square relative cursor-pointer overflow-hidden flex items-center justify-center"
                >
                  {isVideo ? (
                    <div className="relative w-full h-full flex items-center justify-center bg-slate-800">
                      <div className="w-12 h-12 rounded-full bg-indigo-600/90 text-white flex items-center justify-center group-hover:scale-110 transition-transform shadow-lg">
                        <Play className="w-5 h-5 ml-0.5" />
                      </div>
                      <span className="absolute bottom-2 right-2 bg-slate-900/80 text-white text-[10px] px-2 py-0.5 rounded font-mono">
                        {item.duration_seconds || '15'}s
                      </span>
                    </div>
                  ) : (
                    <img
                      src={primaryUrl}
                      alt={item.file_name}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                      onError={(e) => {
                        const target = e.currentTarget;
                        if (!target.dataset.triedFallback) {
                          target.dataset.triedFallback = '1';
                          target.src = item.stream_url || `/api/v1/media/stream?key=${encodeURIComponent(item.minio_object_key)}`;
                        } else if (target.dataset.triedFallback === '1') {
                          target.dataset.triedFallback = '2';
                          target.src = `/media/graphics/${item.file_name}`;
                        }
                      }}
                    />
                  )}
                  <div className="absolute top-2 left-2">
                    <PlatformBadge platform={item.platform} size="sm" />
                  </div>
                </div>

                {/* Details Footer */}
                <div className="p-4 space-y-2">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-bold text-slate-900 truncate max-w-[140px]">{item.file_name}</span>
                    <FormatBadge format={item.format} />
                  </div>
                  <div className="text-[11px] text-slate-400 font-mono flex items-center justify-between">
                    <span>{(item.file_size_bytes / 1024).toFixed(1)} KB</span>
                    {item.width && <span>{item.width}x{item.height}</span>}
                  </div>
                  <div className="pt-2 border-t border-slate-100 flex items-center justify-between">
                    <button
                      type="button"
                      onClick={() => setPreviewModal(item)}
                      className="text-xs font-semibold text-slate-600 hover:text-indigo-600 flex items-center space-x-1 cursor-pointer"
                    >
                      <Eye className="w-3.5 h-3.5" />
                      <span>Preview</span>
                    </button>
                    <button
                      type="button"
                      disabled={downloadingId === item.id}
                      onClick={() => downloadMediaItem(item)}
                      className="text-xs font-semibold text-indigo-600 hover:text-indigo-700 flex items-center space-x-1 cursor-pointer disabled:opacity-50"
                    >
                      <Download className="w-3.5 h-3.5" />
                      <span>{downloadingId === item.id ? 'Saving...' : 'Download'}</span>
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Media Preview Modal */}
      {previewModal && (
        <div
          onClick={() => setPreviewModal(null)}
          className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4 z-50"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="bg-white rounded-2xl p-6 max-w-2xl w-full shadow-2xl border border-slate-200 space-y-4"
          >
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-slate-900">{previewModal.file_name}</h3>
                <p className="text-xs text-slate-500 font-mono">{previewModal.minio_object_key}</p>
              </div>
              <button
                type="button"
                onClick={() => setPreviewModal(null)}
                className="text-xs font-bold text-slate-400 hover:text-slate-700 p-2 cursor-pointer"
              >
                ✕
              </button>
            </div>

            <div className="bg-slate-800 rounded-2xl overflow-hidden flex items-center justify-center max-h-[500px]">
              {previewModal.media_type === 'video' ? (
                <video src={previewModal.stream_url || previewModal.presigned_url} controls className="max-h-[500px] w-auto" />
              ) : (
                <img
                  src={previewModal.fallback_url || previewModal.stream_url || previewModal.presigned_url}
                  alt="Full preview"
                  className="max-h-[500px] w-auto object-contain"
                  onError={(e) => {
                    const target = e.currentTarget;
                    if (!target.dataset.tried) {
                      target.dataset.tried = '1';
                      target.src = `/api/v1/media/stream?key=${encodeURIComponent(previewModal.minio_object_key)}`;
                    } else if (target.dataset.tried === '1') {
                      target.dataset.tried = '2';
                      target.src = `/media/graphics/${previewModal.file_name}`;
                    }
                  }}
                />
              )}
            </div>

            <div className="flex items-center justify-between pt-2">
              <span className="text-xs text-slate-500 font-mono">
                MinIO Bucket: incubrix-assets
              </span>
              <button
                type="button"
                disabled={downloadingId === previewModal.id}
                onClick={() => downloadMediaItem(previewModal)}
                className="inline-flex items-center space-x-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold px-4 py-2 rounded-xl transition-colors cursor-pointer disabled:opacity-50 shadow-sm"
              >
                <Download className="w-3.5 h-3.5" />
                <span>{downloadingId === previewModal.id ? 'Downloading...' : 'Save to Disk'}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
