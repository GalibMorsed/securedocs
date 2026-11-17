export type DocumentStatus = "uploaded" | "processing" | "ready" | "failed";

export interface DocumentVersion {
  id: string;
  version_number: number;
  name: string;
  description: string | null;
  mime_type: string | null;
  file_size: number | null;
  created_by: string | null;
  created_at: string;
}

export interface DocumentRecord {
  id: string;
  organization_id: string;
  owner_id: string;
  has_file: boolean;
  name: string;
  description: string | null;
  mime_type: string | null;
  file_size: number | null;
  status: DocumentStatus;
  created_at: string;
  updated_at: string;
  versions: DocumentVersion[];
}

export interface DocumentPayload {
  name: string;
  description?: string | null;
  mime_type?: string | null;
  file_size?: number | null;
}
