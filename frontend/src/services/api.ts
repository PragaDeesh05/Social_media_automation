import axios from 'axios';
import {
  User, BrandProfile, SourceDocument, Campaign,
  ContentAsset, ScheduledPostItem, ConnectedAccount, CampaignAnalytics
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8005/api/v1';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Interceptor to attach JWT token
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('incubrix_auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const api = {
  // Health
  getHealth: async () => {
    const res = await apiClient.get('/health');
    return res.data;
  },

  // Auth
  login: async (email: string, password: string) => {
    const res = await apiClient.post('/auth/login', { email, password, full_name: 'User' });
    if (res.data.access_token) {
      localStorage.setItem('incubrix_auth_token', res.data.access_token);
    }
    return res.data;
  },

  getMe: async (): Promise<User> => {
    const res = await apiClient.get('/auth/me');
    return res.data;
  },

  // Brand Profiles
  getBrandProfiles: async (): Promise<BrandProfile[]> => {
    const res = await apiClient.get('/brand-profiles');
    return res.data;
  },

  createBrandProfile: async (profile: BrandProfile): Promise<BrandProfile> => {
    const res = await apiClient.post('/brand-profiles', profile);
    return res.data;
  },

  updateBrandProfile: async (id: string, profile: BrandProfile): Promise<BrandProfile> => {
    const res = await apiClient.put(`/brand-profiles/${id}`, profile);
    return res.data;
  },

  // Source Ingestion
  uploadSourceFile: async (file: File, title?: string, onProgress?: (p: number) => void) => {
    const formData = new FormData();
    formData.append('file', file);
    if (title) formData.append('title', title);

    const res = await apiClient.post('/sources/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => {
        if (onProgress && e.total) {
          onProgress(Math.round((e.loaded * 100) / e.total));
        }
      },
    });
    return res.data;
  },

  ingestText: async (payload: { title: string; text_content?: string; url?: string; source_type?: string }) => {
    const res = await apiClient.post('/sources/text', payload);
    return res.data;
  },

  listSources: async (): Promise<SourceDocument[]> => {
    const res = await apiClient.get('/sources');
    return res.data;
  },

  getSource: async (id: string): Promise<SourceDocument> => {
    const res = await apiClient.get(`/sources/${id}`);
    return res.data;
  },

  updateExtraction: async (id: string, payload: { clean_transcript?: string; main_subject?: string; topics?: string[] }) => {
    const res = await apiClient.put(`/sources/${id}/extraction`, payload);
    return res.data;
  },

  // Campaigns
  listCampaigns: async (): Promise<Campaign[]> => {
    const res = await apiClient.get('/campaigns');
    return res.data;
  },

  getCampaign: async (id: string): Promise<Campaign> => {
    const res = await apiClient.get(`/campaigns/${id}`);
    return res.data;
  },

  createCampaign: async (payload: {
    name: string;
    source_document_id?: string;
    brand_profile_id?: string;
    duration_days: number;
    platforms: string[];
    formats: string[];
    timezone_name: string;
  }): Promise<Campaign> => {
    const res = await apiClient.post('/campaigns', payload);
    return res.data;
  },

  planCampaign: async (campaignId: string) => {
    const res = await apiClient.post(`/campaigns/${campaignId}/plan`);
    return res.data;
  },

  generateAssets: async (campaignId: string) => {
    const res = await apiClient.post(`/campaigns/${campaignId}/generate-assets`);
    return res.data;
  },

  exportCampaignLaunchKit: async (campaignId: string) => {
    const res = await apiClient.get(`/campaigns/${campaignId}/export`);
    return res.data;
  },

  // Content Assets
  listAssets: async (params?: { campaign_id?: string; platform?: string; format?: string; approval_status?: string }): Promise<ContentAsset[]> => {
    const res = await apiClient.get('/assets', { params });
    return res.data;
  },

  getAsset: async (id: string): Promise<ContentAsset> => {
    const res = await apiClient.get(`/assets/${id}`);
    return res.data;
  },

  updateAsset: async (id: string, payload: Partial<ContentAsset>) => {
    const res = await apiClient.put(`/assets/${id}`, payload);
    return res.data;
  },

  duplicateAsset: async (id: string) => {
    const res = await apiClient.post(`/assets/${id}/duplicate`);
    return res.data;
  },

  deleteAsset: async (id: string) => {
    const res = await apiClient.delete(`/assets/${id}`);
    return res.data;
  },

  approveAsset: async (id: string) => {
    const res = await apiClient.post(`/assets/${id}/approve`);
    return res.data;
  },

  rejectAsset: async (id: string) => {
    const res = await apiClient.post(`/assets/${id}/reject`);
    return res.data;
  },

  regenerateMedia: async (id: string) => {
    const res = await apiClient.post(`/assets/${id}/regenerate-media`);
    return res.data;
  },

  // Calendar
  getCalendarSlots: async (params?: { campaign_id?: string }): Promise<ScheduledPostItem[]> => {
    const res = await apiClient.get('/calendar', { params });
    return res.data;
  },

  rescheduleSlot: async (postId: string, payload: { scheduled_utc: string; timezone_name?: string }) => {
    const res = await apiClient.post(`/calendar/reschedule/${postId}`, payload);
    return res.data;
  },

  updateCalendarPost: async (postId: string, payload: { title?: string; caption?: string; scheduled_utc?: string; timezone_name?: string; status?: string }) => {
    const res = await apiClient.put(`/calendar/post/${postId}`, payload);
    return res.data;
  },

  deleteCalendarPost: async (postId: string) => {
    const res = await apiClient.delete(`/calendar/post/${postId}`);
    return res.data;
  },

  scheduleManualContent: async (formData: FormData) => {
    const res = await apiClient.post('/calendar/manual-content', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },

  // Independent Generation Modules
  generateAiScript: async (payload: { topic: string; source_text?: string; platform?: string; aspect_ratio?: string; tone?: string }) => {
    const res = await apiClient.post('/generation/ai-script', payload);
    return res.data;
  },

  generateAiCarouselOutline: async (payload: { topic: string; source_text?: string; platform?: string; slide_count?: number; aspect_ratio?: string }) => {
    const res = await apiClient.post('/generation/ai-carousel-outline', payload);
    return res.data;
  },

  generateAiPosterContent: async (payload: { topic: string; source_text?: string; platform?: string; aspect_ratio?: string }) => {
    const res = await apiClient.post('/generation/ai-poster-content', payload);
    return res.data;
  },

  generateVideo: async (payload: {
    title?: string;
    narration?: string;
    scenes?: Array<{ idx: number; headline: string; title: string; highlight?: string }>;
    platform?: string;
    aspect_ratio?: string;
    aspect?: string;
    campaign_id?: string;
    caption?: string;
    hashtags?: string[];
    cta?: string;
    brand?: string;
    use_case?: string;
    goal?: string;
    audience?: string;
    tone?: string;
    offer?: string;
    scenes_count?: number;
    seconds?: number;
    voice?: string;
    asset_id?: string;
  }) => {
    const res = await apiClient.post('/generation/video', payload);
    return res.data;
  },

  generateCarousel: async (payload: {
    title?: string;
    slides?: Array<{ slide_num: number; headline: string; body: string; takeaway: string }>;
    platform?: string;
    aspect_ratio?: string;
    campaign_id?: string;
    caption?: string;
    hashtags?: string[];
    cta?: string;
    brand?: string;
    goal?: string;
    audience?: string;
    tone?: string;
    offer?: string;
    num_slides?: number;
    asset_id?: string;
  }) => {
    const res = await apiClient.post('/generation/carousel', payload);
    return res.data;
  },

  generatePoster: async (payload: {
    headline?: string;
    subheadline?: string;
    quote?: string;
    cta?: string;
    platform?: string;
    aspect_ratio?: string;
    aspect?: string;
    campaign_id?: string;
    caption?: string;
    hashtags?: string[];
    primary_color?: string;
    brand?: string;
    use_case?: string;
    goal?: string;
    direction?: string;
    language?: string;
    variants?: number;
    asset_id?: string;
  }) => {
    const res = await apiClient.post('/generation/poster', payload);
    return res.data;
  },

  // Connected Accounts
  listConnectedAccounts: async (): Promise<ConnectedAccount[]> => {
    const res = await apiClient.get('/connected-accounts');
    return res.data;
  },

  disconnectAccount: async (id: string) => {
    const res = await apiClient.delete(`/connected-accounts/${id}`);
    return res.data;
  },

  startOAuth: async (platform: string) => {
    const res = await apiClient.get(`/oauth/${platform}/authorize`);
    return res.data;
  },

  getOAuthStatus: async () => {
    const res = await apiClient.get('/oauth/status');
    return res.data;
  },

  saveOAuthCredentials: async (platform: string, payload: { client_id: string; client_secret: string }) => {
    const res = await apiClient.post(`/oauth/${platform}/credentials`, payload);
    return res.data;
  },

  connectManualAccount: async (platform: string, payload: {
    account_name: string;
    username?: string;
    account_id?: string;
    access_token?: string;
    account_type?: string;
    platform_subtype?: string;
  }) => {
    const res = await apiClient.post(`/oauth/${platform}/connect-manual`, payload);
    return res.data;
  },

  // Publishing Queue
  getPublishingQueue: async (status?: string): Promise<ScheduledPostItem[]> => {
    const res = await apiClient.get('/publishing/queue', { params: { status } });
    return res.data;
  },

  publishNow: async (postId: string) => {
    const res = await apiClient.post(`/publishing/publish-now/${postId}`);
    return res.data;
  },

  retryPost: async (postId: string) => {
    const res = await apiClient.post(`/publishing/retry/${postId}`);
    return res.data;
  },

  cancelPost: async (postId: string) => {
    const res = await apiClient.post(`/publishing/cancel/${postId}`);
    return res.data;
  },

  publishAssetDirectly: async (assetId: string, platform?: string, customCaption?: string) => {
    const res = await apiClient.post(`/publishing/publish/${assetId}`, {
      platform,
      custom_caption: customCaption
    });
    return res.data;
  },

  scheduleAssetDirectly: async (assetId: string, scheduledDate: string, platform?: string, customCaption?: string) => {
    const res = await apiClient.post('/publishing/schedule', {
      asset_id: assetId,
      scheduled_date: scheduledDate,
      platform,
      custom_caption: customCaption
    });
    return res.data;
  },

  // Media Library
  listMedia: async (params?: { media_type?: string; campaign_id?: string }) => {
    const res = await apiClient.get('/media', { params });
    return res.data;
  },

  // Analytics
  getCampaignAnalytics: async (campaignId: string): Promise<CampaignAnalytics> => {
    const res = await apiClient.get(`/analytics/campaign/${campaignId}`);
    return res.data;
  },
};
