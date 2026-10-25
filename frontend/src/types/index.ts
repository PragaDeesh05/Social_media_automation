export type Platform = 'instagram' | 'facebook' | 'youtube';
export type ContentFormat = 'text' | 'image' | 'carousel' | 'short_video' | 'reel' | 'shorts';
export type PublishingStatus = 'pending' | 'scheduled' | 'publishing' | 'published' | 'failed' | 'cancelled';
export type ApprovalStatus = 'draft' | 'pending_approval' | 'approved' | 'rejected';

export interface User {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  is_superuser: boolean;
}

export interface BrandProfile {
  id?: string;
  brand_name: string;
  target_audience: string;
  tone_of_voice: string;
  vocabulary_rules?: string;
  words_to_avoid: string[];
  default_cta: string;
  primary_color: string;
  secondary_color: string;
  verified_product_facts: string[];
}

export interface SourceDocument {
  id: string;
  title: string;
  source_type: string;
  status: 'pending' | 'processing' | 'ready' | 'failed';
  error_message?: string;
  file_size_bytes?: number;
  media_duration_seconds?: number;
  minio_object_key?: string;
  download_url?: string;
  created_at: string;
  extraction?: SourceExtraction;
}

export interface SourceExtraction {
  clean_transcript?: string;
  main_subject?: string;
  audience_intent?: string;
  topics?: string[];
  subtopics?: string[];
  key_claims?: Array<{ claim: string; evidence: string; status: string }>;
  quotes_with_timestamps?: Array<{ quote: string; timestamp?: string; context?: string }>;
  content_opportunities?: Array<{ title: string; format: string; platform: string }>;
}

export interface Campaign {
  id: string;
  name: string;
  duration_days: number;
  platforms: Platform[];
  formats: ContentFormat[];
  timezone_name: string;
  status: 'draft' | 'planning' | 'generated' | 'scheduled' | 'active' | 'completed';
  total_assets?: number;
  created_at: string;
  plan?: {
    title: string;
    strategy_summary: string;
    total_slots: number;
    pillar_distribution: Record<string, string>;
  };
}

export interface ContentAsset {
  id: string;
  campaign_id: string;
  day_number: number;
  slot_index: number;
  platform: Platform;
  format: ContentFormat;
  hook: string;
  caption: string;
  hashtags: string[];
  cta: string;
  tracking_url?: string;
  approval_status: ApprovalStatus;
  quality_status: 'pending' | 'passed' | 'warnings' | 'failed';
  scheduled_slot_time?: string;
  preview_url?: string;
  media_count?: number;
  media?: AssetMedia[];
  versions?: Array<{
    version_number: number;
    hook: string;
    caption: string;
    cta: string;
    change_notes?: string;
    created_at: string;
  }>;
  quality_checks?: {
    brand?: { passed: boolean; quality_score: number; violations: string[]; warnings: string[] };
    platform?: { passed: boolean; violations: string[]; warnings: string[] };
    is_duplicate?: boolean;
  };
  source_references?: Array<{ quote: string; pillar?: string }>;
}

export interface AssetMedia {
  id: string;
  media_type: string;
  file_name: string;
  slide_index?: number;
  duration_seconds?: number;
  width?: number;
  height?: number;
  minio_object_key: string;
  presigned_url: string;
  editable_config?: Record<string, any>;
}

export interface ScheduledPostItem {
  scheduled_post_id: string;
  content_asset_id: string;
  campaign_id: string;
  platform: Platform;
  format: ContentFormat;
  hook: string;
  caption: string;
  cta: string;
  tracking_url?: string;
  day_number: number;
  scheduled_utc: string;
  status: PublishingStatus;
  retry_count: number;
  max_retries: number;
  last_error?: string;
  published_post_id?: string;
  published_post_url?: string;
  preview_url?: string;
}

export interface ConnectedAccount {
  id: string;
  platform: Platform;
  account_id: string;
  account_name: string;
  username?: string;
  account_type: string;
  status: 'connected' | 'expired' | 'error' | 'disconnected';
  has_token: boolean;
  is_expired: boolean;
  permissions: string[];
  profile_image_url?: string;
  capabilities?: Record<string, any>;
  created_at: string;
}

export interface CampaignAnalytics {
  total_assets: number;
  published_count: number;
  scheduled_count: number;
  failed_count: number;
  total_clicks: number;
  metrics_by_platform: Record<string, {
    total_assets: number;
    published: number;
    clicks: number;
    impressions?: number | null;
  }>;
  collected_at: string;
}
