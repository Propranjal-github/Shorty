export interface URLRequest {
  url: string;
  custom_code?: string;
  ttl_seconds?: number;
}

export interface URLResponse {
  short_code: string;
  short_url: string;
  original_url: string;
  created_at: string;
  expires_at: string | null;
}

export interface URLStats {
  short_code: string;
  original_url: string;
  click_count: number;
  created_at: string;
  expires_at: string | null;
}

export interface ClickBucket {
  bucket: string;
  clicks: number;
}

export interface ReferrerCount {
  referrer: string | null;
  count: number;
}

export interface AnalyticsResponse {
  short_code: string;
  total_clicks: number;
  recent: ClickBucket[];
  top_referrers: ReferrerCount[];
}
