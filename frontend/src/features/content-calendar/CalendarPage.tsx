import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Calendar as CalendarIcon, Clock, ChevronLeft, ChevronRight,
  Filter, Edit, ExternalLink, Loader2, Sparkles, Check, Layers, Video,
  Plus, Upload, Trash2, AlertCircle, RefreshCw, List, Grid, CheckCircle2
} from 'lucide-react';
import { api } from '../../services/api';
import { ScheduledPostItem, Campaign, Platform } from '../../types';
import { PlatformBadge } from '../../components/PlatformBadge';
import { FormatBadge } from '../../components/FormatBadge';
import { StatusBadge } from '../../components/StatusBadge';

export const CalendarPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialCampaignId = searchParams.get('campaign_id') || '';

  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [selectedCampaignId, setSelectedCampaignId] = useState<string>(initialCampaignId);
  const [slots, setSlots] = useState<ScheduledPostItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  // View mode: 'month' | 'list'
  const [viewMode, setViewMode] = useState<'month' | 'list'>('month');

  // Filters & Search
  const [selectedPlatform, setSelectedPlatform] = useState<string>('all');
  const [selectedFormat, setSelectedFormat] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Reschedule Modal
  const [rescheduleModal, setRescheduleModal] = useState<ScheduledPostItem | null>(null);
  const [newDateTime, setNewDateTime] = useState<string>('');
  const [savingReschedule, setSavingReschedule] = useState<boolean>(false);

  // Edit Post Modal
  const [editModal, setEditModal] = useState<ScheduledPostItem | null>(null);
  const [editTitle, setEditTitle] = useState<string>('');
  const [editCaption, setEditCaption] = useState<string>('');
  const [savingEdit, setSavingEdit] = useState<boolean>(false);

  // + Add Content Modal State
  const [isAddContentOpen, setIsAddContentOpen] = useState<boolean>(false);
  const [manualTitle, setManualTitle] = useState<string>('');
  const [manualCaption, setManualCaption] = useState<string>('');
  const [manualHashtags, setManualHashtags] = useState<string>('');
  const [manualCta, setManualCta] = useState<string>('Learn more');
  const [manualPlatforms, setManualPlatforms] = useState<string[]>(['instagram', 'facebook']);
  const [manualFormatMap, setManualFormatMap] = useState<Record<string, string>>({
    instagram: 'image',
    facebook: 'image',
    youtube: 'short_video',
  });
  const [manualDate, setManualDate] = useState<string>(() => {
    const d = new Date(Date.now() + 86400000);
    return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  });
  const [manualTimezone, setManualTimezone] = useState<string>('UTC');
  const [manualFiles, setManualFiles] = useState<File[]>([]);
  const [manualPreviewUrls, setManualPreviewUrls] = useState<string[]>([]);
  const [manualIsDraft, setManualIsDraft] = useState<boolean>(false);
  const [submittingManual, setSubmittingManual] = useState<boolean>(false);
  const [manualError, setManualError] = useState<string>('');
  const [previewPlatformTab, setPreviewPlatformTab] = useState<string>('instagram');

  useEffect(() => {
    loadCampaigns();
  }, []);

  useEffect(() => {
    loadSlots();
  }, [selectedCampaignId]);

  const loadCampaigns = async () => {
    try {
      const data = await api.listCampaigns();
      setCampaigns(data);
      if (!selectedCampaignId) {
        setSelectedCampaignId('all');
      }
    } catch (err) {
      console.error('Failed to load campaigns:', err);
    }
  };

  const loadSlots = async () => {
    setLoading(true);
    try {
      const params = selectedCampaignId && selectedCampaignId !== 'all' ? { campaign_id: selectedCampaignId } : undefined;
      const data = await api.getCalendarSlots(params);
      setSlots(data || []);
    } catch (err) {
      console.error('Failed to load calendar slots:', err);
      setSlots([]);
    } finally {
      setLoading(false);
    }
  };

  const handleOpenReschedule = (post: ScheduledPostItem) => {
    setRescheduleModal(post);
    try {
      const dt = new Date(post.scheduled_utc);
      const isoString = new Date(dt.getTime() - dt.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
      setNewDateTime(isoString);
    } catch {
      setNewDateTime(new Date().toISOString().slice(0, 16));
    }
  };

  const handleSaveReschedule = async () => {
    if (!rescheduleModal || !newDateTime) return;
    setSavingReschedule(true);
    try {
      const isoUtc = new Date(newDateTime).toISOString();
      await api.rescheduleSlot(rescheduleModal.scheduled_post_id, {
        scheduled_utc: isoUtc,
      });
      setRescheduleModal(null);
      await loadSlots();
    } catch (err) {
      console.error('Reschedule failed:', err);
    } finally {
      setSavingReschedule(false);
    }
  };

  const handleOpenEdit = (post: ScheduledPostItem) => {
    setEditModal(post);
    setEditTitle(post.hook || '');
    setEditCaption(post.caption || '');
  };

  const handleSaveEdit = async () => {
    if (!editModal) return;
    setSavingEdit(true);
    try {
      await api.updateCalendarPost(editModal.scheduled_post_id, {
        title: editTitle,
        caption: editCaption,
      });
      setEditModal(null);
      await loadSlots();
    } catch (err) {
      console.error('Update post failed:', err);
    } finally {
      setSavingEdit(false);
    }
  };

  const handleDeletePost = async (postId: string) => {
    if (!window.confirm('Delete this scheduled post from the calendar?')) return;
    try {
      await api.deleteCalendarPost(postId);
      await loadSlots();
    } catch (err) {
      console.error('Delete failed:', err);
    }
  };

  // Handle file uploads in Manual Content Modal
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const filesArray = Array.from(e.target.files);
      setManualFiles(filesArray);

      const urls = filesArray.map((f) => URL.createObjectURL(f));
      setManualPreviewUrls(urls);

      // Auto adjust format mapping
      const first = filesArray[0];
      const isVid = first.type.startsWith('video/');
      const isMulti = filesArray.length > 1;

      setManualFormatMap((prev) => ({
        ...prev,
        instagram: isVid ? 'short_video' : isMulti ? 'carousel' : 'image',
        facebook: isVid ? 'short_video' : isMulti ? 'carousel' : 'image',
        youtube: 'short_video',
      }));
    }
  };

  const togglePlatform = (p: string) => {
    if (manualPlatforms.includes(p)) {
      if (manualPlatforms.length > 1) {
        const next = manualPlatforms.filter((item) => item !== p);
        setManualPlatforms(next);
        if (previewPlatformTab === p) setPreviewPlatformTab(next[0]);
      }
    } else {
      setManualPlatforms([...manualPlatforms, p]);
    }
  };

  // Submit Manual Content
  const handleSaveManualContent = async () => {
    if (!manualTitle.trim()) {
      setManualError('Please provide a post title or hook.');
      return;
    }
    if (!manualCaption.trim()) {
      setManualError('Please provide post caption copy.');
      return;
    }
    if (manualPlatforms.length === 0) {
      setManualError('Please select at least one publishing platform.');
      return;
    }

    setSubmittingManual(true);
    setManualError('');

    try {
      const formData = new FormData();
      formData.append('title', manualTitle);
      formData.append('caption', manualCaption);
      formData.append('platforms', JSON.stringify(manualPlatforms));
      formData.append('formats', JSON.stringify(manualFormatMap));
      formData.append('hashtags', manualHashtags);
      formData.append('cta', manualCta);
      formData.append('scheduled_utc', new Date(manualDate).toISOString());
      formData.append('timezone_name', manualTimezone);
      formData.append('is_draft', String(manualIsDraft));
      if (selectedCampaignId) {
        formData.append('campaign_id', selectedCampaignId);
      }

      for (const file of manualFiles) {
        formData.append('files', file);
      }

      await api.scheduleManualContent(formData);
      setIsAddContentOpen(false);
      // Reset form
      setManualTitle('');
      setManualCaption('');
      setManualFiles([]);
      setManualPreviewUrls([]);
      await loadSlots();
    } catch (err: any) {
      console.error('Failed to create manual content:', err);
      setManualError(err.response?.data?.detail || 'Failed to schedule content.');
    } finally {
      setSubmittingManual(false);
    }
  };

  // Filter slots
  const filteredSlots = slots.filter((slot) => {
    const matchesPlatform = selectedPlatform === 'all' || slot.platform.toLowerCase() === selectedPlatform.toLowerCase();
    const matchesFormat = selectedFormat === 'all' || slot.format.toLowerCase() === selectedFormat.toLowerCase();
    const matchesSearch =
      !searchQuery ||
      (slot.hook || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
      (slot.caption || '').toLowerCase().includes(searchQuery.toLowerCase());
    return matchesPlatform && matchesFormat && matchesSearch;
  });

  // Group scheduled slots by day for calendar grid
  const groupedByDay: { [day: number]: ScheduledPostItem[] } = {};
  for (let i = 1; i <= 30; i++) groupedByDay[i] = [];
  filteredSlots.forEach((slot) => {
    const d = slot.day_number || 1;
    if (!groupedByDay[d]) groupedByDay[d] = [];
    groupedByDay[d].push(slot);
  });

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-slate-200">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center space-x-2">
            <CalendarIcon className="w-6 h-6 text-indigo-600" />
            <span>Content Calendar</span>
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Real-time schedule of your queued posts across YouTube, Facebook, and Instagram.
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex items-center space-x-3">
          <button
            onClick={() => setIsAddContentOpen(true)}
            className="inline-flex items-center space-x-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-xl text-sm font-semibold shadow-sm transition"
          >
            <Plus className="w-4 h-4" />
            <span>+ Add Content</span>
          </button>
        </div>
      </div>

      {/* Filter and View Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex flex-col md:flex-row gap-4 items-center justify-between">
        <div className="flex flex-wrap items-center gap-3 w-full md:w-auto">
          {/* Campaign Selector */}
          {campaigns.length > 0 && (
            <select
              value={selectedCampaignId}
              onChange={(e) => setSelectedCampaignId(e.target.value)}
              className="px-3 py-1.5 border border-slate-200 rounded-lg text-xs bg-white text-slate-700 font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value="all">All Campaigns</option>
              {campaigns.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          )}

          {/* Platform Filter */}
          <select
            value={selectedPlatform}
            onChange={(e) => setSelectedPlatform(e.target.value)}
            className="px-3 py-1.5 border border-slate-200 rounded-lg text-xs bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="all">All Platforms</option>
            <option value="youtube">YouTube</option>
            <option value="facebook">Facebook</option>
            <option value="instagram">Instagram</option>
          </select>

          {/* Format Filter */}
          <select
            value={selectedFormat}
            onChange={(e) => setSelectedFormat(e.target.value)}
            className="px-3 py-1.5 border border-slate-200 rounded-lg text-xs bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="all">All Formats</option>
            <option value="short_video">Videos & Shorts</option>
            <option value="carousel">Carousels</option>
            <option value="image">Posters & Images</option>
            <option value="text">Text Posts</option>
          </select>

          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search posts..."
            className="px-3 py-1.5 border border-slate-200 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500 w-48"
          />
        </div>

        {/* View Toggle */}
        <div className="flex items-center space-x-2">
          <div className="inline-flex bg-slate-100 p-1 rounded-lg border border-slate-200">
            <button
              onClick={() => setViewMode('month')}
              className={`px-3 py-1 rounded text-xs font-medium transition flex items-center space-x-1 ${
                viewMode === 'month' ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-600'
              }`}
            >
              <Grid className="w-3.5 h-3.5" />
              <span>30-Day Grid</span>
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={`px-3 py-1 rounded text-xs font-medium transition flex items-center space-x-1 ${
                viewMode === 'list' ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-600'
              }`}
            >
              <List className="w-3.5 h-3.5" />
              <span>Detailed List</span>
            </button>
          </div>

          <button
            onClick={loadSlots}
            className="p-1.5 border border-slate-200 text-slate-600 hover:text-slate-900 rounded-lg hover:bg-slate-50 transition"
            title="Refresh Slots"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      {loading ? (
        <div className="h-64 flex items-center justify-center bg-white rounded-xl border border-slate-200">
          <Loader2 className="w-6 h-6 text-indigo-600 animate-spin" />
        </div>
      ) : slots.length === 0 ? (
        /* Clean Zero State */
        <div className="bg-white rounded-2xl border border-slate-200 p-16 text-center shadow-sm space-y-4">
          <div className="w-16 h-16 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center mx-auto">
            <CalendarIcon className="w-8 h-8" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-slate-900">No Scheduled Posts in Calendar</h3>
            <p className="text-sm text-slate-500 mt-1 max-w-md mx-auto">
              Posts will only display here when you schedule them. Click below to upload and schedule your first post.
            </p>
          </div>
          <button
            onClick={() => setIsAddContentOpen(true)}
            className="inline-flex items-center space-x-2 bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-2.5 rounded-xl text-sm font-semibold shadow-sm transition"
          >
            <Plus className="w-4 h-4" />
            <span>+ Add Content Now</span>
          </button>
        </div>
      ) : viewMode === 'list' ? (
        /* LIST VIEW */
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-500 uppercase tracking-wider font-semibold border-b border-slate-200">
                <tr>
                  <th className="py-3 px-4">Day & Time</th>
                  <th className="py-3 px-4">Platform & Format</th>
                  <th className="py-3 px-4">Preview</th>
                  <th className="py-3 px-4">Headline / Caption</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredSlots.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-12 text-center text-slate-400">
                      No scheduled posts match your filters.
                    </td>
                  </tr>
                ) : (
                  filteredSlots.map((slot) => (
                    <tr key={slot.scheduled_post_id} className="hover:bg-slate-50/70 transition">
                      <td className="py-3 px-4 whitespace-nowrap">
                        <div className="font-bold text-slate-900">Day {slot.day_number || 1}</div>
                        <div className="text-[11px] text-slate-500 font-mono flex items-center space-x-1 mt-0.5">
                          <Clock className="w-3 h-3 text-slate-400" />
                          <span>
                            {new Date(slot.scheduled_utc).toLocaleDateString([], { month: 'short', day: 'numeric' })}{' '}
                            {new Date(slot.scheduled_utc).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </span>
                        </div>
                      </td>

                      <td className="py-3 px-4 whitespace-nowrap">
                        <div className="flex items-center space-x-1.5">
                          <PlatformBadge platform={slot.platform as Platform} />
                          <FormatBadge format={slot.format} />
                        </div>
                      </td>

                      <td className="py-3 px-4">
                        <div className="w-12 h-12 rounded-lg bg-slate-800 overflow-hidden flex items-center justify-center shrink-0 border border-slate-200">
                          {slot.preview_url ? (
                            ['short_video', 'reel', 'shorts'].includes(slot.format.toLowerCase()) ? (
                              <video src={slot.preview_url} className="w-full h-full object-cover" />
                            ) : (
                              <img src={slot.preview_url} alt="" className="w-full h-full object-cover" />
                            )
                          ) : (
                            <span className="text-[10px] text-slate-400 font-mono">N/A</span>
                          )}
                        </div>
                      </td>

                      <td className="py-3 px-4 max-w-md">
                        <div className="font-semibold text-slate-900 line-clamp-1">{slot.hook}</div>
                        <div className="text-slate-500 text-[11px] line-clamp-2 mt-0.5">{slot.caption}</div>
                      </td>

                      <td className="py-3 px-4 whitespace-nowrap">
                        <StatusBadge status={slot.status || 'scheduled'} />
                      </td>

                      <td className="py-3 px-4 text-right whitespace-nowrap">
                        <div className="inline-flex items-center space-x-2">
                          <button
                            onClick={() => handleOpenEdit(slot)}
                            className="p-1 text-slate-500 hover:text-indigo-600 rounded transition"
                            title="Edit Post"
                          >
                            <Edit className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleOpenReschedule(slot)}
                            className="p-1 text-slate-500 hover:text-indigo-600 rounded transition"
                            title="Reschedule"
                          >
                            <Clock className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleDeletePost(slot.scheduled_post_id)}
                            className="p-1 text-slate-500 hover:text-rose-600 rounded transition"
                            title="Delete Slot"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        /* 30-DAY CALENDAR GRID VIEW */
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
          {Array.from({ length: 30 }, (_, i) => i + 1).map((dayNum) => {
            const daySlots = groupedByDay[dayNum] || [];
            return (
              <div
                key={dayNum}
                className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 flex flex-col justify-between min-h-[200px]"
              >
                <div>
                  <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-100">
                    <span className="font-bold text-slate-900 text-sm">Day {dayNum}</span>
                    <span className={`text-[10px] font-mono px-2 py-0.5 rounded ${daySlots.length > 0 ? 'bg-indigo-50 text-indigo-700 font-bold' : 'text-slate-400 bg-slate-50'}`}>
                      {daySlots.length} {daySlots.length === 1 ? 'post' : 'posts'}
                    </span>
                  </div>

                  {daySlots.length === 0 ? (
                    <div className="py-6 text-center text-[11px] text-slate-400 italic">
                      No post scheduled
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {daySlots.map((slot) => (
                        <div
                          key={slot.scheduled_post_id}
                          className="p-2 bg-slate-50 rounded-lg border border-slate-200 text-xs space-y-1 hover:border-indigo-300 transition"
                        >
                          <div className="flex items-center justify-between">
                            <PlatformBadge platform={slot.platform as Platform} />
                            <span className="text-[10px] font-mono text-slate-500">
                              {new Date(slot.scheduled_utc).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            </span>
                          </div>
                          <p className="font-semibold text-slate-800 line-clamp-1">{slot.hook}</p>

                          <div className="pt-1 flex items-center justify-between border-t border-slate-100 text-[10px]">
                            <span className="text-slate-400 capitalize">{slot.format}</span>
                            <button
                              onClick={() => handleOpenReschedule(slot)}
                              className="text-indigo-600 hover:text-indigo-800 font-medium"
                            >
                              Reschedule
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="pt-2 mt-2 border-t border-slate-100 text-center">
                  <button
                    onClick={() => {
                      setIsAddContentOpen(true);
                      const targetDate = new Date(Date.now() + (dayNum - 1) * 86400000);
                      setManualDate(new Date(targetDate.getTime() - targetDate.getTimezoneOffset() * 60000).toISOString().slice(0, 16));
                    }}
                    className="text-[11px] text-slate-500 hover:text-indigo-600 inline-flex items-center space-x-1"
                  >
                    <Plus className="w-3 h-3" />
                    <span>Add to Day {dayNum}</span>
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* + ADD CONTENT MODAL */}
      {isAddContentOpen && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-4xl w-full max-h-[92vh] overflow-y-auto shadow-2xl p-6 space-y-6">
            <div className="flex items-center justify-between pb-4 border-b border-slate-200">
              <div>
                <h3 className="text-lg font-bold text-slate-900">Add Content to Calendar</h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Schedule your own uploaded media or text posts directly into the publishing queue.
                </p>
              </div>
              <button
                onClick={() => setIsAddContentOpen(false)}
                className="text-slate-400 hover:text-slate-600 p-1"
              >
                ✕
              </button>
            </div>

            {manualError && (
              <div className="p-3 bg-rose-50 border border-rose-200 text-rose-700 text-xs rounded-xl flex items-center space-x-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{manualError}</span>
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
              {/* Left Column: File Upload & Metadata */}
              <div className="md:col-span-7 space-y-4">
                {/* 1. File Upload Dropzone */}
                <div>
                  <label className="text-xs font-semibold text-slate-700 uppercase tracking-wider block mb-1">
                    1. Upload Assets (Video, Images, or Carousel Slides)
                  </label>
                  <label className="border-2 border-dashed border-slate-300 hover:border-indigo-500 rounded-xl p-4 flex flex-col items-center justify-center cursor-pointer bg-slate-50 transition">
                    <Upload className="w-6 h-6 text-slate-400 mb-1" />
                    <span className="text-xs font-semibold text-slate-700">Click to select files from device</span>
                    <span className="text-[10px] text-slate-400 mt-0.5">MP4, PNG, JPG (select multiple for carousels)</span>
                    <input
                      type="file"
                      multiple
                      accept="image/*,video/*"
                      onChange={handleFileChange}
                      className="hidden"
                    />
                  </label>

                  {manualFiles.length > 0 && (
                    <div className="mt-2 flex items-center space-x-2 overflow-x-auto pb-1">
                      {manualFiles.map((f, i) => (
                        <div key={i} className="text-[11px] bg-slate-100 text-slate-700 px-2.5 py-1 rounded-md shrink-0 flex items-center space-x-1">
                          <span className="line-clamp-1">{f.name}</span>
                          <span className="text-slate-400">({(f.size / 1024 / 1024).toFixed(1)}MB)</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* 2. Text Fields */}
                <div>
                  <label className="text-xs font-semibold text-slate-700">Title / Hook Headline</label>
                  <input
                    type="text"
                    value={manualTitle}
                    onChange={(e) => setManualTitle(e.target.value)}
                    placeholder="Engaging headline for this post"
                    className="mt-1 w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>

                <div>
                  <label className="text-xs font-semibold text-slate-700">Post Caption Copy</label>
                  <textarea
                    value={manualCaption}
                    onChange={(e) => setManualCaption(e.target.value)}
                    rows={3}
                    placeholder="Full copy to accompany the post..."
                    className="mt-1 w-full px-3 py-2 border border-slate-200 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500 font-sans"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-semibold text-slate-700">Hashtags</label>
                    <input
                      type="text"
                      value={manualHashtags}
                      onChange={(e) => setManualHashtags(e.target.value)}
                      placeholder="#growth #automation"
                      className="mt-1 w-full px-3 py-1.5 border border-slate-200 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-slate-700">Call to Action (CTA)</label>
                    <input
                      type="text"
                      value={manualCta}
                      onChange={(e) => setManualCta(e.target.value)}
                      placeholder="Visit incubrix.com"
                      className="mt-1 w-full px-3 py-1.5 border border-slate-200 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                  </div>
                </div>

                {/* 3. Platform Selection */}
                <div>
                  <label className="text-xs font-semibold text-slate-700 block mb-1">
                    3. Target Publishing Platforms
                  </label>
                  <div className="flex items-center space-x-3">
                    {['youtube', 'facebook', 'instagram'].map((plat) => (
                      <label
                        key={plat}
                        className={`flex items-center space-x-2 px-3 py-1.5 rounded-lg border text-xs cursor-pointer transition ${
                          manualPlatforms.includes(plat)
                            ? 'bg-indigo-50 border-indigo-500 text-indigo-700 font-semibold'
                            : 'border-slate-200 text-slate-600 hover:bg-slate-50'
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={manualPlatforms.includes(plat)}
                          onChange={() => togglePlatform(plat)}
                          className="rounded text-indigo-600 focus:ring-0"
                        />
                        <span className="capitalize">{plat}</span>
                      </label>
                    ))}
                  </div>
                </div>

                {/* 4. Scheduling Time */}
                <div className="grid grid-cols-2 gap-3 pt-2 border-t border-slate-100">
                  <div>
                    <label className="text-xs font-semibold text-slate-700">Scheduled Date & Time</label>
                    <input
                      type="datetime-local"
                      value={manualDate}
                      onChange={(e) => setManualDate(e.target.value)}
                      className="mt-1 w-full px-3 py-1.5 border border-slate-200 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-slate-700">Timezone</label>
                    <select
                      value={manualTimezone}
                      onChange={(e) => setManualTimezone(e.target.value)}
                      className="mt-1 w-full px-3 py-1.5 border border-slate-200 rounded-lg text-xs bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    >
                      <option value="UTC">UTC</option>
                      <option value="America/New_York">America/New_York (EST)</option>
                      <option value="America/Los_Angeles">America/Los_Angeles (PST)</option>
                      <option value="Europe/London">Europe/London (GMT)</option>
                      <option value="Asia/Kolkata">Asia/Kolkata (IST)</option>
                    </select>
                  </div>
                </div>

                {/* Draft Toggle */}
                <div className="flex items-center space-x-2 pt-1">
                  <input
                    type="checkbox"
                    id="draftToggle"
                    checked={manualIsDraft}
                    onChange={(e) => setManualIsDraft(e.target.checked)}
                    className="rounded text-indigo-600"
                  />
                  <label htmlFor="draftToggle" className="text-xs text-slate-700">
                    Save as draft only (do not schedule into the publishing queue yet)
                  </label>
                </div>
              </div>

              {/* Right Column: Platform Preview */}
              <div className="md:col-span-5 bg-slate-50 p-4 rounded-xl border border-slate-200 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between pb-2 mb-3 border-b border-slate-200">
                    <span className="text-xs font-bold text-slate-700 uppercase tracking-wider">
                      Platform Live Preview
                    </span>
                    <div className="flex space-x-1">
                      {manualPlatforms.map((p) => (
                        <button
                          key={p}
                          onClick={() => setPreviewPlatformTab(p)}
                          className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase transition ${
                            previewPlatformTab === p ? 'bg-indigo-600 text-white' : 'bg-white text-slate-600'
                          }`}
                        >
                          {p}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Device Card Preview */}
                  <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden text-xs">
                    <div className="p-3 border-b border-slate-100 flex items-center space-x-2">
                      <div className="w-7 h-7 rounded-full bg-indigo-600 text-white font-bold flex items-center justify-center text-[10px]">
                        iB
                      </div>
                      <div>
                        <div className="font-bold text-slate-900 leading-none">IncuBrix Official</div>
                        <div className="text-[10px] text-slate-400 capitalize">{previewPlatformTab} Post</div>
                      </div>
                    </div>

                    {/* Media Preview Box */}
                    <div className="aspect-square bg-slate-800 flex items-center justify-center overflow-hidden">
                      {manualPreviewUrls.length > 0 ? (
                        manualFiles[0]?.type.startsWith('video/') ? (
                          <video src={manualPreviewUrls[0]} controls className="w-full h-full object-cover" />
                        ) : (
                          <img src={manualPreviewUrls[0]} alt="" className="w-full h-full object-cover" />
                        )
                      ) : (
                        <div className="text-slate-400 text-center p-4">
                          <Layers className="w-8 h-8 mx-auto mb-1 opacity-50" />
                          <span className="text-[11px]">Upload asset to preview canvas</span>
                        </div>
                      )}
                    </div>

                    <div className="p-3 space-y-1.5">
                      <div className="font-bold text-slate-900">{manualTitle || 'Your Post Headline'}</div>
                      <p className="text-slate-600 text-[11px] whitespace-pre-wrap line-clamp-3">
                        {manualCaption || 'Your post caption copy will appear here...'}
                      </p>
                      {manualHashtags && (
                        <p className="text-indigo-600 text-[10px]">{manualHashtags}</p>
                      )}
                      {manualCta && (
                        <div className="pt-1 text-[10px] font-semibold text-slate-800">
                          CTA: {manualCta}
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {/* Platform Validation Checklist */}
                <div className="pt-3 border-t border-slate-200 space-y-1">
                  <div className="text-[11px] font-semibold text-slate-700 flex items-center space-x-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                    <span>Format verified for {previewPlatformTab.toUpperCase()}</span>
                  </div>
                  <div className="text-[10px] text-slate-500">
                    {previewPlatformTab === 'instagram'
                      ? 'Reels (max 90s), Carousels (2-10 slides), or 1:1/4:5 Images'
                      : previewPlatformTab === 'youtube'
                      ? 'Shorts vertical 9:16 (max 60s) or horizontal video'
                      : 'Posts with text, single image, carousel or video'}
                  </div>
                </div>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="flex items-center justify-end space-x-3 pt-4 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setIsAddContentOpen(false)}
                className="px-4 py-2 border border-slate-200 rounded-lg text-xs font-semibold text-slate-600 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={submittingManual}
                onClick={handleSaveManualContent}
                className="px-5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold shadow-sm transition disabled:opacity-50 flex items-center space-x-1.5"
              >
                {submittingManual ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
                <span>{manualIsDraft ? 'Save as Draft' : 'Schedule into Calendar'}</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* EDIT POST MODAL */}
      {editModal && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl p-6 max-w-lg w-full shadow-2xl border border-slate-200 space-y-4">
            <h3 className="text-base font-bold text-slate-900">Edit Post Content</h3>

            <div>
              <label className="text-xs font-semibold text-slate-700">Headline / Hook</label>
              <input
                type="text"
                value={editTitle}
                onChange={(e) => setEditTitle(e.target.value)}
                className="mt-1 w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-700">Caption</label>
              <textarea
                value={editCaption}
                onChange={(e) => setEditCaption(e.target.value)}
                rows={4}
                className="mt-1 w-full px-3 py-2 border border-slate-200 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div className="flex items-center justify-end space-x-3 pt-3 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setEditModal(null)}
                className="text-xs font-semibold text-slate-600 px-4 py-2 rounded-lg border border-slate-200"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={savingEdit}
                onClick={handleSaveEdit}
                className="bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold px-4 py-2 rounded-lg shadow-sm disabled:opacity-50"
              >
                {savingEdit ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* RESCHEDULE MODAL */}
      {rescheduleModal && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl p-6 max-w-md w-full shadow-2xl border border-slate-200 space-y-4">
            <h3 className="text-base font-bold text-slate-900">Reschedule Publishing Slot</h3>
            <p className="text-xs text-slate-500">
              Modifying this date updates the actual persistent publishing job in PostgreSQL.
            </p>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                New Publication Time (Local / UTC)
              </label>
              <input
                type="datetime-local"
                value={newDateTime}
                onChange={(e) => setNewDateTime(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div className="flex items-center justify-end space-x-3 pt-3 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setRescheduleModal(null)}
                className="text-xs font-semibold text-slate-600 px-4 py-2 rounded-lg border border-slate-200"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={savingReschedule}
                onClick={handleSaveReschedule}
                className="inline-flex items-center space-x-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold px-4 py-2 rounded-lg shadow-sm disabled:opacity-50"
              >
                {savingReschedule ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
                <span>Update Schedule</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
