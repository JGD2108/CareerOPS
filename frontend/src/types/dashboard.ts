export type Company = {
  id: string
  name: string
  website_url: string | null
  notes: string | null
  created_at: string
  updated_at: string
}

export type Job = {
  id: string
  title: string
  source: string
  source_url: string | null
  location: string | null
  work_mode: string | null
  seniority: string | null
  description: string
  posted_at: string | null
  application_deadline: string | null
  availability_status: string
  availability_reason: string | null
  availability_checked_at: string | null
  description_status: string
  description_quality: string
  description_source: string | null
  fetch_status: string
  resolved_description: string | null
  resolved_description_html: string | null
  resolved_description_url: string | null
  resolved_at: string | null
  resolution_confidence: number | null
  resolution_notes: string | null
  raw_payload: Record<string, unknown> | null
  source_trace: Record<string, unknown> | null
  company: Company | null
  created_at: string
  updated_at: string
}

export type Application = {
  id: string
  job_id: string
  status: string
  job_title?: string | null
  company_name?: string | null
  job_source?: string | null
  notes: string | null
  applied_at: string | null
  latest_portal_status?: string | null
  latest_portal_confidence?: string | null
  latest_portal_checked_at?: string | null
  portal_login_required?: boolean
  portal_user_action_required?: boolean
  created_at: string
  updated_at: string
}

export type PortalCredential = {
  id: string
  application_id: string
  company_id: string | null
  portal_name: string
  portal_url: string
  username: string
  mfa_enabled: boolean
  daily_check_allowed: boolean
  last_checked_at: string | null
  created_at: string
  updated_at: string
}

export type ApplicationStatusCheckEvent = {
  id: string
  application_id: string
  agent_run_id: string | null
  source_url: string | null
  previous_status: string | null
  new_status: string
  public_job_status: string
  evidence_summary: string | null
  confidence: string
  login_required: boolean
  credentials_used: boolean
  user_action_required: boolean
  event_metadata: Record<string, unknown> | null
  checked_at: string
}

export type Email = {
  id: string
  raw_email_id: string
  gmail_message_id: string | null
  gmail_thread_id: string | null
  gmail_history_id: string | null
  gmail_label_ids: string[] | null
  application_id: string | null
  company_name: string | null
  from_name: string | null
  from_email: string
  subject: string | null
  snippet: string | null
  body_text: string | null
  category: string
  urgency: string
  requires_reply: boolean
  suggested_action: string | null
  gmail_draft_id: string | null
  received_at: string | null
  created_at: string
  updated_at: string
}

export type ProfileSkill = {
  id: string
  name: string
  category: string | null
  evidence_level: string
  evidence_text: string
}

export type ProfileProject = {
  id: string
  name: string
  description: string | null
  technologies: string[] | null
  impact: string | null
  project_url: string | null
  repo_url: string | null
  metric_bullets: string[] | null
  source_type: string | null
  source_document_id: string | null
  evidence_text: string
}

export type ProfileExperience = {
  id: string
  company: string
  title: string
  location: string | null
  start_date: string | null
  end_date: string | null
  bullets: string[] | null
  evidence_text: string
}

export type CandidateProfile = {
  id: string
  display_name: string | null
  headline: string | null
  location: string | null
  summary: string | null
  preferences: Record<string, unknown> | null
  skills: ProfileSkill[]
  projects: ProfileProject[]
  experiences: ProfileExperience[]
}

export type ResourceState<T> = {
  data: T
  loading: boolean
  error: string | null
  unavailable: boolean
}
