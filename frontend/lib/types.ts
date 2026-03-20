export type UserType   = "smb_owner" | "ca_firm";
export type Language   = "hi" | "en" | "hinglish";
export type UploadStatus = "pending" | "processing" | "completed" | "failed";
export type Severity   = "HIGH" | "MEDIUM" | "LOW";
export type Trend      = "up" | "down" | "flat";
export type ReportType = "weekly" | "monthly" | "alert" | "on_demand";

export interface UploadResponse {
  upload_id:       string;
  file_name:       string;
  file_type:       "tally_xml" | "excel" | "csv";
  file_size_bytes: number;
  status:          UploadStatus;
  message:         string;
}

export interface UploadStatusResponse {
  upload_id:          string;
  status:             UploadStatus;
  data_health_score:  number | null;
  health_report:      Record<string, unknown> | null;
  error_message:      string | null;
  created_at:         string;
  processed_at:       string | null;
}

export interface RevenueMetrics {
  current:       number;
  previous:      number;
  change_amount: number;
  change_pct:    number | null;
  trend:         Trend;
}

export interface TopProduct {
  name:    string;
  revenue: number;
  rank?:   number;
  trend?:  Trend;
}

export interface DeadStockItem {
  product:         string;
  days_since_last_sale: number;
}

export interface MetricsResponse {
  upload_id:       string;
  period_start:    string;
  period_end:      string;
  revenue:         RevenueMetrics;
  top_products:    TopProduct[];
  dead_stock:      DeadStockItem[];
  dead_stock_count: number;
}

export interface Anomaly {
  severity:    Severity;
  title:       string;
  explanation: string;
  action:      string;
}

export interface AnomaliesResponse {
  upload_id:      string;
  total_detected: number;
  high_count:     number;
  medium_count:   number;
  low_count:      number;
  anomalies:      Anomaly[];
}

export interface CustomerSegments {
  [key: string]: number | undefined;
}

export interface TopCustomer {
  name:     string;
  revenue:  number;
  segment?: string;
  visits?:  number;
}

export interface CustomersResponse {
  upload_id:       string;
  total_customers: number;
  segments:        CustomerSegments;
  top_customers:   TopCustomer[];
}

export interface AnalysisHistoryItem {
  analysis_id:      string;
  upload_id:        string;
  file_name:        string;
  file_type:        string;
  health_score:     number | null;
  period_start:     string;
  period_end:       string;
  current_revenue:  number | null;
  trend:            Trend | null;
  anomaly_count:    number;
  created_at:       string;
}

export interface Report {
  report_id:        string;
  analysis_id:      string;
  report_type:      ReportType;
  language:         Language;
  content:          string;
  word_count:       number;
  whatsapp_sent:    boolean;
  whatsapp_sent_at: string | null;
  period_start:     string;
  period_end:       string;
  created_at:       string;
}

export interface CADashboard {
  total_clients:   number;
  active_clients:  number;
  total_uploads:   number;
  at_risk_clients: number;
  high_alert_clients: Array<{
    client_id:   string;
    client_name: string;
    high_alerts: number;
    last_upload: string | null;
  }>;
}

export interface CAClient {
  client_id:           string;
  client_name:         string;
  client_phone:        string | null;
  client_email:        string | null;
  language_preference: Language;
  whatsapp_opted_in:   boolean;
  active:              boolean;
  upload_count:        number;
  last_upload_at:      string | null;
  created_at:          string;
}

export interface UserProfile {
  user_id:             string;
  email:               string;
  name:                string;
  user_type:           UserType;
  language_preference: Language;
  phone:               string | null;
  whatsapp_opted_in:   boolean;
  created_at:          string;
}
