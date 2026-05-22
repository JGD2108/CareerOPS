import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { Dispatch, ReactNode, SetStateAction } from 'react'

import { API_BASE_URL, cvArtifactUrl, requestApi, requestCareerInboxSync } from './lib/api'
import {
  cleanDisplayName,
  cleanDisplayText,
  normalizeForMatch,
  payloadText,
  truncate,
  unknownToDisplayString,
} from './lib/text'
import { InboxSection } from './components/InboxSection'
import { ProfileSection } from './components/ProfileSection'
import { AiText } from './components/AiText'
import type {
  Application,
  ApplicationStatusCheckEvent,
  CandidateProfile,
  Email,
  Job,
  PortalCredential,
  ResourceState,
} from './types/dashboard'
const API_HOSTNAME = (() => {
  try {
    return new URL(API_BASE_URL).hostname
  } catch {
    return ''
  }
})()
const IS_LOCAL_API = API_HOSTNAME === '127.0.0.1' || API_HOSTNAME === 'localhost'
const INITIAL_URL_PARAMS = new URLSearchParams(window.location.search)
const INITIAL_GMAIL_CONNECTED = INITIAL_URL_PARAMS.get('gmail') === 'connected'
const INITIAL_GMAIL_SYNC = INITIAL_URL_PARAMS.get('sync')
const INITIAL_GMAIL_EMAILS = Number(INITIAL_URL_PARAMS.get('emails') ?? 0)
const GMAIL_CONNECTED_MESSAGE =
  INITIAL_GMAIL_SYNC === 'failed'
    ? 'Google connected. Inbox refresh needs a retry.'
    : INITIAL_GMAIL_SYNC === 'done'
      ? `Google connected. Job inbox updated: ${INITIAL_GMAIL_EMAILS} email(s).`
      : 'Google connected.'

const INCOMPLETE_DESCRIPTION_STATUSES = new Set(['missing', 'partial_from_email', 'failed'])

function isJobDescriptionIncomplete(job: Job | null | undefined) {
  return !job || INCOMPLETE_DESCRIPTION_STATUSES.has(job.description_status)
}

function descriptionStatusLabel(job: Job) {
  if (job.fetch_status === 'needs_manual_review') return 'Needs manual review'
  if (job.description_status === 'partial_from_email') return 'Partial from email'
  if (job.description_status === 'manually_provided') return 'Manually provided'
  if (job.description_status === 'manually_provided_url') return 'Resolved from manual URL'
  if (job.description_status === 'resolved_from_ats') return `Resolved from ${job.description_source ?? 'ATS'}`
  if (job.description_status === 'resolved_from_company_site') return 'Resolved from company site'
  if (job.description_status === 'missing') return 'Missing description'
  return job.description_status.replaceAll('_', ' ')
}

type Action = {
  id: string
  application_id: string
  email_id: string | null
  action_key: string
  action_type: string
  status: string
  title: string
  details: string | null
  priority: string
  due_at: string | null
  completed_at: string | null
  created_at: string
  updated_at: string
}

type DocumentRecord = {
  id: string
  source_type: string
  original_filename: string
  storage_path: string
  content_type: string | null
  checksum: string | null
  extracted_text: string | null
  document_metadata: Record<string, unknown> | null
  created_at: string
}

type JobScore = {
  id: string
  job_id: string
  candidate_profile_id: string
  score: number
  recommendation: string
  extracted_requirements: {
    title?: string
    location?: string | null
    seniority?: string | null
    work_mode?: string | null
    role_signals?: Record<string, string[]>
    required_skills?: string[]
    years_experience?: number | null
  }
  matched_skills: Array<{
    required_skill: string
    profile_skill: string
    match_type: string
    evidence_level: string
    evidence_text: string
    rationale: string | null
  }>
  missing_or_weak_skills: Array<string | { skill?: string; evidence_level?: string }>
  reasons: string[]
  risks: string[]
  evidence: Array<{
    claim: string
    source: string
    evidence_text: string
  }>
  created_at: string
}

type CVVersion = {
  id: string
  job_id: string
  candidate_profile_id: string
  source_document_id: string | null
  status: string
  tailoring_plan: {
    planner?: string
    planner_fallback_reason?: string
    template_filename?: string | null
    generated_tex_path?: string | null
    generated_pdf_path?: string | null
    pdf_generation_error?: string | null
    summary_focus?: string[]
    do_not_claim?: string[]
    skills_to_prioritize?: string[]
    experience_bullets_to_reuse?: Array<{
      bullet: string
      why: string
      company: string
      title: string
    }>
    projects_to_prioritize?: Array<{
      project: string
      why: string
      existing_content?: {
        description?: string
        impact?: string
        technologies?: string[]
      }
    }>
    approval_required?: boolean
  }
  changes: Array<{
    section: string
    action: string
    reason: string
    source?: string
  }>
  generated_file_path: string | null
  review_notes: string | null
  reviewed_at: string | null
  created_at: string
}

type MessageDraft = {
  id: string
  job_id: string
  candidate_profile_id: string
  cv_version_id: string | null
  draft_type: string
  status: string
  subject: string | null
  body: string
  tone: string
  language: string
  evidence: Array<Record<string, string>>
  approval_required: boolean
  review_notes: string | null
  reviewed_at: string | null
  created_at: string
}

type ApplicationTracker = {
  application_id: string
  job_id: string
  status: string
  job_title: string | null
  company_name: string | null
  artifact_state: {
    has_score: boolean
    has_approved_cv: boolean
    has_approved_message: boolean
  }
  ready_to_apply: boolean
  current_action: string
  next_steps: string[]
  notes: string | null
  applied_at: string | null
  created_at: string
  updated_at: string
}

type NotificationSummary = {
  id: string
  summary_date: string
  channel: string
  content: {
    counts?: {
      new_jobs?: number
      top_matches?: number
      important_emails?: number
      open_actions?: number
      pending_applications?: number
    }
    top_matches?: Array<{
      score: number
      title?: string
      company?: string
      recommendation: string
    }>
    important_emails?: Array<{
      company_name?: string | null
      subject?: string | null
      category: string
      from_email?: string
    }>
    open_actions?: Array<{
      title: string
      priority: string
      action_type: string
    }>
    pending_applications?: Array<{
      company?: string
      title?: string
      status: string
    }>
  }
  rendered_text: string
  created_at: string
}

type JobDiscoveryResponse = {
  raw_jobs_saved: number
  normalized_jobs_created: number
  applications_created: number
  deduplicated_jobs: number
  auto_scored_jobs: number
  matched_jobs: Job[]
}

type ManualJobDescriptionResponse = {
  job: Job
  attempt: JobDescriptionResolutionAttempt
}

type JobDescriptionResolutionAttempt = {
  id: string
  job_id: string
  attempted_source: string
  attempted_url: string | null
  status: string
  confidence: number | null
  reason: string | null
  raw_response_ref: string | null
  error_message: string | null
  metadata: Record<string, unknown> | null
  created_at: string
}

type JobDescriptionResolveResponse = {
  job_id: string
  status: string
  description_status: string
  description_source: string | null
  description_quality: string
  resolved_description_url: string | null
  confidence: number | null
  notes: string
  attempts: JobDescriptionResolutionAttempt[]
}

type GmailStatus = {
  oauth_configured: boolean
  credentials_file_exists: boolean
  token_file_exists: boolean
  authenticated: boolean
  scopes: string[]
  credentials_path: string
  token_path: string
}

type GmailOAuthStart = {
  authorization_url: string
  state: string
  redirect_uri: string
}

type DeleteJobResponse = {
  message: string
  deleted_job_id: string
  title: string
  company: string
}

type DeleteApplicationResponse = {
  message: string
}

type LinkedInSyncResponse = {
  emails_synced: number
  emails_reclassified: number
  job_alerts: number
  application_confirmations: number
  jobs_imported: number
  applications_created: number
  applications_marked_applied: number
  jobs_auto_scored: number
}

type EmbeddingRebuildResponse = {
  created_or_updated: number
  skipped: number
  total_sources: number
}

type SemanticMatch = {
  source_table: string
  source_id: string
  content: string
  metadata: Record<string, unknown>
  similarity: number
}

type AppSection = 'overview' | 'setup' | 'jobs' | 'applications' | 'inbox' | 'profile'
type ActionFilter = 'all' | 'possible' | 'blocked' | 'none'
type PipelineFilter = 'all' | 'active' | 'rejected' | 'actionable' | 'no_action'
type GuidedAction = 'resume-upload' | 'profile-build' | 'job-review' | 'job-discovery'
type ActionMutationState = Record<string, boolean>
type EmailMutationState = Record<string, boolean>
type PortalCredentialForm = {
  portal_name: string
  portal_url: string
  username: string
  password: string
  mfa_enabled: boolean
  daily_check_allowed: boolean
}

const DEFAULT_SECTIONS: Array<{ id: AppSection; label: string }> = [
  { id: 'overview', label: 'Home' },
  { id: 'jobs', label: 'Jobs' },
  { id: 'applications', label: 'Applications' },
  { id: 'inbox', label: 'Inbox' },
  { id: 'profile', label: 'Profile' },
  { id: 'setup', label: 'Settings' },
]

function createInitialResource<T>(initialData: T): ResourceState<T> {
  return {
    data: initialData,
    loading: true,
    error: null,
    unavailable: false,
  }
}

async function loadResource<T>(
  path: string,
  setter: Dispatch<SetStateAction<ResourceState<T>>>,
  initialData: T,
  options?: { preserveDataWhileLoading?: boolean },
) {
  if (options?.preserveDataWhileLoading) {
    setter((current) => ({
      ...current,
      loading: true,
      error: null,
      unavailable: false,
    }))
  } else {
    setter({
      data: initialData,
      loading: true,
      error: null,
      unavailable: false,
    })
  }

  try {
    const data = await requestApi<T>(path)
    setter({
      data,
      loading: false,
      error: null,
      unavailable: false,
    })
  } catch (error) {
    const status = (error as Error & { status?: number }).status
    if (options?.preserveDataWhileLoading) {
      setter((current) => ({
        ...current,
        loading: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        unavailable: status === 404,
      }))
    } else {
      setter({
        data: initialData,
        loading: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        unavailable: status === 404,
      })
    }
  }
}

function formatDate(value: string | null): string {
  if (!value) {
    return 'Not set'
  }

  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(new Date(value))
}

function formatRelativeDate(value: string | null): string {
  if (!value) {
    return 'No timestamp'
  }

  const date = new Date(value)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (diffDays <= 0) {
    return 'Today'
  }

  if (diffDays === 1) {
    return '1 day ago'
  }

  return `${diffDays} days ago`
}

function formatSourceLabel(source: string): string {
  return source
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

function normalizeTokenList(value: string): string[] {
  return value
    .split(/[\n,;|]+/)
    .map((item) => cleanDisplayText(item).trim())
    .filter(Boolean)
}

function extractJobSections(description: string) {
  const cleaned = cleanDisplayText(description)
  const lines = normalizeTokenList(
    cleaned
      .replace(/Responsibilities?:/gi, '\nResponsibilities:\n')
      .replace(/Requirements?:/gi, '\nRequirements:\n')
      .replace(/Qualifications?:/gi, '\nQualifications:\n')
      .replace(/What you'll do:?/gi, "\nResponsibilities:\n")
      .replace(/What you will do:?/gi, "\nResponsibilities:\n")
      .replace(/What we're looking for:?/gi, '\nRequirements:\n')
      .replace(/What we are looking for:?/gi, '\nRequirements:\n'),
  )

  const responsibilities: string[] = []
  const requirements: string[] = []
  const overview: string[] = []
  let currentSection: 'overview' | 'responsibilities' | 'requirements' = 'overview'

  for (const line of lines) {
    const normalized = line.toLowerCase()
    if (normalized === 'responsibilities:' || normalized === 'responsibilities') {
      currentSection = 'responsibilities'
      continue
    }
    if (
      normalized === 'requirements:' ||
      normalized === 'requirements' ||
      normalized === 'qualifications:' ||
      normalized === 'qualifications'
    ) {
      currentSection = 'requirements'
      continue
    }

    if (currentSection === 'responsibilities') {
      responsibilities.push(line)
    } else if (currentSection === 'requirements') {
      requirements.push(line)
    } else {
      overview.push(line)
    }
  }

  return {
    overview: overview.slice(0, 3),
    responsibilities: responsibilities.slice(0, 8),
    requirements: requirements.slice(0, 8),
  }
}

function extractSalary(description: string): string | null {
  const salaryMatch =
    description.match(/\$[\d,.]+\s*(?:-|to)\s*\$[\d,.]+(?:\s*(?:per year|\/year|yearly|annually))?/i) ??
    description.match(/\$[\d,.]+k?\+?(?:\s*(?:per year|\/year|yearly|annually))?/i)
  return salaryMatch ? cleanDisplayText(salaryMatch[0]) : null
}

function extractTechnologies(description: string, score: JobScore | null): string[] {
  const technologyTerms = [
    'Python',
    'FastAPI',
    'Node.js',
    'TypeScript',
    'JavaScript',
    'React',
    'PostgreSQL',
    'MySQL',
    'Docker',
    'AWS',
    'GCP',
    'OpenAI',
    'LangGraph',
    'pgvector',
    'Redis',
    'Kubernetes',
    'GitHub Actions',
    'SQL',
  ]
  const combined = `${description} ${(score?.extracted_requirements.required_skills ?? []).join(' ')}`
  return technologyTerms.filter((term) => combined.toLowerCase().includes(term.toLowerCase())).slice(0, 8)
}

function statusLabel(value: boolean, positive: string, negative: string) {
  return value ? positive : negative
}

function TriageAuditPanel() {
  const [events, setEvents] = useState<
    Array<{
      id: string
      event_type: string
      details?: Record<string, unknown> | null
      created_at?: string | null
    }>
  >([])

  useEffect(() => {
    let mounted = true
    void (async () => {
      try {
        const data = await requestApi<
          Array<{
            id: string
            event_type: string
            details?: Record<string, unknown> | null
            created_at?: string | null
          }>
        >('/agents/triage-audit')
        if (mounted) setEvents(data.slice(0, 6))
      } catch {
        // ignore errors for this non-critical panel
      }
    })()
    return () => {
      mounted = false
    }
  }, [])

  if (!events.length) {
    return <p className="mt-2 text-xs text-[color:var(--app-muted)]">No recent triage events.</p>
  }

  return (
    <div className="mt-2 space-y-2">
      {events.map((e) => (
        <div
          key={e.id}
          className="rounded-2xl border border-[color:var(--app-border)] bg-white/90 p-3 text-xs shadow-[0_10px_20px_rgba(23,23,23,0.03)]"
        >
          <div className="flex items-center justify-between">
            <span className="font-medium text-[color:var(--app-ink)]">{e.event_type}</span>
            <span className="text-[color:var(--app-muted)]">{e.created_at ? new Date(e.created_at).toLocaleString() : ''}</span>
          </div>
          <div className="mt-1 text-[color:var(--app-muted)]">
            <div>
              {e.details?.subject
                ? truncate(unknownToDisplayString(e.details.subject), 80)
                : unknownToDisplayString(e.details?.reason) || ''}
            </div>
            <div className="mt-1 text-[10px] text-[color:var(--app-muted)]/80">
              from:{' '}
              {unknownToDisplayString(e.details?.from) ||
                unknownToDisplayString(e.details?.from_header) ||
                'unknown'}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

function gmailThreadUrl(email: Email): string | null {
  if (!email.gmail_thread_id) {
    return null
  }
  return `https://mail.google.com/mail/u/0/#inbox/${email.gmail_thread_id}`
}

function isNoReplySender(fromEmail: string | null | undefined): boolean {
  const sender = (fromEmail ?? '').toLowerCase()
  return sender.includes('no-reply@') || sender.includes('noreply@')
}

function jobGmailThreadUrl(job: Job | null): string | null {
  if (!job?.source_trace) {
    return null
  }
  const rawThreadId = job.source_trace.gmail_thread_id
  if (typeof rawThreadId !== 'string' || !rawThreadId.trim()) {
    return null
  }
  return `https://mail.google.com/mail/u/0/#inbox/${rawThreadId}`
}

function getStatusTone(status: string): string {
  switch (status.toLowerCase()) {
    case 'applied':
    case 'interview':
    case 'offer':
    case 'approved':
    case 'completed':
      return 'bg-emerald-100 text-emerald-800 ring-1 ring-emerald-200'
    case 'reviewed':
    case 'cv generated':
    case 'open':
    case 'draft':
      return 'bg-amber-100 text-amber-900 ring-1 ring-amber-200'
    case 'rejected':
    case 'dismissed':
      return 'bg-rose-100 text-rose-800 ring-1 ring-rose-200'
    default:
      return 'bg-slate-100 text-slate-700 ring-1 ring-slate-200'
  }
}

function getPriorityTone(priority: string): string {
  switch (priority.toLowerCase()) {
    case 'high':
      return 'bg-rose-100 text-rose-800 ring-1 ring-rose-200'
    case 'medium':
      return 'bg-amber-100 text-amber-900 ring-1 ring-amber-200'
    default:
      return 'bg-slate-100 text-slate-700 ring-1 ring-slate-200'
  }
}

function getRecommendationTone(value: string): string {
  switch (value.toLowerCase()) {
    case 'apply_now':
      return 'bg-emerald-100 text-emerald-800 ring-1 ring-emerald-200'
    case 'review':
      return 'bg-amber-100 text-amber-900 ring-1 ring-amber-200'
    default:
      return 'bg-slate-100 text-slate-700 ring-1 ring-slate-200'
  }
}

function getAvailabilityTone(status?: string | null): string {
  switch ((status ?? '').toLowerCase()) {
    case 'open':
      return 'bg-emerald-100 text-emerald-800 ring-1 ring-emerald-200'
    case 'closed':
      return 'bg-rose-100 text-rose-800 ring-1 ring-rose-200'
    case 'login_required':
      return 'bg-amber-100 text-amber-900 ring-1 ring-amber-200'
    default:
      return 'bg-slate-100 text-slate-700 ring-1 ring-slate-200'
  }
}

function formatAvailabilityLabel(status?: string | null): string {
  return (status ?? '')
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

function MetricCard(props: { label: string; value: string | number; note: string }) {
  return (
    <article className="crm-card px-4 py-3">
      <p className="crm-label">
        {props.label}
      </p>
      <p className="mt-2 truncate text-[1.35rem] font-semibold leading-7 text-[color:var(--app-ink)]">
        {props.value}
      </p>
      <p className="mt-1 text-xs leading-5 text-[color:var(--app-muted)]">{props.note}</p>
    </article>
  )
}

function ResourceBanner(props: { title: string; state: ResourceState<unknown> }) {
  if (props.state.loading) {
    return (
      <div className="crm-subcard px-3 py-2 text-sm text-[color:var(--app-muted)]">
        Loading {props.title.toLowerCase()}...
      </div>
    )
  }

  if (props.state.unavailable) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
        {props.title} endpoint is currently unavailable. The workspace stays usable, but this section needs the latest FastAPI server build.
      </div>
    )
  }

  if (props.state.error) {
    return (
      <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-900">
        {props.title} could not be loaded: {props.state.error}
      </div>
    )
  }

  return null
}

function Panel(props: { title: string; subtitle?: string; children: ReactNode }) {
  return (
    <section className="rounded-xl border border-[color:var(--app-border)] bg-[color:var(--app-surface)] p-4 shadow-[0_10px_32px_rgba(24,27,24,0.05)] sm:p-5">
      <div className="border-b border-[color:var(--app-border)] pb-3">
        <p className="crm-label">Workspace</p>
        <h2 className="mt-1 text-lg font-semibold leading-6 text-[color:var(--app-ink)]">
          {props.title}
        </h2>
        {props.subtitle ? (
          <p className="mt-1 max-w-3xl text-sm leading-6 text-[color:var(--app-muted)]">
            {props.subtitle}
          </p>
        ) : null}
      </div>
      <div className="mt-5">{props.children}</div>
    </section>
  )
}

function EmptyState(props: { title: string; body: string }) {
  return (
    <div className="rounded-lg border border-dashed border-[color:var(--app-border-strong)] bg-[color:var(--app-bg-soft)] p-4">
      <p className="crm-label">Empty</p>
      <p className="mt-2 text-base font-semibold text-[color:var(--app-ink)]">
        {props.title}
      </p>
      <p className="mt-2 max-w-2xl text-sm leading-6 text-[color:var(--app-muted)]">
        {props.body}
      </p>
    </div>
  )
}

function SectionButton(props: {
  active: boolean
  label: string
  badge?: number
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={props.onClick}
      className={`flex items-center justify-between rounded-lg px-3 py-2 text-left text-sm font-medium transition ${
        props.active
          ? 'bg-[color:var(--app-ink)] text-white'
          : 'text-[color:var(--app-muted)] hover:bg-[color:var(--app-bg-soft)] hover:text-[color:var(--app-ink)]'
      }`}
    >
      <span className="tracking-[0.01em]">{props.label}</span>
      {props.badge !== undefined ? (
        <span
          className={`rounded-md px-2 py-0.5 text-[0.68rem] ${
            props.active ? 'bg-white/12 text-white' : 'bg-[color:var(--app-accent-soft)] text-[color:var(--app-accent)]'
          }`}
        >
          {props.badge}
        </span>
      ) : null}
    </button>
  )
}

function SetupStep(props: {
  index: number
  title: string
  body: string
  status: 'done' | 'pending' | 'loading'
}) {
  const tone =
    props.status === 'done'
      ? 'border-emerald-200 bg-emerald-50 text-emerald-900'
      : props.status === 'loading'
        ? 'border-[color:var(--app-border)] bg-[color:var(--app-bg-soft)] text-[color:var(--app-muted)]'
        : 'border-[color:var(--app-border)] bg-[color:var(--app-surface-strong)] text-[color:var(--app-ink)]'

  return (
    <article className={`rounded-[1.3rem] border p-4 shadow-[0_14px_35px_rgba(23,23,23,0.04)] ${tone}`}>
      <div className="flex items-center gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-white text-xs font-semibold shadow-sm ring-1 ring-black/5">
          {props.status === 'done' ? 'Ready' : props.index}
        </span>
        <div className="min-w-0">
          <p className="text-sm font-semibold tracking-[0.01em]">{props.title}</p>
          <p className="mt-1 text-sm">{props.body}</p>
        </div>
      </div>
    </article>
  )
}

function SetupHome(props: {
  gmailStatus: ResourceState<GmailStatus | null>
  profile: ResourceState<CandidateProfile | null>
  documents: ResourceState<DocumentRecord[]>
  operationMessage: string | null
  operationError: string | null
  gmailConnecting: boolean
  gmailConfiguring: boolean
  selectedGmailCredentialsFile: File | null
  onSelectGmailCredentialsFile: (file: File | null) => void
  onUploadGmailCredentials: () => void
  onConnectGmail: () => void
  onOpenSetup: () => void
  onEnterDashboard: () => void
}) {
  const gmailReady = Boolean(props.gmailStatus.data?.authenticated)
  const gmailChecking = props.gmailStatus.loading || props.gmailStatus.data === null
  const gmailConfigured = Boolean(props.gmailStatus.data?.oauth_configured)
  const profileReady = Boolean(props.profile.data)
  const documentsReady = props.documents.data.length > 0
  const cvReady = props.documents.data.some((document) => document.source_type === 'cv')
  const loading =
    props.gmailStatus.loading || props.profile.loading || props.documents.loading

  return (
    <div className="min-h-screen px-4 py-6 text-[color:var(--app-ink)] lg:px-8">
      <main className="mx-auto flex min-h-[calc(100vh-3rem)] max-w-7xl flex-col justify-center">
        <section className="overflow-hidden rounded-[2rem] border border-[color:var(--app-border)] bg-[color:var(--app-surface)] shadow-[0_30px_90px_rgba(23,23,23,0.08)] backdrop-blur-sm">
          <div className="grid min-h-[720px] lg:grid-cols-[0.96fr_1.04fr]">
            <div className="relative flex flex-col justify-between overflow-hidden bg-[#111111] p-7 text-white lg:p-10">
              <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(15,118,110,0.24),transparent_30%),radial-gradient(circle_at_bottom_right,rgba(180,83,9,0.18),transparent_28%)]" />
              <div>
                <div className="relative inline-flex rounded-full border border-white/15 bg-white/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.22em] text-stone-200">
                  CareerOps Agent
                </div>
                <h1 className="relative mt-8 max-w-xl font-serif text-4xl font-semibold leading-[0.98] lg:text-[4.3rem]">
                  Sign in with Google to unlock your private hiring workspace.
                </h1>
                <p className="relative mt-5 max-w-md text-base leading-7 text-stone-300">
                  CareerOps uses Google to bring in recruiter updates, job alerts, interviews, and application confirmations. Google sign-in is required before you can enter.
                </p>
              </div>

              <div className="relative mt-10">
                <div className="grid gap-3 sm:grid-cols-3">
                  <div className="rounded-[1.2rem] border border-white/10 bg-white/10 p-4 backdrop-blur-sm">
                    <p className="text-xs uppercase tracking-[0.18em] text-stone-400">Google</p>
                    <p className="mt-1 text-sm font-semibold">
                      {gmailReady ? 'Connected' : 'Required'}
                    </p>
                  </div>
                  <div className="rounded-[1.2rem] border border-white/10 bg-white/10 p-4 backdrop-blur-sm">
                    <p className="text-xs uppercase tracking-[0.18em] text-stone-400">CV</p>
                    <p className="mt-1 text-sm font-semibold">{cvReady ? 'Ready' : 'Next step'}</p>
                  </div>
                  <div className="rounded-[1.2rem] border border-white/10 bg-white/10 p-4 backdrop-blur-sm">
                    <p className="text-xs uppercase tracking-[0.18em] text-stone-400">Profile</p>
                    <p className="mt-1 text-sm font-semibold">
                      {profileReady ? 'Ready' : 'Pending'}
                    </p>
                  </div>
                </div>

                <div className="mt-6 flex flex-wrap gap-3">
                  <button
                    type="button"
                    onClick={props.onConnectGmail}
                    disabled={props.gmailConnecting || !gmailConfigured}
                    className="rounded-2xl bg-[color:var(--app-bg-soft)] px-5 py-3 text-sm font-semibold text-[color:var(--app-ink)] transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {props.gmailConnecting
                      ? 'Opening Google...'
                      : gmailChecking
                        ? 'Checking Google...'
                      : gmailReady
                        ? 'Reconnect Google'
                        : 'Continue with Google'}
                  </button>
                  <button
                    type="button"
                    onClick={props.onEnterDashboard}
                    disabled={!gmailReady}
                    className="rounded-2xl border border-white/20 bg-white/10 px-5 py-3 text-sm font-semibold text-white transition hover:bg-white/15 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    Enter workspace
                  </button>
                </div>
                {!gmailChecking && !gmailConfigured && IS_LOCAL_API ? (
                  <div className="mt-5 rounded-[1.3rem] border border-white/15 bg-white/5 p-4">
                    <p className="text-sm font-semibold text-white">Load your Google OAuth JSON</p>
                    <p className="mt-2 text-sm leading-6 text-stone-300">
                      CareerOps can store the downloaded Google OAuth client locally, so you do not need to copy files by hand.
                    </p>
                    <input
                      type="file"
                      accept=".json,application/json"
                      onChange={(event) =>
                        props.onSelectGmailCredentialsFile(event.target.files?.[0] ?? null)
                      }
                      className="mt-4 w-full rounded-2xl border border-white/15 bg-white/10 px-3 py-2 text-sm text-white file:mr-3 file:rounded-xl file:border-0 file:bg-white file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-[color:var(--app-ink)]"
                    />
                    <div className="mt-4 flex flex-wrap items-center gap-3">
                      <button
                        type="button"
                        onClick={props.onUploadGmailCredentials}
                        disabled={props.gmailConfiguring || !props.selectedGmailCredentialsFile}
                        className="rounded-2xl border border-white/20 bg-white/10 px-4 py-2 text-sm font-semibold text-white transition hover:bg-white/15 disabled:cursor-not-allowed disabled:opacity-40"
                      >
                        {props.gmailConfiguring ? 'Saving OAuth JSON...' : 'Load OAuth JSON'}
                      </button>
                      <span className="text-xs text-stone-400">
                        Expected path:{' '}
                        {props.gmailStatus.data?.credentials_path ?? 'storage/secrets/gmail_credentials.json'}
                      </span>
                    </div>
                  </div>
                ) : null}
                {!gmailChecking && !gmailConfigured ? (
                  <p className="mt-4 text-sm text-rose-200">
                    Google OAuth is not configured on the backend yet.
                  </p>
                ) : null}
              </div>
            </div>

            <div className="flex flex-col justify-between bg-[linear-gradient(180deg,rgba(255,255,255,0.55),rgba(255,248,238,0.92))] p-6 lg:p-8">
              <div>
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[color:var(--app-muted)]">
                      Access
                    </p>
                    <h2 className="mt-2 font-serif text-3xl font-semibold text-[color:var(--app-ink)]">
                      {gmailReady ? 'Workspace ready' : 'Google sign-in required'}
                    </h2>
                  </div>
                  <span
                    className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${
                      gmailReady
                        ? 'bg-emerald-100 text-emerald-800'
                        : 'bg-stone-200 text-stone-700'
                    }`}
                  >
                    {gmailReady ? 'Unlocked' : 'Locked'}
                  </span>
                </div>

                <div className="mt-7 space-y-3">
                  <SetupStep
                    index={1}
                    title="Google"
                    body={
                      gmailReady
                        ? 'Connected'
                        : gmailChecking
                          ? 'Checking'
                        : gmailConfigured
                          ? 'Waiting for sign-in'
                          : 'Backend credentials missing'
                    }
                    status={loading ? 'loading' : gmailReady ? 'done' : 'pending'}
                  />
                  <SetupStep
                    index={2}
                    title="Resume"
                    body={
                      cvReady
                        ? 'CV source is available'
                        : documentsReady
                          ? 'Choose one file to use as your main resume'
                          : 'Upload your main resume'
                    }
                    status={props.documents.loading ? 'loading' : cvReady ? 'done' : 'pending'}
                  />
                  <SetupStep
                    index={3}
                    title="Profile"
                    body={
                      profileReady
                        ? `${cleanDisplayName(props.profile.data?.display_name)} is ready`
                        : 'Create it from your resume'
                    }
                    status={props.profile.loading ? 'loading' : profileReady ? 'done' : 'pending'}
                  />
                </div>
              </div>

              <div className="mt-8">
                <div className="flex flex-wrap gap-3">
                  <button
                    type="button"
                    onClick={props.onOpenSetup}
                    disabled={!gmailReady}
                    className="rounded-2xl bg-[color:var(--app-ink)] px-5 py-3 text-sm font-semibold text-white transition hover:opacity-92 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Continue to resume setup
                  </button>
                <button
                  type="button"
                  onClick={props.onEnterDashboard}
                  disabled={!gmailReady}
                  className="rounded-2xl border border-[color:var(--app-border-strong)] bg-white px-5 py-3 text-sm font-semibold text-[color:var(--app-ink)] transition hover:bg-[color:var(--app-bg-soft)] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Enter workspace
                </button>
              </div>

              {props.operationMessage ? (
                <div className="mt-5 rounded-2xl border border-emerald-200 bg-emerald-50/90 px-4 py-3 text-sm text-emerald-900">
                  {props.operationMessage}
                </div>
              ) : null}
              {props.operationError ? (
                <div className="mt-5 rounded-2xl border border-rose-200 bg-rose-50/90 px-4 py-3 text-sm text-rose-900">
                  {props.operationError}
                </div>
              ) : null}
              </div>
            </div>
          </div>
        </section>
      </main>
    </div>
  )
}

function App() {
  const autoInboxRefreshStarted = useRef(false)
  const autoSyncedApplicationIds = useRef<Set<string>>(new Set())
  const autoSyncInFlightApplicationIds = useRef<Set<string>>(new Set())
  const documentInputRef = useRef<HTMLInputElement | null>(null)
  const [activeSection, setActiveSection] = useState<AppSection>('overview')
  const [guidedAction, setGuidedAction] = useState<GuidedAction | null>(null)
  const [jobSearch, setJobSearch] = useState('')
  const [jobDescriptionDrafts, setJobDescriptionDrafts] = useState<Record<string, string>>({})
  const [jobOfficialUrlDrafts, setJobOfficialUrlDrafts] = useState<Record<string, string>>({})
  const [applicationJobDescriptionDrafts, setApplicationJobDescriptionDrafts] = useState<Record<string, string>>({})
  const [applicationJobReplyInfo, setApplicationJobReplyInfo] = useState('')
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null)
  const [selectedApplicationId, setSelectedApplicationId] = useState<string | null>(null)
  const [actionFilter, setActionFilter] = useState<ActionFilter>('all')
  const [pipelineSearch, setPipelineSearch] = useState('')
  const [pipelineFilter, setPipelineFilter] = useState<PipelineFilter>('all')
  const [applicationMutating, setApplicationMutating] = useState(false)
  const [actionMutating, setActionMutating] = useState<ActionMutationState>({})
  const [emailMutating, setEmailMutating] = useState<EmailMutationState>({})
  const [operationMutating, setOperationMutating] = useState<Record<string, boolean>>({})
  const [operationMessage, setOperationMessage] = useState<string | null>(
    INITIAL_GMAIL_CONNECTED ? GMAIL_CONNECTED_MESSAGE : null,
  )
  const [operationError, setOperationError] = useState<string | null>(null)
  const [documentSourceType, setDocumentSourceType] = useState('cv')
  const [selectedDocument, setSelectedDocument] = useState<File | null>(null)
  const [selectedGmailCredentialsFile, setSelectedGmailCredentialsFile] = useState<File | null>(
    null,
  )
  const [localDocumentPath, setLocalDocumentPath] = useState(
    'C:\\Users\\Jdela\\OneDrive - University of South Florida\\Escritorio\\resume\\resume\\pdf\\jose_david_gomez_resume_master_full_en.pdf',
  )
  const [emailAgentBatchLimit, setEmailAgentBatchLimit] = useState('8')

  const [jobs, setJobs] = useState<ResourceState<Job[]>>(createInitialResource([]))
  const [applications, setApplications] = useState<ResourceState<Application[]>>(
    createInitialResource([]),
  )
  const [actions, setActions] = useState<ResourceState<Action[]>>(createInitialResource([]))
  const [emails, setEmails] = useState<ResourceState<Email[]>>(createInitialResource([]))
  const [profile, setProfile] = useState<ResourceState<CandidateProfile | null>>(
    createInitialResource<CandidateProfile | null>(null),
  )
  const [documents, setDocuments] = useState<ResourceState<DocumentRecord[]>>(
    createInitialResource([]),
  )
  const [gmailStatusState, setGmailStatusState] = useState<ResourceState<GmailStatus | null>>(
    createInitialResource<GmailStatus | null>(null),
  )
  const [summaries, setSummaries] = useState<ResourceState<NotificationSummary[]>>(
    createInitialResource([]),
  )

  const [selectedJobScores, setSelectedJobScores] = useState<ResourceState<JobScore[]>>(
    createInitialResource([]),
  )
  const [selectedJobCvVersions, setSelectedJobCvVersions] = useState<ResourceState<CVVersion[]>>(
    createInitialResource([]),
  )
  const [selectedJobDrafts, setSelectedJobDrafts] = useState<ResourceState<MessageDraft[]>>(
    createInitialResource([]),
  )
  const [selectedJobResolutionAttempts, setSelectedJobResolutionAttempts] = useState<
    ResourceState<JobDescriptionResolutionAttempt[]>
  >(createInitialResource([]))
  const [selectedJobSemanticMatches, setSelectedJobSemanticMatches] = useState<
    ResourceState<SemanticMatch[]>
  >(createInitialResource([]))
  const [selectedApplicationTracker, setSelectedApplicationTracker] = useState<
    ResourceState<ApplicationTracker | null>
  >(createInitialResource<ApplicationTracker | null>(null))
  const [selectedApplicationActions, setSelectedApplicationActions] = useState<
    ResourceState<Action[]>
  >(createInitialResource([]))
  const [selectedPortalCredentials, setSelectedPortalCredentials] = useState<
    ResourceState<PortalCredential[]>
  >(createInitialResource([]))
  const [selectedStatusChecks, setSelectedStatusChecks] = useState<
    ResourceState<ApplicationStatusCheckEvent[]>
  >(createInitialResource([]))
  const [selectedNoReplyDraft, setSelectedNoReplyDraft] = useState('')
  const [portalCredentialForm, setPortalCredentialForm] = useState<PortalCredentialForm>({
    portal_name: '',
    portal_url: '',
    username: '',
    password: '',
    mfa_enabled: false,
    daily_check_allowed: false,
  })
  const [gmailOAuthPending, setGmailOAuthPending] = useState(false)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    if (params.get('gmail') === 'connected') {
      window.history.replaceState(null, '', window.location.pathname)
    }

    void loadResource<Job[]>('/jobs', setJobs, [])
    void loadResource<Application[]>('/applications', setApplications, [])
    void loadResource<Action[]>('/actions', setActions, [])
    void loadResource<Email[]>('/emails', setEmails, [])
    void loadResource<CandidateProfile | null>('/profile', setProfile, null)
    void loadResource<DocumentRecord[]>('/documents', setDocuments, [])
    void loadResource<GmailStatus | null>('/gmail/status', setGmailStatusState, null)
    void loadResource<NotificationSummary[]>('/notifications/daily-summary', setSummaries, [])
  }, [])

  useEffect(() => {
    if (gmailStatusState.data?.authenticated) {
      setGmailOAuthPending(false)
      return
    }
    const timer = window.setInterval(() => {
      void loadResource<GmailStatus | null>('/gmail/status', setGmailStatusState, null, {
        preserveDataWhileLoading: true,
      })
    }, gmailOAuthPending ? 2000 : 5000)
    return () => window.clearInterval(timer)
  }, [gmailOAuthPending, gmailStatusState.data?.authenticated])

  const effectiveSelectedJobId = selectedJobId ?? jobs.data[0]?.id ?? null
  const effectiveSelectedApplicationId =
    selectedApplicationId ?? applications.data[0]?.id ?? null

  useEffect(() => {
    if (!effectiveSelectedJobId) {
      return
    }

    void loadResource<JobScore[]>(
      `/jobs/${effectiveSelectedJobId}/scores`,
      setSelectedJobScores,
      [],
      { preserveDataWhileLoading: true },
    )
    void loadResource<CVVersion[]>(
      `/jobs/${effectiveSelectedJobId}/cv-tailoring-plans`,
      setSelectedJobCvVersions,
      [],
      { preserveDataWhileLoading: true },
    )
    void loadResource<MessageDraft[]>(
      `/jobs/${effectiveSelectedJobId}/message-drafts`,
      setSelectedJobDrafts,
      [],
      { preserveDataWhileLoading: true },
    )
    void loadResource<SemanticMatch[]>(
      `/jobs/${effectiveSelectedJobId}/semantic-matches`,
      setSelectedJobSemanticMatches,
      [],
      { preserveDataWhileLoading: true },
    )
  }, [effectiveSelectedJobId])

  useEffect(() => {
    if (!effectiveSelectedApplicationId) {
      return
    }

    void loadResource<ApplicationTracker | null>(
      `/applications/${effectiveSelectedApplicationId}`,
      setSelectedApplicationTracker,
      null,
      { preserveDataWhileLoading: true },
    )
    void loadResource<Action[]>(
      `/applications/${effectiveSelectedApplicationId}/actions`,
      setSelectedApplicationActions,
      [],
      { preserveDataWhileLoading: true },
    )
    void loadResource<PortalCredential[]>(
      `/applications/${effectiveSelectedApplicationId}/portal-credentials`,
      setSelectedPortalCredentials,
      [],
      { preserveDataWhileLoading: true },
    )
    void loadResource<ApplicationStatusCheckEvent[]>(
      `/applications/${effectiveSelectedApplicationId}/status-checks`,
      setSelectedStatusChecks,
      [],
      { preserveDataWhileLoading: true },
    )
  }, [effectiveSelectedApplicationId])

  const jobsById = useMemo(() => new Map(jobs.data.map((job) => [job.id, job])), [jobs.data])

  const filteredJobs = useMemo(() => {
    const query = jobSearch.trim().toLowerCase()
    if (!query) {
      return jobs.data
    }

    return jobs.data.filter((job) => {
      const candidate = [
        job.title,
        job.company?.name,
        job.location,
        job.seniority,
        job.work_mode,
        job.source,
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()

      return candidate.includes(query)
    })
  }, [jobSearch, jobs.data])

  const selectedJob = useMemo(
    () => jobs.data.find((job) => job.id === effectiveSelectedJobId) ?? null,
    [effectiveSelectedJobId, jobs.data],
  )
  const selectedJobDescriptionInput = selectedJob
    ? (jobDescriptionDrafts[selectedJob.id] ?? selectedJob.resolved_description ?? selectedJob.description)
    : ''
  const selectedJobOfficialUrlInput = selectedJob ? (jobOfficialUrlDrafts[selectedJob.id] ?? '') : ''
  const selectedJobDescriptionIncomplete = isJobDescriptionIncomplete(selectedJob)
  const selectedJobReviewCandidates = selectedJobResolutionAttempts.data.filter(
    (attempt) => attempt.status === 'needs_manual_review' && attempt.metadata?.candidate_description,
  )
  const latestCvDocument = useMemo(() => {
    return [...documents.data]
      .filter((document) => document.source_type === 'cv')
      .sort((left, right) => right.created_at.localeCompare(left.created_at))[0]
  }, [documents.data])

  const pendingApplications = useMemo(() => {
    return applications.data.filter((application) =>
      ['Found', 'Reviewed', 'CV Generated'].includes(application.status),
    )
  }, [applications.data])

  const openActions = useMemo(() => {
    return actions.data.filter((action) => action.status === 'open')
  }, [actions.data])

  const importantEmails = useMemo(() => {
    return emails.data.filter(
      (email) => email.urgency.toLowerCase() === 'high' || email.requires_reply,
    )
  }, [emails.data])

  const inboxEmails = useMemo(() => {
    const JOB_INBOX_CATEGORIES = [
      'application_confirmation',
      'interview_invitation',
      'coding_assessment',
      'recruiter_follow_up',
      'rejection',
      'offer',
      'documents_requested',
      'form_pending',
    ]
    return emails.data.filter((email) => {
      if (email.application_id) return true
      return JOB_INBOX_CATEGORIES.includes((email.category || '').toLowerCase())
    })
  }, [emails.data])

  const selectedJobScore = selectedJobScores.data[0] ?? null
  const approvedCvCount = selectedJobCvVersions.data.filter(
    (version) => version.status === 'approved',
  ).length
  const approvedDraftCount = selectedJobDrafts.data.filter(
    (draft) => draft.status === 'approved',
  ).length
  const workspaceUnlocked = Boolean(gmailStatusState.data?.authenticated)
  const applicationsByJobId = useMemo(
    () => new Map(applications.data.map((application) => [application.job_id, application])),
    [applications.data],
  )
  const selectedApplication = useMemo(
    () =>
      effectiveSelectedApplicationId
        ? applications.data.find((application) => application.id === effectiveSelectedApplicationId) ?? null
        : null,
    [applications.data, effectiveSelectedApplicationId],
  )
  const selectedApplicationJob = useMemo(
    () => (selectedApplication ? jobsById.get(selectedApplication.job_id) ?? null : null),
    [jobsById, selectedApplication],
  )
  const applicationJobDescriptionInput = selectedApplication
    ? (applicationJobDescriptionDrafts[selectedApplication.id] ?? selectedApplicationJob?.description ?? '')
    : ''
  const selectedApplicationSourceEmail = useMemo(() => {
    if (!effectiveSelectedApplicationId) {
      return null
    }
    return (
      emails.data
        .filter((email) => email.application_id === effectiveSelectedApplicationId)
        .sort((left, right) => {
          const leftTime = left.received_at ? Date.parse(left.received_at) : 0
          const rightTime = right.received_at ? Date.parse(right.received_at) : 0
          return rightTime - leftTime
        })[0] ?? null
    )
  }, [emails.data, effectiveSelectedApplicationId])

  useEffect(() => {
    setPortalCredentialForm({
      portal_name: selectedApplicationJob?.company?.name ?? '',
      portal_url: selectedApplicationJob?.source_url ?? '',
      username: '',
      password: '',
      mfa_enabled: false,
      daily_check_allowed: false,
    })
  }, [selectedApplicationJob?.company?.name, selectedApplicationJob?.source_url])

  const actionsByApplicationId = useMemo(() => {
    const map = new Map<string, Action[]>()
    for (const action of actions.data) {
      const list = map.get(action.application_id) ?? []
      list.push(action)
      map.set(action.application_id, list)
    }
    return map
  }, [actions.data])
  const applicationRows = useMemo(() => {
    const waitingStatuses = new Set(['found', 'reviewed', 'cv generated', 'applied', 'recruiter replied'])
    return applications.data
      .map((application) => {
        const job = jobsById.get(application.job_id)
        const companyLabel = job?.company?.name ?? application.company_name ?? 'Unknown company'
        const titleLabel = job?.title ?? application.job_title ?? 'Unknown role'
        const linkedActions = actionsByApplicationId.get(application.id) ?? []
        const openActions = linkedActions.filter((action) => action.status === 'open')
        const hasNoActions = openActions.length === 0
        const hasActionable = openActions.some((action) => {
          if (action.action_type !== 'respond_to_recruiter' && action.action_type !== 'send_follow_up') return true
          if (!action.email_id) return false
          const linkedEmail = emails.data.find((email) => email.id === action.email_id)
          return !isNoReplySender(linkedEmail?.from_email)
        })
        const hasNoReply = openActions.some((action) => {
          if (action.action_type !== 'respond_to_recruiter' && action.action_type !== 'send_follow_up') return false
          if (!action.email_id) return true
          const linkedEmail = emails.data.find((email) => email.id === action.email_id)
          return isNoReplySender(linkedEmail?.from_email)
        })
        const statusLower = application.status.toLowerCase()
        const isRejected = statusLower === 'rejected'
        const isActive = waitingStatuses.has(statusLower)
        const searchable = `${companyLabel} ${titleLabel} ${application.status}`.toLowerCase()
        return {
          application,
          companyLabel,
          titleLabel,
          hasNoActions,
          hasActionable,
          hasNoReply,
          isRejected,
          isActive,
          searchable,
        }
      })
      .filter((row) => {
        const query = pipelineSearch.trim().toLowerCase()
        if (query && !row.searchable.includes(query)) return false
        if (pipelineFilter === 'active') return row.isActive
        if (pipelineFilter === 'rejected') return row.isRejected
        if (pipelineFilter === 'actionable') return row.hasActionable
        if (pipelineFilter === 'no_action') return row.hasNoActions
        return true
      })
  }, [applications.data, jobsById, actionsByApplicationId, emails.data, pipelineSearch, pipelineFilter])
  const selectedApplicationStatus = (selectedApplicationTracker.data?.status ?? '').toLowerCase()
  const waitingStatuses = new Set(['found', 'reviewed', 'cv generated', 'applied', 'recruiter replied'])
  const appIsRejected = selectedApplicationStatus === 'rejected'
  const appIsWaiting = waitingStatuses.has(selectedApplicationStatus)
  const actionRows = useMemo(() => {
    const rows = selectedApplicationActions.data.map((action) => {
      const linkedEmail = action.email_id ? emails.data.find((email) => email.id === action.email_id) : null
      const blockedReply = Boolean(
        action.status === 'open' &&
          (action.action_type === 'respond_to_recruiter' || action.action_type === 'send_follow_up') &&
          (!action.email_id || isNoReplySender(linkedEmail?.from_email)),
      )
      const actionable = action.status === 'open' && !blockedReply
      return { action, blockedReply, actionable }
    })
    if (actionFilter === 'possible') return rows.filter((row) => row.actionable)
    if (actionFilter === 'blocked') return rows.filter((row) => row.blockedReply)
    if (actionFilter === 'none') return []
    return rows
  }, [selectedApplicationActions.data, emails.data, actionFilter])
  const selectedJobApplication = effectiveSelectedJobId
    ? applicationsByJobId.get(effectiveSelectedJobId) ?? null
    : null
  const selectedApplicationRow = useMemo(
    () => applicationRows.find((row) => row.application.id === effectiveSelectedApplicationId) ?? null,
    [applicationRows, effectiveSelectedApplicationId],
  )
  const profileCompletion = [
    Boolean(gmailStatusState.data?.authenticated),
    Boolean(latestCvDocument),
    Boolean(profile.data),
    Boolean(profile.data?.skills.length),
  ]
  const profileCompletionPercent = Math.round(
    (profileCompletion.filter(Boolean).length / profileCompletion.length) * 100,
  )
  const featuredJobs = jobs.data.slice(0, 4)
  const activeApplications = applications.data.slice(0, 5)
  const homeQuickActions = [
    {
      label: statusLabel(Boolean(latestCvDocument), 'Resume ready', 'Add your resume'),
      note: latestCvDocument
        ? 'Your latest resume is available for profile updates.'
        : 'Start by adding a base resume.',
      cta: latestCvDocument ? 'Open resume setup' : 'Choose a resume file',
      action: () => {
        setGuidedAction('resume-upload')
        setActiveSection('setup')
      },
    },
    {
      label: profile.data ? 'Profile looks ready' : 'Build your profile',
      note: profile.data
        ? 'Skills and experience are already available for matching.'
        : 'Create your profile from your stored resume.',
      cta: profile.data ? 'Review profile' : 'Open profile builder',
      action: () => {
        setGuidedAction('profile-build')
        setActiveSection(profile.data ? 'profile' : 'setup')
      },
    },
    {
      label: jobs.data.length ? 'Review job matches' : 'Find new jobs',
      note: jobs.data.length
        ? 'Open the strongest active opportunities.'
        : 'Run job search to populate your workspace.',
      cta: jobs.data.length ? 'Open job review' : 'Open job search tools',
      action: () => {
        if (featuredJobs.length) {
          setSelectedJobId(featuredJobs[0].id)
          setGuidedAction('job-review')
          setActiveSection('jobs')
          return
        }
        setGuidedAction('job-discovery')
        setActiveSection('setup')
      },
    },
  ]
  const selectedJobSections = selectedJob
    ? extractJobSections(selectedJob.description)
    : { overview: [], responsibilities: [], requirements: [] }
  const selectedJobSalary = selectedJob ? extractSalary(selectedJob.description) : null
  const selectedJobTechnologies = selectedJob
    ? extractTechnologies(selectedJob.description, selectedJobScore)
    : []

  const getEmailApplicationOptions = (email: Email) => {
    const companyNeedle = normalizeForMatch(email.company_name ?? email.from_name)
    const subjectNeedle = normalizeForMatch(email.subject)
    const bodyNeedle = normalizeForMatch(email.snippet ?? email.body_text)

    return [...applications.data].sort((left, right) => {
      const leftJob = jobsById.get(left.job_id)
      const rightJob = jobsById.get(right.job_id)

      const scoreCandidate = (application: Application, job: Job | undefined) => {
        let score = 0
        const companyName = normalizeForMatch(job?.company?.name)
        const title = normalizeForMatch(job?.title)

        if (email.application_id === application.id) {
          score += 100
        }
        if (companyNeedle && companyName && companyNeedle.includes(companyName)) {
          score += 25
        }
        if (companyNeedle && companyName && companyName.includes(companyNeedle)) {
          score += 20
        }
        if (subjectNeedle && title && subjectNeedle.includes(title)) {
          score += 18
        }
        if (bodyNeedle && title && bodyNeedle.includes(title)) {
          score += 12
        }
        if (bodyNeedle && companyName && bodyNeedle.includes(companyName)) {
          score += 8
        }
        return score
      }

      const rightScore = scoreCandidate(right, rightJob)
      const leftScore = scoreCandidate(left, leftJob)

      if (rightScore !== leftScore) {
        return rightScore - leftScore
      }

      return right.updated_at.localeCompare(left.updated_at)
    })
  }

  const runOperation = useCallback(async (label: string, operation: () => Promise<string>) => {
    setOperationMutating((current) => ({ ...current, [label]: true }))
    setOperationError(null)
    setOperationMessage(null)
    try {
      const message = await operation()
      setOperationMessage(message)
    } catch (error) {
      setOperationError(error instanceof Error ? error.message : 'Unexpected operation error')
    } finally {
      setOperationMutating((current) => ({ ...current, [label]: false }))
    }
  }, [])

  async function refreshCoreData() {
    await Promise.all([
      loadResource<Job[]>('/jobs', setJobs, []),
      loadResource<Application[]>('/applications', setApplications, []),
      loadResource<Action[]>('/actions', setActions, []),
      loadResource<Email[]>('/emails', setEmails, []),
      loadResource<CandidateProfile | null>('/profile', setProfile, null),
      loadResource<DocumentRecord[]>('/documents', setDocuments, []),
      loadResource<GmailStatus | null>('/gmail/status', setGmailStatusState, null),
      loadResource<NotificationSummary[]>('/notifications/daily-summary', setSummaries, []),
    ])
  }

  async function refreshSelectedJobArtifacts(jobId: string) {
    await Promise.all([
      loadResource<JobScore[]>(`/jobs/${jobId}/scores`, setSelectedJobScores, []),
      loadResource<CVVersion[]>(
        `/jobs/${jobId}/cv-tailoring-plans`,
        setSelectedJobCvVersions,
        [],
      ),
      loadResource<MessageDraft[]>(`/jobs/${jobId}/message-drafts`, setSelectedJobDrafts, []),
      loadResource<JobDescriptionResolutionAttempt[]>(
        `/jobs/${jobId}/resolution-attempts`,
        setSelectedJobResolutionAttempts,
        [],
      ),
    ])
  }

  async function handleUpdateSelectedJobDescription() {
    const description = selectedJobDescriptionInput.trim()
    if (!effectiveSelectedJobId) {
      setOperationError('Select a job before saving its description.')
      return
    }
    if (description.length < 20) {
      setOperationError('Paste the job description for the selected job before saving it.')
      return
    }

    await runOperation('selected-job-description', async () => {
      const result = await requestApi<ManualJobDescriptionResponse>(
        `/jobs/${effectiveSelectedJobId}/manual-description`,
        {
          method: 'POST',
          body: JSON.stringify({
            description,
          }),
        },
      )
      setSelectedJobId(result.job.id)
      setJobDescriptionDrafts((current) => {
        const next = { ...current }
        delete next[result.job.id]
        return next
      })
      await Promise.all([
        loadResource<Job[]>('/jobs', setJobs, []),
        loadResource<Application[]>('/applications', setApplications, []),
        loadResource<Action[]>('/actions', setActions, []),
      ])
      await refreshSelectedJobArtifacts(result.job.id)
      return `Saved the full job description for ${result.job.title}.`
    })
  }

  async function handleResolveSelectedJobDescription() {
    if (!effectiveSelectedJobId) {
      return
    }

    await runOperation('resolve-job-description', async () => {
      const result = await requestApi<JobDescriptionResolveResponse>(
        `/jobs/${effectiveSelectedJobId}/resolve-description`,
        {
          method: 'POST',
        },
      )
      await Promise.all([
        loadResource<Job[]>('/jobs', setJobs, []),
        loadResource<JobDescriptionResolutionAttempt[]>(
          `/jobs/${effectiveSelectedJobId}/resolution-attempts`,
          setSelectedJobResolutionAttempts,
          [],
        ),
      ])
      await refreshSelectedJobArtifacts(effectiveSelectedJobId)
      return result.status === 'success'
        ? `Resolved description from ${result.description_source ?? 'ATS'} with ${Math.round((result.confidence ?? 0) * 100)}% confidence.`
        : result.notes
    })
  }

  async function handleResolveSelectedJobManualUrl() {
    const url = selectedJobOfficialUrlInput.trim()
    if (!effectiveSelectedJobId || !url) {
      setOperationError('Add an official public job URL before resolving.')
      return
    }

    await runOperation('manual-job-url', async () => {
      const result = await requestApi<ManualJobDescriptionResponse>(
        `/jobs/${effectiveSelectedJobId}/manual-url`,
        {
          method: 'POST',
          body: JSON.stringify({ url }),
        },
      )
      setJobOfficialUrlDrafts((current) => {
        const next = { ...current }
        delete next[result.job.id]
        return next
      })
      await loadResource<Job[]>('/jobs', setJobs, [])
      await refreshSelectedJobArtifacts(result.job.id)
      return `Resolved description from official URL with ${Math.round((result.job.resolution_confidence ?? 0) * 100)}% confidence.`
    })
  }

  async function handleAcceptResolutionCandidate(attemptId: string) {
    if (!effectiveSelectedJobId) return
    await runOperation(`accept-candidate-${attemptId}`, async () => {
      const result = await requestApi<ManualJobDescriptionResponse>(
        `/jobs/${effectiveSelectedJobId}/resolution-attempts/${attemptId}/accept`,
        { method: 'POST' },
      )
      await loadResource<Job[]>('/jobs', setJobs, [])
      await refreshSelectedJobArtifacts(result.job.id)
      return `Accepted candidate description for ${result.job.title}.`
    })
  }

  async function handleRejectResolutionCandidate(attemptId: string) {
    if (!effectiveSelectedJobId) return
    await runOperation(`reject-candidate-${attemptId}`, async () => {
      await requestApi<JobDescriptionResolutionAttempt>(
        `/jobs/${effectiveSelectedJobId}/resolution-attempts/${attemptId}/reject`,
        { method: 'POST' },
      )
      await refreshSelectedJobArtifacts(effectiveSelectedJobId)
      return 'Rejected candidate description.'
    })
  }

  async function handleUpdateApplicationJobDescription() {
    const description = applicationJobDescriptionInput.trim()
    const applicationJobId = selectedApplication?.job_id ?? selectedApplicationJob?.id
    if (!applicationJobId) {
      setOperationError('Select an application with a linked job before saving a description.')
      return
    }
    if (description.length < 20) {
      setOperationError('Paste the job description for this application before saving it.')
      return
    }

    await runOperation('application-job-description', async () => {
      const result = await requestApi<ManualJobDescriptionResponse>(
        `/jobs/${applicationJobId}/manual-description`,
        {
          method: 'POST',
          body: JSON.stringify({
            description,
          }),
        },
      )
      setSelectedJobId(result.job.id)
      setApplicationJobReplyInfo('')
      if (selectedApplication) {
        setApplicationJobDescriptionDrafts((current) => {
          const next = { ...current }
          delete next[selectedApplication.id]
          return next
        })
      }
      await Promise.all([
        loadResource<Job[]>('/jobs', setJobs, []),
        loadResource<Application[]>('/applications', setApplications, []),
        effectiveSelectedApplicationId
          ? loadResource<ApplicationTracker | null>(
              `/applications/${effectiveSelectedApplicationId}`,
              setSelectedApplicationTracker,
              null,
            )
          : Promise.resolve(),
      ])
      await refreshSelectedJobArtifacts(result.job.id)
      return `Saved the full job description under this application for ${result.job.title}.`
    })
  }

  async function handleDeleteSelectedJob() {
    if (!effectiveSelectedJobId || !selectedJob) {
      return
    }

    const confirmed = window.confirm(
      `Remove "${selectedJob.title}" at ${selectedJob.company?.name ?? 'Unknown company'} from your workspace?`,
    )
    if (!confirmed) {
      return
    }

    const nextJobId = filteredJobs.find((job) => job.id !== effectiveSelectedJobId)?.id ?? null

    await runOperation('delete-job', async () => {
      const result = await requestApi<DeleteJobResponse>(`/jobs/${effectiveSelectedJobId}`, {
        method: 'DELETE',
      })
      setSelectedJobId(nextJobId)
      if (!nextJobId) {
        setGuidedAction('job-discovery')
      }
      await Promise.all([
        loadResource<Job[]>('/jobs', setJobs, []),
        loadResource<Application[]>('/applications', setApplications, []),
        loadResource<Action[]>('/actions', setActions, []),
        loadResource<Email[]>('/emails', setEmails, []),
      ])
      return result.message
    })
  }

  async function handleCheckSelectedJobAvailability() {
    if (!effectiveSelectedJobId) {
      return
    }

    await runOperation('availability-check', async () => {
      const updatedJob = await requestApi<Job>(`/jobs/${effectiveSelectedJobId}/availability-check`, {
        method: 'POST',
      })
      await loadResource<Job[]>('/jobs', setJobs, [])
      return `Apply link checked for ${updatedJob.title}. Status: ${formatAvailabilityLabel(updatedJob.availability_status)}.`
    })
  }

  async function handleUploadDocument() {
    if (!selectedDocument) {
      setOperationError('Select your LinkedIn PDF, CV, or LaTeX template first.')
      return
    }

    await runOperation('upload-document', async () => {
      const formData = new FormData()
      formData.append('file', selectedDocument)
      formData.append('source_type', documentSourceType)

      await requestApi<DocumentRecord>('/documents/upload', {
        method: 'POST',
        body: formData,
      })
      setSelectedDocument(null)
      await loadResource<DocumentRecord[]>('/documents', setDocuments, [])
      return documentSourceType === 'cv'
        ? `Uploaded ${selectedDocument.name}. Build profile is ready.`
        : `Uploaded ${selectedDocument.name}.`
    })
  }

  async function handleExtractProfile() {
    await runOperation('extract-profile', async () => {
      if (!latestCvDocument) {
        throw new Error('Add your main resume before building the profile.')
      }
      const extractedProfile = await requestApi<CandidateProfile>('/agents/profile/run', {
        method: 'POST',
        body: JSON.stringify({
          document_id: latestCvDocument.id,
        }),
      })
      await loadResource<CandidateProfile | null>('/profile', setProfile, null)
      return `AI profile agent rebuilt ${cleanDisplayName(extractedProfile.display_name)} using stored documents only.`
    })
  }

  async function handleRunDiscovery() {
    await runOperation('run-discovery', async () => {
      const result = await requestApi<JobDiscoveryResponse>('/job-discovery/run-saved', {
        method: 'POST',
      })
      await Promise.all([
        loadResource<Job[]>('/jobs', setJobs, []),
        loadResource<Application[]>('/applications', setApplications, []),
      ])
      return `Discovery finished: ${result.normalized_jobs_created} new jobs, ${result.deduplicated_jobs} duplicates skipped, ${result.applications_created} applications created, ${result.auto_scored_jobs} auto-scored against your profile.`
    })
  }

  const handleSyncGmail = useCallback(async () => {
    await runOperation('sync-gmail', async () => {
      const syncedEmails = await requestCareerInboxSync()
      await Promise.all([
        loadResource<Email[]>('/emails', setEmails, []),
        loadResource<Job[]>('/jobs', setJobs, []),
        loadResource<Application[]>('/applications', setApplications, []),
        loadResource<Action[]>('/actions', setActions, []),
        loadResource<GmailStatus | null>('/gmail/status', setGmailStatusState, null),
      ])
      return `Inbox refresh finished: ${syncedEmails.length} new career email(s) classified.`
    })
  }, [runOperation])

  async function handleUploadGmailCredentials() {
    if (!selectedGmailCredentialsFile) {
      setOperationError('Choose the Google OAuth JSON file you downloaded from Google Cloud first.')
      return
    }

    await runOperation('gmail-config-upload', async () => {
      const formData = new FormData()
      formData.append('file', selectedGmailCredentialsFile)
      const status = await requestApi<GmailStatus>('/gmail/config/upload', {
        method: 'POST',
        body: formData,
      })
      setSelectedGmailCredentialsFile(null)
      await loadResource<GmailStatus | null>('/gmail/status', setGmailStatusState, null)
      return status.oauth_configured
        ? `Google OAuth JSON saved to ${status.credentials_path}. Continue with Google to finish sign-in.`
        : 'The OAuth file was uploaded, but the backend still does not consider it valid.'
    })
  }

  async function handleStartGmailWebOAuth() {
    await runOperation('gmail-web-oauth', async () => {
      const result = await requestApi<GmailOAuthStart>('/gmail/oauth/start')
      setGmailOAuthPending(true)
      window.open(result.authorization_url, '_blank', 'noopener,noreferrer')
      return `Opening Google sign-in: ${result.redirect_uri}`
    })
  }

  function enterDashboard(section: AppSection = 'overview') {
    if (!gmailStatusState.data?.authenticated) {
      setOperationError('Sign in with Google before opening CareerOps.')
      return
    }
    setActiveSection(section)
    window.history.replaceState(null, '', window.location.pathname)
  }

  async function handleRebuildEmbeddings() {
    await runOperation('rebuild-embeddings', async () => {
      const result = await requestApi<EmbeddingRebuildResponse>(
        '/knowledge-base/embeddings/rebuild',
        {
          method: 'POST',
          body: JSON.stringify({
            include_jobs: true,
            job_limit: 100,
          }),
        },
      )
      if (effectiveSelectedJobId) {
        await loadResource<SemanticMatch[]>(
          `/jobs/${effectiveSelectedJobId}/semantic-matches`,
          setSelectedJobSemanticMatches,
          [],
        )
      }
      return `Embeddings rebuilt: ${result.created_or_updated} updated, ${result.skipped} unchanged, ${result.total_sources} sources checked.`
    })
  }

  async function handleCreateSelectedJobEmbedding() {
    if (!effectiveSelectedJobId) {
      return
    }
    await runOperation('job-embedding', async () => {
      await requestApi(`/jobs/${effectiveSelectedJobId}/embeddings`, { method: 'POST' })
      await loadResource<SemanticMatch[]>(
        `/jobs/${effectiveSelectedJobId}/semantic-matches`,
        setSelectedJobSemanticMatches,
        [],
      )
      return 'Job embedding refreshed. Semantic evidence matches are ready for this role.'
    })
  }

  async function handleSyncLinkedIn() {
    await runOperation('sync-linkedin', async () => {
      const result = await requestApi<LinkedInSyncResponse>('/linkedin/sync', {
        method: 'POST',
        body: JSON.stringify({
          newer_than_days: 90,
          max_results: 50,
        }),
      })
      await Promise.all([
        loadResource<Email[]>('/emails', setEmails, []),
        loadResource<Job[]>('/jobs', setJobs, []),
        loadResource<Application[]>('/applications', setApplications, []),
        loadResource<Action[]>('/actions', setActions, []),
      ])
      return `LinkedIn via Gmail synced: ${result.application_confirmations} application confirmations, ${result.jobs_imported} new jobs, ${result.applications_marked_applied} applied records, ${result.jobs_auto_scored} auto-scored jobs.`
    })
  }

  async function handleImportLocalCvAndRunAiProfileAgent() {
    if (!localDocumentPath.trim()) {
      setOperationError('Paste the full local path to your base CV PDF first.')
      return
    }

    await runOperation('ai-profile-import-run', async () => {
      const importedDocument = await requestApi<DocumentRecord>('/documents/import-local', {
        method: 'POST',
        body: JSON.stringify({
          source_type: 'cv',
          local_path: localDocumentPath.trim(),
        }),
      })

      const extractedProfile = await requestApi<CandidateProfile>('/agents/profile/run', {
        method: 'POST',
        body: JSON.stringify({
          document_id: importedDocument.id,
        }),
      })

      await refreshCoreData()
      return `AI profile agent ran on ${importedDocument.original_filename} and rebuilt the profile for ${cleanDisplayName(extractedProfile.display_name)}.`
    })
  }

  async function handleRunAiProfileAgentOnLatestCv() {
    if (!latestCvDocument) {
      setOperationError('Upload or import a CV document first, then run the AI profile agent.')
      return
    }

    await runOperation('ai-profile-latest-cv', async () => {
      const extractedProfile = await requestApi<CandidateProfile>('/agents/profile/run', {
        method: 'POST',
        body: JSON.stringify({
          document_id: latestCvDocument.id,
        }),
      })

      await refreshCoreData()
      return `AI profile agent refreshed ${cleanDisplayName(extractedProfile.display_name)} from ${latestCvDocument.original_filename}.`
    })
  }

  async function handleRunAiEmailTriage() {
    const parsedLimit = Number.parseInt(emailAgentBatchLimit, 10)
    if (Number.isNaN(parsedLimit) || parsedLimit < 1 || parsedLimit > 25) {
      setOperationError('Choose a small AI email batch between 1 and 25.')
      return
    }

    await runOperation('ai-email-triage', async () => {
      const triagedEmails = await requestApi<Email[]>('/agents/emails/triage-unlinked', {
        method: 'POST',
        body: JSON.stringify({
          limit: parsedLimit,
        }),
      })

      await Promise.all([
        loadResource<Email[]>('/emails', setEmails, []),
        loadResource<Application[]>('/applications', setApplications, []),
        loadResource<Action[]>('/actions', setActions, []),
      ])
      return `AI email triage reviewed ${triagedEmails.length} unlinked emails using the low-cost inbox model.`
    })
  }

  async function handleReclassifyEmails() {
    await runOperation('reclassify-emails', async () => {
      const updatedEmails = await requestApi<Email[]>('/emails/reclassify', {
        method: 'POST',
      })
      await Promise.all([
        loadResource<Email[]>('/emails', setEmails, []),
        loadResource<Job[]>('/jobs', setJobs, []),
        loadResource<Application[]>('/applications', setApplications, []),
      ])
      return `Reclassified ${updatedEmails.length} emails for the work inbox.`
    })
  }

  async function handleGenerateDailySummary() {
    await runOperation('daily-summary', async () => {
      await requestApi<NotificationSummary>('/notifications/daily-summary', {
        method: 'POST',
      })
      await loadResource<NotificationSummary[]>('/notifications/daily-summary', setSummaries, [])
      return 'Daily summary regenerated from jobs, applications, inbox, and actions.'
    })
  }

  async function handleScoreSelectedJob() {
    if (!effectiveSelectedJobId) {
      return
    }

    await runOperation('score-job', async () => {
      const score = await requestApi<JobScore>(`/jobs/${effectiveSelectedJobId}/score`, {
        method: 'POST',
      })
      await refreshSelectedJobArtifacts(effectiveSelectedJobId)
      return `Job scored: ${score.score} with recommendation ${score.recommendation}.`
    })
  }

  async function handleCreateCvPlan() {
    if (!effectiveSelectedJobId) {
      return
    }

    await runOperation('cv-plan', async () => {
      const version = await requestApi<CVVersion>(
        `/jobs/${effectiveSelectedJobId}/cv-tailoring-plan`,
        {
          method: 'POST',
        },
      )
      await refreshSelectedJobArtifacts(effectiveSelectedJobId)
      return `CV tailoring plan ${version.id.slice(0, 8)} created for human review using ${version.tailoring_plan.planner ?? 'the current planner'}.`
    })
  }

  async function handleGenerateFinalCv() {
    if (!effectiveSelectedJobId) {
      return
    }

    const cvVersion = selectedJobCvVersions.data[0]
    if (!cvVersion) {
      setOperationError('Create a CV tailoring plan before generating the final LaTeX file.')
      return
    }

    await runOperation('final-cv', async () => {
      const finalVersion = await requestApi<CVVersion>(
        `/cv-versions/${cvVersion.id}/final-latex`,
        {
          method: 'POST',
        },
      )
      await refreshSelectedJobArtifacts(effectiveSelectedJobId)
      return finalVersion.tailoring_plan.generated_pdf_path
        ? `Final CV generated as LaTeX and PDF.`
        : `Final LaTeX CV generated. PDF was not produced: ${finalVersion.tailoring_plan.pdf_generation_error ?? 'compiler unavailable'}`
    })
  }

  async function handleGenerateMessageDrafts() {
    if (!effectiveSelectedJobId) {
      return
    }

    await runOperation('message-drafts', async () => {
      const drafts = await requestApi<MessageDraft[]>(
        `/jobs/${effectiveSelectedJobId}/message-drafts`,
        {
          method: 'POST',
          body: JSON.stringify({
            draft_types: ['linkedin', 'application_email', 'short_cover_letter'],
            tone: 'natural-professional',
            language: 'english',
          }),
        },
      )
      await refreshSelectedJobArtifacts(effectiveSelectedJobId)
      return `${drafts.length} message drafts generated for human review.`
    })
  }

  async function refreshApplicationViews(applicationId: string) {
    await Promise.all([
      loadResource<Application[]>('/applications', setApplications, [], {
        preserveDataWhileLoading: true,
      }),
      loadResource<Action[]>('/actions', setActions, [], {
        preserveDataWhileLoading: true,
      }),
      loadResource<ApplicationTracker | null>(
        `/applications/${applicationId}`,
        setSelectedApplicationTracker,
        null,
        { preserveDataWhileLoading: true },
      ),
      loadResource<Action[]>(
        `/applications/${applicationId}/actions`,
        setSelectedApplicationActions,
        [],
        { preserveDataWhileLoading: true },
      ),
      loadResource<PortalCredential[]>(
        `/applications/${applicationId}/portal-credentials`,
        setSelectedPortalCredentials,
        [],
        { preserveDataWhileLoading: true },
      ),
      loadResource<ApplicationStatusCheckEvent[]>(
        `/applications/${applicationId}/status-checks`,
        setSelectedStatusChecks,
        [],
        { preserveDataWhileLoading: true },
      ),
    ])
  }

  async function handleDeleteSelectedApplication() {
    if (!effectiveSelectedApplicationId || !selectedApplicationTracker.data) {
      return
    }

    const confirmed = window.confirm(
      `Remove this application from ${selectedApplicationTracker.data.company_name ?? 'Unknown company'}?`,
    )
    if (!confirmed) {
      return
    }

    const nextApplicationId =
      applicationRows.find((row) => row.application.id !== effectiveSelectedApplicationId)?.application.id ?? null

    await runOperation('delete-application', async () => {
      const result = await requestApi<DeleteApplicationResponse>(
        `/applications/${effectiveSelectedApplicationId}`,
        {
          method: 'DELETE',
        },
      )
      setSelectedApplicationId(nextApplicationId)
      await Promise.all([
        loadResource<Application[]>('/applications', setApplications, []),
        loadResource<Action[]>('/actions', setActions, []),
        loadResource<Email[]>('/emails', setEmails, []),
      ])
      return result.message
    })
  }

  async function handleMarkApplied() {
    if (!effectiveSelectedApplicationId) {
      return
    }

    setApplicationMutating(true)
    try {
      await requestApi<ApplicationTracker>(
        `/applications/${effectiveSelectedApplicationId}/mark-applied`,
        {
          method: 'PATCH',
          body: JSON.stringify({
            notes: 'Applied manually from the dashboard after human review.',
          }),
        },
      )
      await refreshApplicationViews(effectiveSelectedApplicationId)
    } finally {
      setApplicationMutating(false)
    }
  }

  async function handleSyncNextActions() {
    if (!effectiveSelectedApplicationId) {
      return
    }

    setApplicationMutating(true)
    try {
      await requestApi(`/applications/${effectiveSelectedApplicationId}/next-actions/sync`, {
        method: 'POST',
      })
      await refreshApplicationViews(effectiveSelectedApplicationId)
    } finally {
      setApplicationMutating(false)
    }
  }

  async function handleSavePortalCredential() {
    if (!effectiveSelectedApplicationId) {
      return
    }
    if (!portalCredentialForm.portal_name.trim() || !portalCredentialForm.portal_url.trim()) {
      setOperationError('Add the portal name and URL before saving credentials.')
      return
    }
    if (!portalCredentialForm.username.trim() || !portalCredentialForm.password) {
      setOperationError('Add the portal username/email and password before saving credentials.')
      return
    }

    await runOperation('portal-credential-save', async () => {
      await requestApi<PortalCredential>(
        `/applications/${effectiveSelectedApplicationId}/portal-credentials`,
        {
          method: 'POST',
          body: JSON.stringify(portalCredentialForm),
        },
      )
      await loadResource<PortalCredential[]>(
        `/applications/${effectiveSelectedApplicationId}/portal-credentials`,
        setSelectedPortalCredentials,
        [],
        { preserveDataWhileLoading: true },
      )
      setPortalCredentialForm((current) => ({
        ...current,
        username: '',
        password: '',
        daily_check_allowed: false,
      }))
      return 'Portal credentials saved securely. Passwords are not returned to the app UI.'
    })
  }

  async function handleDeleteDocument(document: DocumentRecord) {
    await runOperation(`delete-document-${document.id}`, async () => {
      await requestApi(`/documents/${document.id}`, { method: 'DELETE' })
      await Promise.all([
        loadResource<DocumentRecord[]>('/documents', setDocuments, []),
        loadResource<CandidateProfile | null>('/profile', setProfile, null),
      ])
      return `Deleted ${document.original_filename}. You can rebuild the profile from another resume.`
    })
  }

  async function handleDeletePortalCredential(credentialId: string) {
    if (!effectiveSelectedApplicationId) {
      return
    }
    await runOperation(`portal-credential-delete-${credentialId}`, async () => {
      await requestApi(`/portal-credentials/${credentialId}`, { method: 'DELETE' })
      await loadResource<PortalCredential[]>(
        `/applications/${effectiveSelectedApplicationId}/portal-credentials`,
        setSelectedPortalCredentials,
        [],
        { preserveDataWhileLoading: true },
      )
      return 'Portal credential deleted.'
    })
  }

  async function handleRunPortalStatusCheck() {
    if (!effectiveSelectedApplicationId) {
      return
    }
    await runOperation('portal-status-check', async () => {
      const event = await requestApi<ApplicationStatusCheckEvent>(
        `/applications/${effectiveSelectedApplicationId}/status-checks/run`,
        { method: 'POST' },
      )
      await refreshApplicationViews(effectiveSelectedApplicationId)
      return `Portal status checked: ${event.new_status} (${event.confidence}).`
    })
  }

  async function handleGeneratePortalFollowUpDraft() {
    if (!effectiveSelectedApplicationId) {
      return
    }
    await runOperation('portal-follow-up-draft', async () => {
      const draft = await requestApi<MessageDraft>(
        `/applications/${effectiveSelectedApplicationId}/portal-follow-up-draft`,
        { method: 'POST' },
      )
      const fallbackText = (draft as MessageDraft & { rendered_text?: string }).rendered_text ?? ''
      setSelectedNoReplyDraft((draft.body ?? fallbackText).trim())
      if (selectedApplicationJob?.id) {
        await refreshSelectedJobArtifacts(selectedApplicationJob.id)
      }
      return `Follow-up draft created for review: ${draft.subject ?? 'No subject'}`
    })
  }

  async function handleCopyNoReplyDraft() {
    if (!selectedNoReplyDraft.trim()) {
      setOperationError('Generate a no-reply draft first.')
      return
    }
    try {
      await navigator.clipboard.writeText(selectedNoReplyDraft)
      setOperationMessage('Draft copied. Paste it when you find a recruiter/HR contact.')
    } catch {
      setOperationError('Clipboard access failed. Copy manually from the text box.')
    }
  }

  async function handleCreateGmailReplyDraft(emailId: string) {
    setEmailMutating((current) => ({ ...current, [emailId]: true }))
    setOperationError(null)
    try {
      const emailRecord = emails.data.find((email) => email.id === emailId) ?? null
      if (emailRecord && isNoReplySender(emailRecord.from_email)) {
        setOperationError('Reply blocked: this sender is no-reply. Link a recruiter/HR email instead.')
        return
      }
      await requestApi(`/emails/${emailId}/draft-reply`, {
        method: 'POST',
        body: JSON.stringify({
          create_gmail_draft: true,
        }),
      })
      const threadUrl = emailRecord ? gmailThreadUrl(emailRecord) : null
      window.open(threadUrl ?? 'https://mail.google.com/mail/u/0/#drafts', '_blank', 'noopener,noreferrer')
      setOperationMessage('Gmail draft created. Gmail was opened to continue editing/sending.')
      await Promise.all([
        loadResource<Email[]>('/emails', setEmails, [], { preserveDataWhileLoading: true }),
        loadResource<Action[]>('/actions', setActions, [], { preserveDataWhileLoading: true }),
      ])
      if (effectiveSelectedApplicationId) {
        await refreshApplicationViews(effectiveSelectedApplicationId)
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to create Gmail draft.'
      setOperationError(message)
    } finally {
      setEmailMutating((current) => ({ ...current, [emailId]: false }))
    }
  }

  async function autoSyncNextActions(applicationId: string) {
    if (autoSyncedApplicationIds.current.has(applicationId)) {
      return
    }
    if (autoSyncInFlightApplicationIds.current.has(applicationId)) {
      return
    }

    autoSyncInFlightApplicationIds.current.add(applicationId)
    try {
      await requestApi(`/applications/${applicationId}/next-actions/sync`, {
        method: 'POST',
      })
      autoSyncedApplicationIds.current.add(applicationId)
      await refreshApplicationViews(applicationId)
    } finally {
      autoSyncInFlightApplicationIds.current.delete(applicationId)
    }
  }

  async function handleUpdateAction(actionId: string, status: 'completed' | 'dismissed') {
    setActionMutating((current) => ({ ...current, [actionId]: true }))
    try {
      await requestApi<Action>(`/actions/${actionId}`, {
        method: 'PATCH',
        body: JSON.stringify({
          status,
          notes:
            status === 'completed'
              ? 'Updated from dashboard.'
              : 'Dismissed from dashboard.',
        }),
      })

      if (effectiveSelectedApplicationId) {
        await refreshApplicationViews(effectiveSelectedApplicationId)
      } else {
        await Promise.all([
          loadResource<Application[]>('/applications', setApplications, []),
          loadResource<Action[]>('/actions', setActions, []),
        ])
      }
    } finally {
      setActionMutating((current) => ({ ...current, [actionId]: false }))
    }
  }

  async function handleLinkEmail(emailId: string, applicationId: string) {
    setEmailMutating((current) => ({ ...current, [emailId]: true }))
    try {
      await requestApi<Email>(`/emails/${emailId}/link`, {
        method: 'PATCH',
        body: JSON.stringify({
          application_id: applicationId || null,
          sync_next_actions: true,
        }),
      })

      if (applicationId) {
        setSelectedApplicationId(applicationId)
      }

      await Promise.all([
        loadResource<Email[]>('/emails', setEmails, []),
        loadResource<Application[]>('/applications', setApplications, []),
        loadResource<Action[]>('/actions', setActions, []),
      ])

      if (applicationId) {
        await refreshApplicationViews(applicationId)
      } else if (effectiveSelectedApplicationId) {
        await refreshApplicationViews(effectiveSelectedApplicationId)
      }
    } finally {
      setEmailMutating((current) => ({ ...current, [emailId]: false }))
    }
  }

  useEffect(() => {
    if (!gmailStatusState.data?.authenticated || autoInboxRefreshStarted.current) {
      return
    }
    autoInboxRefreshStarted.current = true
    const timer = window.setTimeout(() => {
      void handleSyncGmail()
    }, 600)
    return () => window.clearTimeout(timer)
  }, [gmailStatusState.data?.authenticated, handleSyncGmail])

  useEffect(() => {
    if (!workspaceUnlocked || !effectiveSelectedApplicationId) {
      return
    }
    void autoSyncNextActions(effectiveSelectedApplicationId)
  }, [workspaceUnlocked, effectiveSelectedApplicationId])

  if (!workspaceUnlocked) {
    return (
      <SetupHome
        gmailStatus={gmailStatusState}
        profile={profile}
        documents={documents}
        operationMessage={operationMessage}
        operationError={operationError}
        gmailConnecting={Boolean(operationMutating['gmail-web-oauth'])}
        gmailConfiguring={Boolean(operationMutating['gmail-config-upload'])}
        selectedGmailCredentialsFile={selectedGmailCredentialsFile}
        onSelectGmailCredentialsFile={setSelectedGmailCredentialsFile}
        onUploadGmailCredentials={() => void handleUploadGmailCredentials()}
        onConnectGmail={() => void handleStartGmailWebOAuth()}
        onOpenSetup={() => enterDashboard('setup')}
        onEnterDashboard={() => enterDashboard('overview')}
      />
    )
  }

  return (
    <div className="min-h-screen text-[color:var(--app-ink)]">
      <div className="mx-auto flex min-h-screen max-w-[1720px] flex-col gap-4 px-4 py-4 lg:px-5">
        <header className="overflow-hidden rounded-xl border border-[color:var(--app-border)] bg-[#151815] px-5 py-4 text-white shadow-[0_12px_36px_rgba(24,27,24,0.14)]">
          <div className="pointer-events-none absolute hidden" />
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="space-y-1">
              <p className="text-[0.68rem] font-semibold uppercase tracking-[0.12em] text-[#8fd4ce]">
                CareerOps Agent
              </p>
              <h1 className="text-2xl font-semibold tracking-tight text-white md:text-[1.9rem]">
                Hiring pipeline, edited like a dossier.
              </h1>
              <p className="max-w-3xl text-sm leading-6 text-stone-300">
                Review job discovery, active applications, recruiter inbox signals, profile evidence, CV drafts, and next actions from one private workspace.
              </p>
            </div>
            <div className="flex flex-col gap-3 lg:min-w-[560px]">
              <div className="rounded-lg border border-white/10 bg-white/10 p-3">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="text-[0.68rem] font-semibold uppercase tracking-[0.1em] text-stone-400">Google</p>
                    <p className="mt-1 text-sm font-semibold text-white">
                      {gmailStatusState.data?.authenticated ? 'Connected' : 'Sign-in required'}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => void handleStartGmailWebOAuth()}
                      disabled={
                        operationMutating['gmail-web-oauth'] ||
                        !gmailStatusState.data?.oauth_configured
                      }
                      className="crm-button bg-[color:var(--app-bg-soft)] text-xs text-[color:var(--app-ink)] hover:bg-white disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {gmailStatusState.data?.authenticated ? 'Reconnect' : 'Continue with Google'}
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleSyncGmail()}
                      disabled={
                        operationMutating['sync-gmail'] ||
                        !gmailStatusState.data?.authenticated
                      }
                      className="crm-button border border-white/20 bg-white/10 text-xs text-white hover:bg-white/15 disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      {operationMutating['sync-gmail'] ? 'Refreshing...' : 'Refresh inbox'}
                    </button>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
                <MetricCard
                  label="Jobs"
                  value={jobs.data.length}
                  note={`${selectedJobScores.data.length} score records visible for selected job`}
                />
                <MetricCard
                  label="Applications"
                  value={applications.data.length}
                  note={`${pendingApplications.length} still in pre-submit or review`}
                />
                <MetricCard
                  label="Urgent inbox"
                  value={importantEmails.length}
                  note={`${openActions.length} open actions currently tracked`}
                />
              </div>
            </div>
          </div>
        </header>

        <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-[260px_minmax(0,1fr)]">
          <aside className="self-start rounded-xl border border-[color:var(--app-border)] bg-[color:var(--app-surface)] p-3 shadow-[0_10px_32px_rgba(24,27,24,0.05)] lg:sticky lg:top-4">
            <div className="mb-4 rounded-lg bg-[color:var(--app-bg-soft)] p-3 ring-1 ring-[color:var(--app-border)]">
              <p className="crm-label">
                Workspace
              </p>
              <p className="mt-1 text-lg font-semibold text-[color:var(--app-ink)]">
                Operations
              </p>
              <p className="mt-2 text-sm leading-6 text-[color:var(--app-muted)]">
                Move from evidence to application without leaving the desktop shell.
              </p>
            </div>
            <nav className="flex flex-col gap-1">
              {DEFAULT_SECTIONS.map((section) => (
                <SectionButton
                  key={section.id}
                  active={section.id === activeSection}
                  label={section.label}
                  badge={section.id === 'applications' ? applications.data.length : undefined}
                  onClick={() => setActiveSection(section.id)}
                />
              ))}
            </nav>

            <div className="mt-4 rounded-lg border border-[color:var(--app-border)] bg-[color:var(--app-bg-soft)] p-3">
              <p className="crm-label">
                Current profile
              </p>
              <p className="mt-2 text-base font-semibold text-[color:var(--app-ink)]">
                {cleanDisplayName(profile.data?.display_name)}
              </p>
              <p className="mt-1 text-sm leading-6 text-[color:var(--app-muted)]">
                {profile.data?.headline
                  ? cleanDisplayText(profile.data.headline)
                  : 'Waiting for profile extraction'}
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                <span className="rounded-md bg-white px-2 py-1 text-xs text-[color:var(--app-muted)] ring-1 ring-[color:var(--app-border)]">
                  {profile.data?.skills.length ?? 0} skills
                </span>
                <span className="rounded-md bg-white px-2 py-1 text-xs text-[color:var(--app-muted)] ring-1 ring-[color:var(--app-border)]">
                  {profile.data?.projects.length ?? 0} projects
                </span>
                <span className="rounded-md bg-white px-2 py-1 text-xs text-[color:var(--app-muted)] ring-1 ring-[color:var(--app-border)]">
                  {profile.data?.experiences.length ?? 0} experiences
                </span>
              </div>
            </div>
          </aside>

          <main className="min-w-0 space-y-4">
            {operationMessage ? (
              <div className="rounded-2xl border border-emerald-200 bg-emerald-50/90 px-4 py-3 text-sm text-emerald-900 shadow-[0_14px_30px_rgba(16,185,129,0.08)]">
                {operationMessage}
              </div>
            ) : null}
            {operationError ? (
              <div className="rounded-2xl border border-rose-200 bg-rose-50/90 px-4 py-3 text-sm text-rose-900 shadow-[0_14px_30px_rgba(180,35,24,0.08)]">
                {operationError}
              </div>
            ) : null}

            {activeSection === 'overview' ? (
              <>
                <div className="grid gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(340px,0.95fr)]">
                  <Panel
                    title="Home"
                    subtitle="A simpler daily view of what matters now: promising jobs, application progress, and the next move to make."
                  >
                    <ResourceBanner title="Daily summary" state={summaries} />
                    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                      <MetricCard
                        label="Fresh jobs"
                        value={jobs.data.length}
                        note="Live opportunities currently in the workspace"
                      />
                      <MetricCard
                        label="Active applications"
                        value={applications.data.length}
                        note="Roles you are tracking beyond discovery"
                      />
                      <MetricCard
                        label="Next actions"
                        value={openActions.length}
                        note="Follow-ups, interviews, and submission steps"
                      />
                      <MetricCard
                        label="Profile ready"
                        value={`${profileCompletionPercent}%`}
                        note="Resume, profile, and skills completeness"
                      />
                    </div>

                    <div className="mt-6 grid gap-4 xl:grid-cols-2">
                      {featuredJobs.length ? (
                        featuredJobs.map((job) => {
                          const linkedApplication = applicationsByJobId.get(job.id)
                          return (
                            <button
                              key={job.id}
                              type="button"
                              onClick={() => {
                                setSelectedJobId(job.id)
                                setActiveSection('jobs')
                              }}
                              className="rounded-[1.4rem] border border-[color:var(--app-border)] bg-[linear-gradient(180deg,#fffdf9,#f7f1e8)] p-4 text-left shadow-[0_14px_30px_rgba(23,23,23,0.04)] transition hover:-translate-y-0.5 hover:shadow-[0_18px_38px_rgba(23,23,23,0.08)]"
                            >
                              <div className="flex items-start justify-between gap-3">
                                <div>
                                  <p className="text-sm font-medium text-[color:var(--app-ink)]">
                                    {job.company?.name ?? 'Unknown company'}
                                  </p>
                                  <p className="mt-1 text-base font-semibold text-[color:var(--app-ink)]">
                                    {job.title}
                                  </p>
                                </div>
                                <span className="rounded-full bg-white px-2.5 py-1 text-xs text-[color:var(--app-muted)] ring-1 ring-[color:var(--app-border)]">
                                  {linkedApplication?.status ?? 'New'}
                                </span>
                              </div>
                              <p className="mt-2 text-sm text-[color:var(--app-muted)]">
                                {[job.location ?? 'Location not listed', job.work_mode ?? 'Work style not listed']
                                  .filter(Boolean)
                                  .join(' • ')}
                              </p>
                              <p className="mt-3 text-sm leading-6 text-[color:var(--app-muted)]">
                                {truncate(cleanDisplayText(job.description), 170)}
                              </p>
                            </button>
                          )
                        })
                      ) : (
                        <EmptyState
                          title="No job opportunities yet"
                          body="Use Find new jobs in Settings to bring opportunities into the workspace."
                        />
                      )}
                    </div>
                  </Panel>

                  <Panel
                    title="Quick actions"
                    subtitle="Only the smallest set of actions needed to keep the pipeline moving."
                  >
                    <div className="space-y-3">
                      {homeQuickActions.map((item) => (
                        <button
                          key={item.label}
                          type="button"
                          onClick={item.action}
                          className="w-full rounded-[1.25rem] border border-[color:var(--app-border)] bg-[color:var(--app-bg-soft)] p-4 text-left transition hover:bg-white hover:shadow-[0_12px_24px_rgba(23,23,23,0.06)]"
                        >
                          <p className="text-sm font-semibold text-[color:var(--app-ink)]">{item.label}</p>
                          <p className="mt-1 text-sm leading-6 text-[color:var(--app-muted)]">{item.note}</p>
                          <p className="mt-3 text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--app-accent)]">
                            {item.cta}
                          </p>
                        </button>
                      ))}
                    </div>

                    <div className="mt-6 rounded-[1.35rem] border border-[color:var(--app-border)] bg-[linear-gradient(180deg,#fffdf8,#f5efe5)] p-4">
                      <p className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[color:var(--app-muted)]">
                        Profile completion
                      </p>
                      <p className="mt-2 font-serif text-3xl font-semibold text-[color:var(--app-ink)]">
                        {profileCompletionPercent}%
                      </p>
                      <div className="mt-3 h-2 overflow-hidden rounded-full bg-white/80 ring-1 ring-[color:var(--app-border)]">
                        <div
                          className="h-full rounded-full bg-[color:var(--app-accent)] transition-all"
                          style={{ width: `${profileCompletionPercent}%` }}
                        />
                      </div>
                      <div className="mt-4 grid gap-2">
                        <p className="text-sm text-[color:var(--app-muted)]">
                          Google: {statusLabel(Boolean(gmailStatusState.data?.authenticated), 'connected', 'not connected')}
                        </p>
                        <p className="text-sm text-[color:var(--app-muted)]">
                          Resume: {statusLabel(Boolean(latestCvDocument), 'ready', 'missing')}
                        </p>
                        <p className="text-sm text-[color:var(--app-muted)]">
                          Profile: {statusLabel(Boolean(profile.data), 'built', 'not built yet')}
                        </p>
                        <p className="text-sm text-[color:var(--app-muted)]">
                          Skills: {profile.data?.skills.length ?? 0} verified
                        </p>
                      </div>
                    </div>
                  </Panel>
                </div>

                <div className="grid gap-6 xl:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
                  <Panel
                    title="Application progress"
                    subtitle="A compact view of the applications that still need attention."
                  >
                    {activeApplications.length ? (
                      <div className="space-y-3">
                        {activeApplications.map((application) => {
                          const job = jobsById.get(application.job_id)
                          return (
                            <button
                              key={application.id}
                              type="button"
                              onClick={() => {
                                setSelectedApplicationId(application.id)
                                setActiveSection('applications')
                              }}
                              className="w-full rounded-[1.3rem] border border-[color:var(--app-border)] bg-white/90 p-4 text-left transition hover:-translate-y-0.5 hover:shadow-[0_12px_24px_rgba(23,23,23,0.06)]"
                            >
                              <div className="flex items-start justify-between gap-3">
                                <div>
                                  <p className="text-sm font-medium text-[color:var(--app-ink)]">
                                    {job?.company?.name ?? 'Unknown company'}
                                  </p>
                                  <p className="mt-1 text-sm text-[color:var(--app-muted)]">
                                    {job?.title ?? 'Unknown role'}
                                  </p>
                                </div>
                                <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${getStatusTone(application.status)}`}>
                                  {application.status}
                                </span>
                              </div>
                              <p className="mt-3 text-sm text-[color:var(--app-muted)]">
                                {application.applied_at
                                  ? `Applied ${formatDate(application.applied_at)}`
                                  : `Updated ${formatRelativeDate(application.updated_at)}`}
                              </p>
                            </button>
                          )
                        })}
                      </div>
                    ) : (
                      <EmptyState
                        title="No active applications yet"
                        body="As soon as you track a role beyond discovery, it will appear here."
                      />
                    )}
                  </Panel>

                  <Panel
                    title="Upcoming actions"
                    subtitle="The next interviews, replies, or follow-ups worth handling now."
                  >
                    <ResourceBanner title="Actions" state={actions} />
                    {openActions.length ? (
                      <div className="space-y-3">
                        {openActions.slice(0, 4).map((action) => {
                          const application = applications.data.find(
                            (candidate) => candidate.id === action.application_id,
                          )
                          const job = application ? jobsById.get(application.job_id) : null
                          return (
                            <article
                              key={action.id}
                              className="rounded-[1.25rem] border border-[color:var(--app-border)] bg-[color:var(--app-bg-soft)] p-4"
                            >
                              <div className="flex items-center justify-between gap-3">
                                <p className="text-sm font-medium text-[color:var(--app-ink)]">{action.title}</p>
                                <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${getPriorityTone(action.priority)}`}>
                                  {action.priority}
                                </span>
                              </div>
                              <p className="mt-1 text-sm text-[color:var(--app-muted)]">
                                {job?.company?.name ?? 'Unknown company'} - {job?.title ?? 'Unknown role'}
                              </p>
                              <p className="mt-3 text-sm leading-6 text-[color:var(--app-muted)]">
                                {truncate(action.details, 140)}
                              </p>
                            </article>
                          )
                        })}
                      </div>
                    ) : (
                      <EmptyState
                        title="Nothing urgent right now"
                        body="When interviews, follow-ups, or submission tasks need attention, they will appear here."
                      />
                    )}
                  </Panel>
                </div>
              </>
            ) : null}

            {activeSection === 'setup' ? (
              <div className="space-y-6">
                {guidedAction === 'resume-upload' || guidedAction === 'profile-build' || guidedAction === 'job-discovery' ? (
                  <div className="rounded-[1.45rem] border border-[color:var(--app-border)] bg-[linear-gradient(135deg,#fffdf8,#eef6f3)] p-5 shadow-[0_14px_32px_rgba(23,23,23,0.05)]">
                    <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                      <div>
                        <p className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[color:var(--app-muted)]">
                          Guided action
                        </p>
                        <p className="mt-2 text-lg font-semibold text-[color:var(--app-ink)]">
                          {guidedAction === 'resume-upload'
                            ? 'Add or update your main resume'
                            : guidedAction === 'profile-build'
                              ? 'Build your profile from the latest resume'
                              : 'Search for fresh jobs'}
                        </p>
                        <p className="mt-2 text-sm leading-6 text-[color:var(--app-muted)]">
                          {guidedAction === 'resume-upload'
                            ? 'Use the resume controls below to choose a file and add it to the workspace.'
                            : guidedAction === 'profile-build'
                              ? 'This creates the profile used for fit checks, tailored resumes, and outreach.'
                              : 'Run job discovery from here, then return to Jobs to review the new roles.'}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-3">
                        {guidedAction === 'resume-upload' ? (
                          <button
                            type="button"
                            onClick={() => documentInputRef.current?.click()}
                            className="rounded-2xl bg-[color:var(--app-ink)] px-4 py-2 text-sm font-medium text-white transition hover:opacity-92"
                          >
                            Choose resume file
                          </button>
                        ) : null}
                        {guidedAction === 'profile-build' ? (
                          <button
                            type="button"
                            onClick={() => void handleExtractProfile()}
                            disabled={operationMutating['extract-profile'] || !latestCvDocument}
                            className="rounded-2xl bg-[color:var(--app-ink)] px-4 py-2 text-sm font-medium text-white transition hover:opacity-92 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {operationMutating['extract-profile'] ? 'Building profile...' : 'Build profile now'}
                          </button>
                        ) : null}
                        {guidedAction === 'job-discovery' ? (
                          <button
                            type="button"
                            onClick={() => void handleRunDiscovery()}
                            disabled={operationMutating['run-discovery']}
                            className="rounded-2xl bg-[color:var(--app-ink)] px-4 py-2 text-sm font-medium text-white transition hover:opacity-92 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {operationMutating['run-discovery'] ? 'Looking for jobs...' : 'Find new jobs now'}
                          </button>
                        ) : null}
                        <button
                          type="button"
                          onClick={() => setGuidedAction(null)}
                          className="rounded-2xl border border-[color:var(--app-border-strong)] bg-white px-4 py-2 text-sm font-medium text-[color:var(--app-ink)] transition hover:bg-[color:var(--app-bg-soft)]"
                        >
                          Dismiss
                        </button>
                      </div>
                    </div>
                  </div>
                ) : null}

                <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                <Panel
                  title="Resume and profile"
                  subtitle="Add your main resume first. CareerOps uses it to build the profile that powers matching and tailored documents."
                >
                  <div className="space-y-4">
                    <div className="grid gap-3 lg:grid-cols-[180px_minmax(0,1fr)]">
                      <label className="block">
                        <span className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[color:var(--app-muted)]">
                          Document type
                        </span>
                        <select
                          value={documentSourceType}
                          onChange={(event) => setDocumentSourceType(event.target.value)}
                          className="mt-2 w-full rounded-2xl border border-[color:var(--app-border-strong)] bg-white px-3 py-2 text-sm text-[color:var(--app-ink)] outline-none transition focus:border-[color:var(--app-accent)]"
                        >
                          <option value="cv">Main resume</option>
                          <option value="linkedin">LinkedIn PDF/text</option>
                          <option value="manual">Notes about me</option>
                          <option value="portfolio">Portfolio/GitHub note</option>
                        </select>
                      </label>

                      <label className="block">
                        <span className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[color:var(--app-muted)]">
                          File
                        </span>
                        <input
                          ref={documentInputRef}
                          type="file"
                          accept=".pdf,.docx,.txt,.md,.tex"
                          onChange={(event) =>
                            setSelectedDocument(event.target.files?.[0] ?? null)
                          }
                          className="mt-2 w-full rounded-2xl border border-[color:var(--app-border-strong)] bg-white px-3 py-2 text-sm text-[color:var(--app-ink)] file:mr-3 file:rounded-xl file:border-0 file:bg-[color:var(--app-ink)] file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-white"
                        />
                      </label>
                    </div>

                    <div className="flex flex-wrap gap-3">
                      <button
                        type="button"
                        onClick={() => void handleUploadDocument()}
                        disabled={operationMutating['upload-document']}
                        className="rounded-2xl bg-[color:var(--app-ink)] px-4 py-2 text-sm font-medium text-white transition hover:opacity-92 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {operationMutating['upload-document']
                          ? 'Uploading...'
                          : 'Add file'}
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleExtractProfile()}
                        disabled={operationMutating['extract-profile'] || !latestCvDocument}
                        className="rounded-2xl border border-[color:var(--app-border-strong)] bg-white px-4 py-2 text-sm font-medium text-[color:var(--app-ink)] transition hover:bg-[color:var(--app-bg-soft)] disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {operationMutating['extract-profile']
                          ? 'Extracting...'
                          : latestCvDocument
                            ? 'Build profile'
                            : 'Upload CV first'}
                      </button>
                    </div>

                    <div className="rounded-[1.4rem] border border-[color:var(--app-border)] bg-[linear-gradient(180deg,#fcfffe,#edf7f5)] p-4">
                      <p className="text-sm font-medium text-[color:var(--app-accent)]">
                        Resume import
                      </p>

                      {IS_LOCAL_API ? (
                        <label className="mt-4 block">
                          <span className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[color:var(--app-accent)]">
                            Resume file path
                          </span>
                          <input
                            type="text"
                            value={localDocumentPath}
                            onChange={(event) => setLocalDocumentPath(event.target.value)}
                            className="mt-2 w-full rounded-2xl border border-sky-200 bg-white px-3 py-2 text-sm text-[color:var(--app-ink)] outline-none transition focus:border-[color:var(--app-accent)]"
                            placeholder="C:\Users\you\...\resume.pdf"
                          />
                        </label>
                      ) : null}

                      <div className="mt-4 flex flex-wrap gap-3">
                        {IS_LOCAL_API ? (
                          <button
                            type="button"
                            onClick={() => void handleImportLocalCvAndRunAiProfileAgent()}
                            disabled={operationMutating['ai-profile-import-run']}
                            className="rounded-2xl bg-[color:var(--app-accent)] px-4 py-2 text-sm font-medium text-white transition hover:opacity-92 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {operationMutating['ai-profile-import-run']
                              ? 'Importing resume...'
                              : 'Import resume from this computer'}
                          </button>
                        ) : null}
                        <button
                          type="button"
                          onClick={() => void handleRunAiProfileAgentOnLatestCv()}
                          disabled={
                            operationMutating['ai-profile-latest-cv'] || !latestCvDocument
                          }
                          className="rounded-2xl border border-sky-300 bg-white px-4 py-2 text-sm font-medium text-[color:var(--app-accent)] transition hover:bg-sky-100 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          {operationMutating['ai-profile-latest-cv']
                            ? 'Refreshing profile...'
                            : latestCvDocument
                              ? 'Refresh from latest resume'
                              : 'Add a resume first'}
                        </button>
                      </div>
                    </div>

                    <ResourceBanner title="Documents" state={documents} />
                    <div className="space-y-3">
                      {documents.data.map((document) => (
                        <article
                          key={document.id}
                          className="rounded-[1.2rem] border border-[color:var(--app-border)] bg-white/90 p-3"
                        >
                          <div className="flex items-center justify-between gap-3">
                            <p className="text-sm font-medium text-[color:var(--app-ink)]">
                              {document.original_filename}
                            </p>
                            <div className="flex items-center gap-2">
                              <span className="rounded-full bg-[color:var(--app-bg-soft)] px-2.5 py-1 text-xs font-medium text-[color:var(--app-muted)] ring-1 ring-[color:var(--app-border)]">
                                {document.source_type}
                              </span>
                              <button
                                type="button"
                                onClick={() => void handleDeleteDocument(document)}
                                disabled={Boolean(operationMutating[`delete-document-${document.id}`])}
                                className="rounded-lg border border-rose-300 bg-white px-2.5 py-1 text-xs font-medium text-rose-700 transition hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-60"
                              >
                                {operationMutating[`delete-document-${document.id}`] ? 'Deleting...' : 'Delete'}
                              </button>
                            </div>
                          </div>
                          <p className="mt-2 text-xs text-[color:var(--app-muted)]">
                            {document.extracted_text
                              ? `${document.extracted_text.length} extracted characters`
                              : 'Stored without extracted text yet'}
                          </p>
                        </article>
                      ))}
                      {documents.data.length === 0 ? (
                        <EmptyState
                          title="No documents uploaded"
                          body="Add your main resume to build the profile used for matching and tailored documents."
                        />
                      ) : null}
                    </div>
                  </div>
                </Panel>

                <Panel
                  title="Connections and maintenance"
                  subtitle="Keep Google, job discovery, inbox review, and matching data up to date from one place."
                >
                  <div className="space-y-5">
                    <div className="grid gap-3 md:grid-cols-2">
                      <MetricCard
                        label="Gmail"
                        value={gmailStatusState.data?.authenticated ? 'Ready' : 'Required'}
                        note={
                          gmailStatusState.data?.token_file_exists
                            ? 'Connected'
                            : 'Sign in required'
                        }
                      />
                      <MetricCard
                        label="Evidence docs"
                        value={documents.data.length}
                        note="Sources available for profile extraction"
                      />
                    </div>

                    <ResourceBanner title="Gmail status" state={gmailStatusState} />

                    <div className="rounded-md border border-slate-200 bg-slate-50 p-4">
                      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                        <div>
                          <p className="text-sm font-medium text-slate-900">
                            Google account
                          </p>
                          <p className="mt-1 text-sm leading-6 text-slate-600">
                            {gmailStatusState.data?.authenticated
                              ? 'Connected'
                              : gmailStatusState.data?.oauth_configured
                                ? 'Ready for sign-in'
                                : 'Not configured'}
                          </p>
                        </div>
                      <button
                        type="button"
                        onClick={() => void handleStartGmailWebOAuth()}
                          disabled={
                            operationMutating['gmail-web-oauth'] ||
                            !gmailStatusState.data?.oauth_configured
                          }
                          className="rounded-2xl border border-[color:var(--app-border-strong)] bg-white px-4 py-2 text-sm font-medium text-[color:var(--app-ink)] transition hover:bg-[color:var(--app-bg-soft)] disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          {operationMutating['gmail-web-oauth']
                            ? 'Opening OAuth...'
                            : gmailStatusState.data?.authenticated
                              ? 'Reconnect Google'
                              : 'Continue with Google'}
                        </button>
                      </div>
                    </div>

                    <div className="rounded-md border border-amber-200 bg-amber-50 p-4">
                      <p className="text-sm font-medium text-amber-950">
                        Email review
                      </p>
                      <div className="mt-4 grid gap-3 sm:grid-cols-[160px_minmax(0,1fr)]">
                        <label className="block">
                          <span className="text-xs font-semibold uppercase tracking-wide text-amber-800">
                            Emails to review
                          </span>
                          <input
                            type="number"
                            min={1}
                            max={25}
                            value={emailAgentBatchLimit}
                            onChange={(event) => setEmailAgentBatchLimit(event.target.value)}
                            className="mt-2 w-full rounded-md border border-amber-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-amber-500"
                          />
                        </label>
                        <div className="flex items-end">
                          <button
                            type="button"
                            onClick={() => void handleRunAiEmailTriage()}
                            disabled={
                              operationMutating['ai-email-triage'] ||
                              !gmailStatusState.data?.authenticated
                            }
                            className="w-full rounded-md border border-amber-300 bg-white px-4 py-2 text-sm font-medium text-amber-900 transition hover:bg-amber-100 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {operationMutating['ai-email-triage']
                              ? 'Reviewing emails...'
                              : 'Review recent hiring emails'}
                          </button>
                        </div>
                      </div>
                    </div>

                    <div className="rounded-md border border-sky-200 bg-sky-50 p-4">
                      <p className="text-sm font-medium text-sky-950">
                        Job matching
                      </p>
                      <button
                        type="button"
                        onClick={() => void handleRebuildEmbeddings()}
                        disabled={operationMutating['rebuild-embeddings']}
                        className="mt-4 rounded-md bg-sky-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {operationMutating['rebuild-embeddings']
                          ? 'Refreshing matching...'
                          : 'Refresh job matching'}
                      </button>
                    </div>

                    <div className="grid gap-3 sm:grid-cols-2">
                      <button
                        type="button"
                        onClick={() => void handleRunDiscovery()}
                        disabled={operationMutating['run-discovery']}
                        className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {operationMutating['run-discovery']
                          ? 'Looking for jobs...'
                          : 'Find new jobs'}
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleSyncGmail()}
                        disabled={
                          operationMutating['sync-gmail'] ||
                          !gmailStatusState.data?.authenticated
                        }
                        className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {operationMutating['sync-gmail'] ? 'Refreshing...' : 'Refresh inbox'}
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleSyncLinkedIn()}
                        disabled={
                          operationMutating['sync-linkedin'] ||
                          !gmailStatusState.data?.authenticated
                        }
                        className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {operationMutating['sync-linkedin']
                          ? 'Importing LinkedIn alerts...'
                          : 'Import LinkedIn alerts'}
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleReclassifyEmails()}
                        disabled={operationMutating['reclassify-emails']}
                        className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {operationMutating['reclassify-emails']
                          ? 'Re-checking inbox...'
                          : 'Re-check inbox categories'}
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleGenerateDailySummary()}
                        disabled={operationMutating['daily-summary']}
                        className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {operationMutating['daily-summary']
                          ? 'Refreshing summary...'
                          : 'Refresh home summary'}
                      </button>
                      <button
                        type="button"
                        onClick={() => void refreshCoreData()}
                        className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 transition hover:bg-slate-50"
                      >
                        Refresh all data
                      </button>
                    </div>

                  </div>
                </Panel>
                </div>
              </div>
            ) : null}

            {activeSection === 'jobs' ? (
              <div className="space-y-6">
                {guidedAction === 'job-review' && selectedJob ? (
                  <div className="rounded-[1.45rem] border border-[color:var(--app-border)] bg-[linear-gradient(135deg,#fffdf8,#f2efe8)] p-5 shadow-[0_14px_32px_rgba(23,23,23,0.05)]">
                    <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                      <div>
                        <p className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[color:var(--app-muted)]">
                          Guided action
                        </p>
                        <p className="mt-2 text-lg font-semibold text-[color:var(--app-ink)]">
                          Review this opportunity and decide what to do next
                        </p>
                        <p className="mt-2 text-sm leading-6 text-[color:var(--app-muted)]">
                          Check fit, create a tailored resume, or remove the role from the workspace if it is not relevant.
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-3">
                        <button
                          type="button"
                          onClick={() => void handleScoreSelectedJob()}
                          disabled={operationMutating['score-job'] || selectedJobDescriptionIncomplete}
                          className="rounded-2xl bg-[color:var(--app-ink)] px-4 py-2 text-sm font-medium text-white transition hover:opacity-92 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          {operationMutating['score-job'] ? 'Checking fit...' : 'Check fit'}
                        </button>
                        <button
                          type="button"
                          onClick={() => void handleDeleteSelectedJob()}
                          disabled={operationMutating['delete-job']}
                          className="rounded-2xl border border-rose-300 bg-white px-4 py-2 text-sm font-medium text-rose-700 transition hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          {operationMutating['delete-job'] ? 'Removing...' : 'Remove from workspace'}
                        </button>
                        <button
                          type="button"
                          onClick={() => setGuidedAction(null)}
                          className="rounded-2xl border border-[color:var(--app-border-strong)] bg-white px-4 py-2 text-sm font-medium text-[color:var(--app-ink)] transition hover:bg-[color:var(--app-bg-soft)]"
                        >
                          Dismiss
                        </button>
                      </div>
                    </div>
                  </div>
                ) : null}

                <div className="grid gap-4 xl:grid-cols-[minmax(340px,0.88fr)_minmax(0,1.35fr)]">
                <Panel
                  title="Job opportunities"
                  subtitle="A searchable shortlist of roles with a dedicated detail view for responsibilities, requirements, and application progress."
                >
                  <div className="mb-4">
                    <label className="crm-label block">
                      Search jobs
                    </label>
                    <input
                      type="text"
                      value={jobSearch}
                      onChange={(event) => setJobSearch(event.target.value)}
                      placeholder="Search by title, company, source, or location"
                      className="crm-input mt-2 w-full px-3 py-2 text-sm"
                    />
                  </div>
                  <ResourceBanner title="Jobs" state={jobs} />
                  <div className="space-y-3">
                    {filteredJobs.slice(0, 40).map((job) => {
                      const selected = job.id === effectiveSelectedJobId
                      const linkedApplication = applicationsByJobId.get(job.id)
                      return (
                        <button
                          key={job.id}
                          type="button"
                          onClick={() => setSelectedJobId(job.id)}
                          className={`w-full rounded-[1.35rem] border p-4 text-left transition ${
                            selected
                              ? 'border-[color:var(--app-ink)] bg-[color:var(--app-ink)] text-white shadow-[0_18px_40px_rgba(23,23,23,0.18)]'
                              : 'border-[color:var(--app-border)] bg-[color:var(--app-bg-soft)] text-[color:var(--app-ink)] hover:-translate-y-0.5 hover:bg-white hover:shadow-[0_18px_36px_rgba(23,23,23,0.06)]'
                          }`}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <p className="text-sm font-medium">{job.title}</p>
                              <p
                                className={`mt-1 text-sm ${
                                  selected ? 'text-slate-300' : 'text-slate-600'
                                }`}
                              >
                                {job.company?.name ?? 'Unknown company'}
                              </p>
                              <p
                                className={`mt-2 text-xs ${
                                  selected ? 'text-stone-300' : 'text-[color:var(--app-muted)]'
                                }`}
                              >
                                {job.location ?? 'Location not listed'}
                                {' · '}
                                {job.work_mode ?? 'Work mode not listed'}
                              </p>
                            </div>
                            <div className="flex flex-col items-end gap-2">
                              <span
                                className={`rounded-full px-2.5 py-1 text-xs ${
                                  selected
                                    ? 'bg-white/15 text-white'
                                    : 'bg-white text-[color:var(--app-muted)] ring-1 ring-[color:var(--app-border)]'
                                }`}
                              >
                                {formatSourceLabel(job.source)}
                              </span>
                              <span
                                className={`rounded-full px-2.5 py-1 text-[0.68rem] font-medium ${
                                  selected
                                    ? 'bg-white/10 text-stone-100'
                                    : getStatusTone(linkedApplication?.status ?? 'Not applied')
                                }`}
                              >
                                {linkedApplication?.status ?? 'Not applied'}
                              </span>
                              <span
                                className={`rounded-full px-2.5 py-1 text-[0.68rem] font-medium ${
                                  selected
                                    ? 'bg-white/10 text-stone-100'
                                    : isJobDescriptionIncomplete(job)
                                      ? 'bg-amber-50 text-amber-800 ring-1 ring-amber-200'
                                      : 'bg-emerald-50 text-emerald-800 ring-1 ring-emerald-200'
                                }`}
                              >
                                {descriptionStatusLabel(job)}
                              </span>
                            </div>
                          </div>
                          <p className={`mt-3 text-sm leading-6 ${selected ? 'text-stone-200' : 'text-[color:var(--app-muted)]'}`}>
                            {truncate(cleanDisplayText(job.description), 170)}
                          </p>
                        </button>
                      )
                    })}
                  </div>
                </Panel>

                <div className="space-y-6">
                  <Panel
                    title={selectedJob?.title ?? 'Select a job'}
                    subtitle={
                      selectedJob
                        ? `${selectedJob.company?.name ?? 'Unknown company'} · ${selectedJob.location ?? 'Location not listed'}`
                        : 'Pick a role from the list to review requirements, fit, and tailored documents.'
                    }
                  >
                    {selectedJob ? (
                      <div className="space-y-5">
                        <div className="flex flex-wrap gap-2">
                          <span className="rounded-full bg-[color:var(--app-bg-soft)] px-2.5 py-1 text-xs font-medium text-[color:var(--app-muted)] ring-1 ring-[color:var(--app-border)]">
                            {formatSourceLabel(selectedJob.source)}
                          </span>
                          <span className="rounded-full bg-[color:var(--app-bg-soft)] px-2.5 py-1 text-xs font-medium text-[color:var(--app-muted)] ring-1 ring-[color:var(--app-border)]">
                            {selectedJob.work_mode ?? 'Work mode not parsed'}
                          </span>
                          <span className="rounded-full bg-[color:var(--app-bg-soft)] px-2.5 py-1 text-xs font-medium text-[color:var(--app-muted)] ring-1 ring-[color:var(--app-border)]">
                            {selectedJob.seniority ?? 'Seniority not parsed'}
                          </span>
                          <span
                            className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                              getStatusTone(selectedJobApplication?.status ?? 'Not applied')
                            }`}
                          >
                            {selectedJobApplication?.status ?? 'Not applied'}
                          </span>
                          <span
                            className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                              selectedJobDescriptionIncomplete
                                ? 'bg-amber-50 text-amber-800 ring-1 ring-amber-200'
                                : 'bg-emerald-50 text-emerald-800 ring-1 ring-emerald-200'
                            }`}
                          >
                            {descriptionStatusLabel(selectedJob)}
                          </span>
                        </div>

                        {selectedJob.description_status === 'partial_from_email' ? (
                          <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-900">
                            This job was discovered from a LinkedIn email alert, but the full job description has not been resolved yet.
                          </div>
                        ) : null}

                        <div className="grid gap-2 rounded-lg border border-[color:var(--app-border)] bg-white p-3 sm:grid-cols-2 xl:grid-cols-3">
                          {[
                            {
                              label: 'Company',
                              value: selectedJob.company?.name ?? 'Unknown',
                              note: formatSourceLabel(selectedJob.source),
                            },
                            {
                              label: 'Location',
                              value: selectedJob.location ?? 'Not listed',
                              note: selectedJob.work_mode ?? 'Work mode not listed',
                            },
                            {
                              label: 'Posted',
                              value: selectedJob.posted_at ? formatDate(selectedJob.posted_at) : 'Unknown',
                              note: selectedJob.application_deadline
                                ? `Deadline ${formatDate(selectedJob.application_deadline)}`
                                : `Added ${formatDate(selectedJob.created_at)}`,
                            },
                            {
                              label: 'Salary',
                              value: selectedJobSalary ?? 'Unknown',
                              note: 'From job description',
                            },
                            {
                              label: 'Apply link',
                              value: formatAvailabilityLabel(selectedJob.availability_status) || 'Unknown',
                              note: selectedJob.availability_checked_at
                                ? `Checked ${formatRelativeDate(selectedJob.availability_checked_at)}`
                                : 'Not checked yet',
                            },
                            {
                              label: 'Application',
                              value: selectedJobApplication?.status ?? 'New',
                              note: selectedJobApplication?.applied_at
                                ? `Updated ${formatDate(selectedJobApplication.applied_at)}`
                                : 'No application tracked',
                            },
                            {
                              label: 'Description',
                              value: descriptionStatusLabel(selectedJob),
                              note: selectedJob.resolution_confidence !== null
                                ? `Confidence ${Math.round(selectedJob.resolution_confidence * 100)}%`
                                : selectedJob.resolution_notes ?? 'Not resolved yet',
                            },
                          ].map((item) => (
                            <div key={item.label} className="min-w-0 rounded-md bg-[color:var(--app-bg-soft)] px-3 py-2 ring-1 ring-[color:var(--app-border)]">
                              <p className="text-[0.66rem] font-semibold uppercase tracking-[0.08em] text-[color:var(--app-muted)]">
                                {item.label}
                              </p>
                              <p className="mt-1 truncate text-sm font-semibold text-[color:var(--app-ink)]" title={String(item.value)}>
                                {item.value}
                              </p>
                              <p className="mt-0.5 truncate text-xs text-[color:var(--app-muted)]" title={item.note}>
                                {item.note}
                              </p>
                            </div>
                          ))}
                        </div>

                        <div className="rounded-[1.35rem] border border-[color:var(--app-border)] bg-[color:var(--app-bg-soft)] p-4">
                          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                            <div>
                              <p className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[color:var(--app-muted)]">
                                Source trace
                              </p>
                              <p className="mt-2 text-sm text-[color:var(--app-muted)]">
                                Imported from {formatSourceLabel(selectedJob.source)}
                                {selectedJob.source_trace?.email_subject
                                  ? ` via email "${String(selectedJob.source_trace.email_subject)}"`
                                  : selectedJob.source_trace?.subject
                                    ? ` via email "${String(selectedJob.source_trace.subject)}"`
                                  : ''}
                              </p>
                              {selectedJob.source_trace?.gmail_message_id ? (
                                <p className="mt-1 text-xs text-[color:var(--app-muted)]/80">
                                  Gmail message: {String(selectedJob.source_trace.gmail_message_id)}
                                </p>
                              ) : null}
                            </div>
                            <div className="flex shrink-0 flex-wrap gap-2">
                              {selectedJob.source_url ? (
                                <a
                                  href={selectedJob.source_url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="rounded-2xl bg-white px-3 py-2 text-xs font-medium text-[color:var(--app-ink)] ring-1 ring-[color:var(--app-border-strong)] transition hover:bg-[color:var(--app-bg-soft)]"
                                >
                                  Open original job
                                </a>
                              ) : null}
                              {selectedJob.source_trace?.gmail_thread_id ? (
                                <a
                                  href={`https://mail.google.com/mail/u/0/#inbox/${String(selectedJob.source_trace.gmail_thread_id)}`}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="rounded-2xl bg-white px-3 py-2 text-xs font-medium text-[color:var(--app-ink)] ring-1 ring-[color:var(--app-border-strong)] transition hover:bg-[color:var(--app-bg-soft)]"
                                >
                                  Open source email
                                </a>
                              ) : null}
                            </div>
                          </div>
                          <details className="mt-3">
                            <summary className="cursor-pointer text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[color:var(--app-muted)]">
                              Raw source metadata
                            </summary>
                            <pre className="mt-2 max-h-64 overflow-auto rounded-2xl bg-white p-3 text-xs leading-5 text-[color:var(--app-muted)] ring-1 ring-[color:var(--app-border)]">
                              {payloadText(selectedJob.source_trace ?? selectedJob.raw_payload)}
                            </pre>
                          </details>
                        </div>

                        <div className="flex flex-wrap gap-3 rounded-[1.35rem] border border-[color:var(--app-border)] bg-[linear-gradient(180deg,#fffdf8,#f6f0e7)] p-3">
                          <button
                            type="button"
                            onClick={() => void handleResolveSelectedJobDescription()}
                            disabled={operationMutating['resolve-job-description'] || !selectedJobDescriptionIncomplete}
                            className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {operationMutating['resolve-job-description']
                              ? 'Resolving...'
                              : 'Resolve description'}
                          </button>
                          <button
                            type="button"
                            onClick={() => void handleScoreSelectedJob()}
                            disabled={operationMutating['score-job'] || selectedJobDescriptionIncomplete}
                            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {operationMutating['score-job'] ? 'Checking fit...' : 'Check fit'}
                          </button>
                          <button
                            type="button"
                            onClick={() => void handleCreateCvPlan()}
                            disabled={operationMutating['cv-plan'] || selectedJobDescriptionIncomplete}
                            className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {operationMutating['cv-plan'] ? 'Planning...' : 'Plan tailored resume'}
                          </button>
                          <button
                            type="button"
                            onClick={() => void handleGenerateFinalCv()}
                            disabled={operationMutating['final-cv']}
                            className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {operationMutating['final-cv']
                              ? 'Generating...'
                              : 'Create tailored resume'}
                          </button>
                          <button
                            type="button"
                            onClick={() => void handleGenerateMessageDrafts()}
                            disabled={operationMutating['message-drafts'] || selectedJobDescriptionIncomplete}
                            className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {operationMutating['message-drafts']
                              ? 'Drafting...'
                              : 'Create outreach drafts'}
                          </button>
                          <button
                            type="button"
                            onClick={() => void handleCheckSelectedJobAvailability()}
                            disabled={operationMutating['availability-check'] || !selectedJob.source_url}
                            className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {operationMutating['availability-check']
                              ? 'Checking link...'
                              : 'Verify apply link'}
                          </button>
                          <button
                            type="button"
                            onClick={() => void handleCreateSelectedJobEmbedding()}
                            disabled={operationMutating['job-embedding']}
                            className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {operationMutating['job-embedding']
                              ? 'Embedding...'
                              : 'Refresh job insights'}
                          </button>
                          <button
                            type="button"
                            onClick={() => void handleDeleteSelectedJob()}
                            disabled={operationMutating['delete-job']}
                            className="rounded-md border border-rose-300 bg-white px-4 py-2 text-sm font-medium text-rose-700 transition hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {operationMutating['delete-job'] ? 'Removing...' : 'Remove from workspace'}
                          </button>
                        </div>
                        {selectedJobDescriptionIncomplete || selectedJob.fetch_status === 'needs_manual_review' ? (
                          <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-900">
                            Final scoring, CV tailoring, and outreach drafts are blocked until this job has a complete official description. Resolve from ATS, accept a review candidate, add an official public job URL, or paste the full description manually.
                          </div>
                        ) : null}

                        <div className="rounded-[1.35rem] border border-[color:var(--app-border)] bg-white p-4">
                          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                            <div>
                              <p className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[color:var(--app-muted)]">
                                Description resolver
                              </p>
                              <p className="mt-2 text-sm leading-6 text-[color:var(--app-muted)]">
                                {selectedJob.resolution_notes ?? 'No resolver attempt has been accepted for this role yet.'}
                              </p>
                            </div>
                            <div className="flex flex-wrap gap-2">
                              <span className="rounded-full bg-[color:var(--app-bg-soft)] px-2.5 py-1 text-xs font-medium text-[color:var(--app-muted)] ring-1 ring-[color:var(--app-border)]">
                                {selectedJob.description_source ?? 'No source'}
                              </span>
                              <span className="rounded-full bg-[color:var(--app-bg-soft)] px-2.5 py-1 text-xs font-medium text-[color:var(--app-muted)] ring-1 ring-[color:var(--app-border)]">
                                {selectedJob.resolution_confidence !== null
                                  ? `${Math.round(selectedJob.resolution_confidence * 100)}% confidence`
                                  : 'No confidence'}
                              </span>
                            </div>
                          </div>
                          {selectedJob.resolved_description_url ? (
                            <a
                              href={selectedJob.resolved_description_url}
                              target="_blank"
                              rel="noreferrer"
                              className="mt-3 inline-flex rounded-md border border-[color:var(--app-border-strong)] px-3 py-2 text-xs font-medium text-[color:var(--app-ink)] transition hover:bg-[color:var(--app-bg-soft)]"
                            >
                              Open resolved source
                            </a>
                          ) : null}
                          <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto]">
                            <input
                              value={selectedJobOfficialUrlInput}
                              onChange={(event) => {
                                if (selectedJob) {
                                  setJobOfficialUrlDrafts((current) => ({
                                    ...current,
                                    [selectedJob.id]: event.target.value,
                                  }))
                                }
                              }}
                              placeholder="Add official public job URL"
                              className="min-h-10 rounded-md border border-[color:var(--app-border-strong)] bg-[color:var(--app-bg-soft)] px-3 text-sm text-[color:var(--app-ink)] outline-none transition focus:border-[color:var(--app-accent)]"
                            />
                            <button
                              type="button"
                              onClick={() => void handleResolveSelectedJobManualUrl()}
                              disabled={operationMutating['manual-job-url'] || selectedJobOfficialUrlInput.trim().length < 8}
                              className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                            >
                              {operationMutating['manual-job-url'] ? 'Checking URL...' : 'Add official job URL'}
                            </button>
                          </div>
                          {selectedJobReviewCandidates.length ? (
                            <div className="mt-4 space-y-3">
                              {selectedJobReviewCandidates.map((attempt) => (
                                <div
                                  key={attempt.id}
                                  className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-3 text-sm text-amber-950"
                                >
                                  <div className="grid gap-2 md:grid-cols-2">
                                    <div>
                                      <p className="text-[0.66rem] font-semibold uppercase tracking-[0.08em] text-amber-800">
                                        Candidate source
                                      </p>
                                      <p className="mt-1 font-semibold">{attempt.attempted_source}</p>
                                    </div>
                                    <div>
                                      <p className="text-[0.66rem] font-semibold uppercase tracking-[0.08em] text-amber-800">
                                        Confidence
                                      </p>
                                      <p className="mt-1 font-semibold">
                                        {attempt.confidence !== null ? `${Math.round(attempt.confidence * 100)}%` : 'Unknown'}
                                      </p>
                                    </div>
                                    <div>
                                      <p className="text-[0.66rem] font-semibold uppercase tracking-[0.08em] text-amber-800">
                                        Candidate title
                                      </p>
                                      <p className="mt-1">{unknownToDisplayString(attempt.metadata?.posting_title ?? 'Unknown')}</p>
                                    </div>
                                    <div>
                                      <p className="text-[0.66rem] font-semibold uppercase tracking-[0.08em] text-amber-800">
                                        Candidate company
                                      </p>
                                      <p className="mt-1">{unknownToDisplayString(attempt.metadata?.posting_company ?? 'Unknown')}</p>
                                    </div>
                                    <div>
                                      <p className="text-[0.66rem] font-semibold uppercase tracking-[0.08em] text-amber-800">
                                        Candidate location
                                      </p>
                                      <p className="mt-1">{unknownToDisplayString(attempt.metadata?.posting_location ?? 'Not listed')}</p>
                                    </div>
                                    <div className="min-w-0">
                                      <p className="text-[0.66rem] font-semibold uppercase tracking-[0.08em] text-amber-800">
                                        Candidate URL
                                      </p>
                                      {attempt.attempted_url ? (
                                        <a href={attempt.attempted_url} target="_blank" rel="noreferrer" className="mt-1 block truncate underline">
                                          {attempt.attempted_url}
                                        </a>
                                      ) : (
                                        <p className="mt-1">No URL</p>
                                      )}
                                    </div>
                                  </div>
                                  {attempt.reason ? <p className="mt-3 text-xs leading-5">{attempt.reason}</p> : null}
                                  {attempt.metadata?.evidence ? (
                                    <pre className="mt-2 max-h-28 overflow-auto rounded-md bg-white/70 p-2 text-xs leading-5">
                                      {payloadText(attempt.metadata.evidence)}
                                    </pre>
                                  ) : null}
                                  <div className="mt-3 flex flex-wrap gap-2">
                                    <button
                                      type="button"
                                      onClick={() => void handleAcceptResolutionCandidate(attempt.id)}
                                      disabled={operationMutating[`accept-candidate-${attempt.id}`]}
                                      className="rounded-md bg-slate-900 px-3 py-2 text-xs font-medium text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
                                    >
                                      Accept this description
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => void handleRejectResolutionCandidate(attempt.id)}
                                      disabled={operationMutating[`reject-candidate-${attempt.id}`]}
                                      className="rounded-md border border-amber-300 bg-white px-3 py-2 text-xs font-medium text-amber-900 transition hover:bg-amber-100 disabled:cursor-not-allowed disabled:opacity-60"
                                    >
                                      Reject
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => {
                                        const pasted = String(attempt.metadata?.candidate_description ?? '')
                                        if (selectedJob && pasted) {
                                          setJobDescriptionDrafts((current) => ({ ...current, [selectedJob.id]: pasted }))
                                        }
                                      }}
                                      className="rounded-md border border-amber-300 bg-white px-3 py-2 text-xs font-medium text-amber-900 transition hover:bg-amber-100"
                                    >
                                      Paste description manually
                                    </button>
                                  </div>
                                </div>
                              ))}
                            </div>
                          ) : null}
                          <div className="mt-4 space-y-2">
                            {selectedJobResolutionAttempts.data.map((attempt) => (
                              <div
                                key={attempt.id}
                                className="rounded-md bg-[color:var(--app-bg-soft)] px-3 py-2 text-xs text-[color:var(--app-muted)] ring-1 ring-[color:var(--app-border)]"
                              >
                                <div className="flex flex-wrap items-center justify-between gap-2">
                                  <span className="font-semibold text-[color:var(--app-ink)]">
                                    {attempt.attempted_source} · {attempt.status}
                                  </span>
                                  <span>
                                    {attempt.confidence !== null
                                      ? `${Math.round(attempt.confidence * 100)}%`
                                      : formatRelativeDate(attempt.created_at)}
                                  </span>
                                </div>
                                {attempt.attempted_url ? (
                                  <a href={attempt.attempted_url} target="_blank" rel="noreferrer" className="mt-1 block truncate underline">
                                    {attempt.attempted_url}
                                  </a>
                                ) : null}
                                {attempt.reason ? <p className="mt-1">{attempt.reason}</p> : null}
                                {attempt.error_message ? <p className="mt-1 text-rose-700">{attempt.error_message}</p> : null}
                                <p className="mt-1">{formatRelativeDate(attempt.created_at)}</p>
                              </div>
                            ))}
                            {!selectedJobResolutionAttempts.loading && selectedJobResolutionAttempts.data.length === 0 ? (
                              <p className="text-xs text-[color:var(--app-muted)]">
                                No resolver attempts recorded yet.
                              </p>
                            ) : null}
                          </div>
                        </div>

                        <div className="rounded-[1.35rem] border border-[color:var(--app-border)] bg-white p-4">
                          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                            <div>
                              <p className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[color:var(--app-muted)]">
                                Job description for this role
                              </p>
                              <p className="mt-2 text-sm leading-6 text-[color:var(--app-muted)]">
                                Paste or correct the full description for this selected job so scoring, requirements, and CV tailoring use the right role context.
                              </p>
                            </div>
                            <button
                              type="button"
                              onClick={() => void handleUpdateSelectedJobDescription()}
                              disabled={
                                operationMutating['selected-job-description'] ||
                                !effectiveSelectedJobId ||
                                selectedJobDescriptionInput.trim().length < 20
                              }
                              className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
                            >
                              {operationMutating['selected-job-description']
                                ? 'Saving...'
                                : 'Paste description manually'}
                            </button>
                          </div>
                          <textarea
                            value={selectedJobDescriptionInput}
                            onChange={(event) => {
                              if (selectedJob) {
                                setJobDescriptionDrafts((current) => ({
                                  ...current,
                                  [selectedJob.id]: event.target.value,
                                }))
                              }
                            }}
                            rows={9}
                            placeholder="Paste the full job description for this selected job."
                            className="mt-4 min-h-52 w-full resize-y rounded-2xl border border-[color:var(--app-border-strong)] bg-[color:var(--app-bg-soft)] px-4 py-3 text-sm leading-6 text-[color:var(--app-ink)] outline-none transition focus:border-[color:var(--app-accent)]"
                          />
                        </div>

                        <div className="grid gap-5 xl:grid-cols-[minmax(0,1.1fr)_320px]">
                          <div className="space-y-5">
                            <div className="rounded-[1.35rem] border border-[color:var(--app-border)] bg-white p-5">
                              <p className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[color:var(--app-muted)]">
                                Role overview
                              </p>
                              <p className="mt-3 text-sm leading-7 text-slate-700">
                                {selectedJobSections.overview || cleanDisplayText(selectedJob.description)}
                              </p>
                            </div>

                            <div className="grid gap-5 lg:grid-cols-2">
                              <div className="rounded-[1.35rem] border border-[color:var(--app-border)] bg-[color:var(--app-bg-soft)] p-5">
                                <p className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[color:var(--app-muted)]">
                                  Responsibilities
                                </p>
                                {selectedJobSections.responsibilities.length ? (
                                  <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-700">
                                    {selectedJobSections.responsibilities.slice(0, 6).map((item) => (
                                      <li key={item}>- {item}</li>
                                    ))}
                                  </ul>
                                ) : (
                                  <p className="mt-3 text-sm text-[color:var(--app-muted)]">
                                    Responsibilities were not clearly structured in the source description yet.
                                  </p>
                                )}
                              </div>

                              <div className="rounded-[1.35rem] border border-[color:var(--app-border)] bg-[color:var(--app-bg-soft)] p-5">
                                <p className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[color:var(--app-muted)]">
                                  Requirements
                                </p>
                                {(selectedJobSections.requirements.length ||
                                  selectedJobScore?.extracted_requirements.required_skills?.length) ? (
                                  <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-700">
                                    {(selectedJobSections.requirements.length
                                      ? selectedJobSections.requirements
                                      : selectedJobScore?.extracted_requirements.required_skills ?? []
                                    )
                                      .slice(0, 6)
                                      .map((item) => (
                                        <li key={item}>- {item}</li>
                                      ))}
                                  </ul>
                                ) : (
                                  <p className="mt-3 text-sm text-[color:var(--app-muted)]">
                                    Requirements will appear here once the role has structured or scored fit data.
                                  </p>
                                )}
                              </div>
                            </div>

                            <div className="rounded-[1.35rem] border border-[color:var(--app-border)] bg-white p-5">
                              <p className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[color:var(--app-muted)]">
                                Full description
                              </p>
                              <p className="mt-3 whitespace-pre-line text-sm leading-7 text-slate-700">
                                {cleanDisplayText(selectedJob.description)}
                              </p>
                            </div>
                          </div>

                          <div className="space-y-5">
                            <div className="rounded-[1.35rem] border border-[color:var(--app-border)] bg-[linear-gradient(180deg,#fffdf8,#f4eee4)] p-5">
                              <p className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[color:var(--app-muted)]">
                                Technologies
                              </p>
                              {selectedJobTechnologies.length ? (
                                <div className="mt-3 flex flex-wrap gap-2">
                                  {selectedJobTechnologies.map((technology) => (
                                    <span
                                      key={technology}
                                      className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-[color:var(--app-ink)] ring-1 ring-[color:var(--app-border)]"
                                    >
                                      {technology}
                                    </span>
                                  ))}
                                </div>
                              ) : (
                                <p className="mt-3 text-sm text-[color:var(--app-muted)]">
                                  No technology tags were inferred yet from the job text.
                                </p>
                              )}
                            </div>

                            <div className="rounded-[1.35rem] border border-[color:var(--app-border)] bg-[color:var(--app-bg-soft)] p-5">
                              <p className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[color:var(--app-muted)]">
                                Company and application
                              </p>
                              <dl className="mt-3 space-y-3 text-sm text-slate-700">
                                <div>
                                  <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                                    Company
                                  </dt>
                                  <dd className="mt-1">{selectedJob.company?.name ?? 'Unknown company'}</dd>
                                </div>
                                <div>
                                  <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                                    Location
                                  </dt>
                                  <dd className="mt-1">
                                    {selectedJob.location ?? 'Location not listed'}
                                  </dd>
                                </div>
                                <div>
                                  <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                                    Work style
                                  </dt>
                                  <dd className="mt-1">
                                    {selectedJob.work_mode ?? 'Not identified'}
                                  </dd>
                                </div>
                                <div>
                                  <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                                    Application status
                                  </dt>
                                  <dd className="mt-1">
                                    {selectedJobApplication?.status ?? 'Not applied'}
                                  </dd>
                                </div>
                                <div>
                                  <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                                    Apply availability
                                  </dt>
                                  <dd className="mt-2">
                                    <span
                                      className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${getAvailabilityTone(selectedJob.availability_status)}`}
                                    >
                                      {formatAvailabilityLabel(selectedJob.availability_status)}
                                    </span>
                                  </dd>
                                  <p className="mt-2 text-xs leading-5 text-[color:var(--app-muted)]">
                                    {selectedJob.availability_reason ??
                                      'Run Verify apply link to check whether the source page still accepts applications.'}
                                  </p>
                                </div>
                              </dl>
                            </div>
                          </div>
                        </div>

                        <div className="rounded-md border border-slate-200 bg-white p-4">
                          <ResourceBanner
                            title="Match evidence"
                            state={selectedJobSemanticMatches}
                          />
                          {selectedJobSemanticMatches.data.length ? (
                            <div className="mt-3 space-y-3">
                              {selectedJobSemanticMatches.data.slice(0, 5).map((match) => (
                                <article
                                  key={`${match.source_table}-${match.source_id}`}
                                  className="rounded-md bg-slate-50 p-3 ring-1 ring-slate-200"
                                >
                                  <div className="flex items-start justify-between gap-3">
                                    <p className="text-sm font-medium text-slate-900">
                                      {String(match.metadata.name ?? match.metadata.kind ?? match.source_table)}
                                    </p>
                                    <span className="rounded-sm bg-sky-100 px-2 py-1 text-xs font-medium text-sky-800 ring-1 ring-sky-200">
                                      {Math.round(match.similarity * 100)}%
                                    </span>
                                  </div>
                                  <p className="mt-2 text-sm leading-6 text-slate-600">
                                    {truncate(cleanDisplayText(match.content), 220)}
                                  </p>
                                </article>
                              ))}
                            </div>
                          ) : (
                            <p className="mt-3 text-sm text-slate-500">
                              No semantic matches yet. Rebuild embeddings from Setup or refresh
                              this job embedding.
                            </p>
                          )}
                        </div>

                        <ResourceBanner title="Job scores" state={selectedJobScores} />
                        {selectedJobScore ? (
                          <div className="grid gap-5 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
                            <div className="space-y-4 rounded-md border border-slate-200 bg-slate-50 p-4">
                              <div className="flex items-center justify-between gap-3">
                                <div>
                                  <p className="text-sm font-medium text-slate-900">
                                    Fit summary
                                  </p>
                                  <p className="mt-1 text-3xl font-semibold text-slate-950">
                                    {selectedJobScore.score}
                                  </p>
                                </div>
                                <span
                                  className={`inline-flex rounded-sm px-2 py-1 text-xs font-medium ${getRecommendationTone(selectedJobScore.recommendation)}`}
                                >
                                  {selectedJobScore.recommendation}
                                </span>
                              </div>

                              <div>
                                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                                  Requirements
                                </p>
                                <div className="mt-2 flex flex-wrap gap-2">
                                  {selectedJobScore.extracted_requirements.required_skills?.map(
                                    (skill) => (
                                      <span
                                        key={skill}
                                        className="rounded-sm bg-white px-2 py-1 text-xs font-medium text-slate-700 ring-1 ring-slate-200"
                                      >
                                        {skill}
                                      </span>
                                    ),
                                  )}
                                </div>
                              </div>

                              <div>
                                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                                  Reasons
                                </p>
                                <ul className="mt-2 space-y-2 text-sm text-slate-700">
                                  {selectedJobScore.reasons.map((reason) => (
                                    <li key={reason}>- {reason}</li>
                                  ))}
                                </ul>
                              </div>

                              {selectedJobScore.risks.length ? (
                                <div>
                                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                                    Risks
                                  </p>
                                  <ul className="mt-2 space-y-2 text-sm text-slate-700">
                                    {selectedJobScore.risks.map((risk) => (
                                      <li key={risk}>- {risk}</li>
                                    ))}
                                  </ul>
                                </div>
                              ) : null}
                            </div>

                            <div className="rounded-md border border-slate-200 bg-white p-4">
                              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                                Match evidence
                              </p>
                              <div className="mt-3 space-y-3">
                                {selectedJobScore.matched_skills.map((match) => (
                                  <article
                                    key={`${match.required_skill}-${match.profile_skill}`}
                                    className="rounded-md border border-slate-200 bg-slate-50 p-3"
                                  >
                                    <div className="flex items-center justify-between gap-3">
                                      <p className="text-sm font-medium text-slate-900">
                                        {match.required_skill}
                                        {' -> '}
                                        {match.profile_skill}
                                      </p>
                                      <span className="rounded-sm bg-slate-200 px-2 py-1 text-xs text-slate-700">
                                        {match.match_type}
                                      </span>
                                    </div>
                                    <p className="mt-2 text-sm text-slate-700">
                                      {truncate(match.evidence_text, 180)}
                                    </p>
                                    {match.rationale ? (
                                      <p className="mt-2 text-xs text-slate-500">
                                        {match.rationale}
                                      </p>
                                    ) : null}
                                  </article>
                                ))}
                              </div>
                            </div>
                          </div>
                        ) : (
                          <EmptyState
                            title="No job score yet"
                            body="This role is loaded, but there is no scored match record available from the backend."
                          />
                        )}
                      </div>
                    ) : (
                      <EmptyState
                        title="No job selected"
                        body="Pick a role from the left column to review fit, tailored resumes, and outreach drafts."
                      />
                    )}
                  </Panel>

                  <div className="grid gap-6 xl:grid-cols-2">
                    <Panel
                      title="Tailored resumes"
                      subtitle={`${selectedJobCvVersions.data.length} tailored resume records for the selected role`}
                    >
                      <ResourceBanner title="Resume plans" state={selectedJobCvVersions} />
                      {selectedJobCvVersions.data.length ? (
                        <div className="space-y-4">
                          {selectedJobCvVersions.data.map((version) => (
                            <article
                              key={version.id}
                              className="rounded-md border border-slate-200 bg-slate-50 p-4"
                            >
                              <div className="flex items-center justify-between gap-3">
                                <p className="text-sm font-medium text-slate-900">
                                  CV version {version.id.slice(0, 8)}
                                </p>
                                <div className="flex flex-wrap items-center gap-2">
                                  {version.tailoring_plan.planner ? (
                                    <span className="inline-flex rounded-sm bg-sky-100 px-2 py-1 text-xs font-medium text-sky-800 ring-1 ring-sky-200">
                                      {version.tailoring_plan.planner}
                                    </span>
                                  ) : null}
                                  <span
                                    className={`inline-flex rounded-sm px-2 py-1 text-xs font-medium ${getStatusTone(version.status)}`}
                                  >
                                    {version.status}
                                  </span>
                                </div>
                              </div>

                              {version.tailoring_plan.template_filename ? (
                                <p className="mt-2 text-xs text-slate-500">
                                  Template source: {version.tailoring_plan.template_filename}
                                </p>
                              ) : null}
                              {version.tailoring_plan.planner_fallback_reason ? (
                                <p className="mt-2 text-xs text-amber-700">
                                  Fallback used: {version.tailoring_plan.planner_fallback_reason}
                                </p>
                              ) : null}

                              <p className="mt-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
                                Focus
                              </p>
                              <ul className="mt-2 space-y-2 text-sm text-slate-700">
                                {version.tailoring_plan.summary_focus?.map((item) => (
                                  <li key={item}>- {item}</li>
                                ))}
                              </ul>

                              <p className="mt-4 text-xs font-semibold uppercase tracking-wide text-slate-500">
                                Prioritized skills
                              </p>
                              <div className="mt-2 flex flex-wrap gap-2">
                                {version.tailoring_plan.skills_to_prioritize?.map((skill) => (
                                  <span
                                    key={skill}
                                    className="rounded-sm bg-white px-2 py-1 text-xs font-medium text-slate-700 ring-1 ring-slate-200"
                                  >
                                    {skill}
                                  </span>
                                ))}
                              </div>

                              {version.changes?.length ? (
                                <div className="mt-4">
                                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                                    Audit trail
                                  </p>
                                  <ul className="mt-2 space-y-2 text-sm text-slate-700">
                                    {version.changes.slice(0, 4).map((change, index) => (
                                      <li key={`${change.section}-${index}`}>
                                        <span className="font-medium text-slate-900">{change.section}:</span>{' '}
                                        {change.reason}
                                        {change.source ? (
                                          <span className="text-slate-500"> Source: {change.source}.</span>
                                        ) : null}
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              ) : null}

                              {version.generated_file_path ? (
                                <div className="mt-4 space-y-3">
                                  <p className="text-xs text-slate-500">
                                    Generated file: {version.generated_file_path}
                                  </p>
                                  <div className="flex flex-wrap gap-2">
                                    <a
                                      href={cvArtifactUrl(version.id, 'tex')}
                                      className="rounded-md border border-slate-300 bg-white px-3 py-2 text-xs font-medium text-slate-800 transition hover:bg-slate-50"
                                      target="_blank"
                                      rel="noreferrer"
                                    >
                                      Open LaTeX
                                    </a>
                                    {version.tailoring_plan.generated_pdf_path ? (
                                      <a
                                        href={cvArtifactUrl(version.id, 'pdf')}
                                        className="rounded-md bg-slate-900 px-3 py-2 text-xs font-medium text-white transition hover:bg-slate-700"
                                        target="_blank"
                                        rel="noreferrer"
                                      >
                                        Open PDF
                                      </a>
                                    ) : null}
                                  </div>
                                  {version.tailoring_plan.pdf_generation_error ? (
                                    <p className="text-xs text-amber-700">
                                      PDF generation: {version.tailoring_plan.pdf_generation_error}
                                    </p>
                                  ) : null}
                                </div>
                              ) : null}
                              {version.review_notes ? (
                                <p className="mt-2 text-sm text-slate-600">
                                  Review: {version.review_notes}
                                </p>
                              ) : null}
                            </article>
                          ))}
                        </div>
                      ) : (
                        <EmptyState
                          title="No tailored resumes for this job"
                          body="When you create a tailored resume plan, the focus areas, audit trail, and generated files will appear here."
                        />
                      )}
                    </Panel>

                    <Panel
                      title="Outreach drafts"
                      subtitle={`${approvedDraftCount} approved drafts and ${approvedCvCount} approved resume versions for this role`}
                    >
                      <ResourceBanner title="Outreach drafts" state={selectedJobDrafts} />
                      {selectedJobDrafts.data.length ? (
                        <div className="space-y-4">
                          {selectedJobDrafts.data.map((draft) => (
                            <article
                              key={draft.id}
                              className="rounded-md border border-slate-200 bg-slate-50 p-4"
                            >
                              <div className="flex items-center justify-between gap-3">
                                <div>
                                  <p className="text-sm font-medium text-slate-900">
                                    {draft.draft_type}
                                  </p>
                                  <p className="mt-1 text-sm text-slate-600">
                                    {draft.subject ?? 'No subject'}
                                  </p>
                                </div>
                                <span
                                  className={`inline-flex rounded-sm px-2 py-1 text-xs font-medium ${getStatusTone(draft.status)}`}
                                >
                                  {draft.status}
                                </span>
                              </div>
                              <div className="mt-3 rounded-lg border border-[color:var(--app-border)] bg-white p-3">
                                <AiText>{truncate(draft.body, 360)}</AiText>
                              </div>
                              {draft.review_notes ? (
                                <p className="mt-3 text-sm text-slate-600">
                                  Review: {draft.review_notes}
                                </p>
                              ) : null}
                            </article>
                          ))}
                        </div>
                      ) : (
                        <EmptyState
                          title="No drafts for this job"
                          body="Drafts appear here after you generate outreach messages or prepare recruiter replies."
                        />
                      )}
                    </Panel>
                  </div>
                </div>
                </div>
              </div>
            ) : null}

            {activeSection === 'applications' ? (
              <div className="grid gap-6 xl:grid-cols-[minmax(360px,0.9fr)_minmax(0,1.3fr)]">
                <Panel
                  title="Application pipeline"
                  subtitle="Human-reviewed pipeline across found roles, ready-to-apply items, and post-submit follow-up."
                >
                  <ResourceBanner title="Applications" state={applications} />
                  <div className="mb-3 space-y-3">
                    <input
                      value={pipelineSearch}
                      onChange={(event) => setPipelineSearch(event.target.value)}
                      placeholder="Search company, role, or status"
                      className="w-full rounded-2xl border border-[color:var(--app-border)] bg-white px-3 py-2 text-sm text-[color:var(--app-ink)] outline-none focus:border-[color:var(--app-accent)]"
                    />
                    <div className="flex flex-wrap gap-2">
                      {[
                        { id: 'all', label: 'All' },
                        { id: 'active', label: 'Active' },
                        { id: 'rejected', label: 'Rejected' },
                        { id: 'actionable', label: 'Action available' },
                        { id: 'no_action', label: 'No action' },
                      ].map((option) => (
                        <button
                          key={option.id}
                          type="button"
                          onClick={() => setPipelineFilter(option.id as PipelineFilter)}
                          className={`rounded-md px-2.5 py-1.5 text-xs font-medium ring-1 ${
                            pipelineFilter === option.id
                              ? 'bg-[color:var(--app-ink)] text-white ring-[color:var(--app-ink)]'
                              : 'bg-white text-[color:var(--app-muted)] ring-[color:var(--app-border)]'
                          }`}
                        >
                          {option.label}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="space-y-2">
                    {applicationRows.map((row) => {
                      const { application, companyLabel, titleLabel } = row
                      const selected = application.id === effectiveSelectedApplicationId
                      return (
                        <button
                          key={application.id}
                          type="button"
                          onClick={() => setSelectedApplicationId(application.id)}
                          className={`w-full rounded-lg border p-3 text-left transition ${
                            selected
                              ? 'border-[color:var(--app-ink)] bg-[color:var(--app-ink)] text-white'
                              : 'border-[color:var(--app-border)] bg-[color:var(--app-bg-soft)] text-[color:var(--app-ink)] hover:bg-white'
                          }`}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <p className="text-sm font-medium">
                                {companyLabel}
                              </p>
                              <p
                                className={`mt-1 text-sm ${
                                  selected ? 'text-slate-300' : 'text-slate-600'
                                }`}
                              >
                                {titleLabel}
                              </p>
                            </div>
                            <span
                              className={`rounded-md px-2 py-1 text-xs ${
                                selected
                                  ? 'bg-white/15 text-white'
                                  : 'bg-white text-[color:var(--app-muted)] ring-1 ring-[color:var(--app-border)]'
                              }`}
                            >
                              {application.status}
                            </span>
                          </div>
                          <p
                            className={`mt-3 text-sm ${
                              selected ? 'text-slate-300' : 'text-slate-600'
                            }`}
                          >
                            {application.applied_at
                              ? `Applied ${formatDate(application.applied_at)}`
                              : truncate(application.notes, 110)}
                          </p>
                          <div className="mt-2 flex flex-wrap gap-2">
                            {row.hasNoReply ? (
                              <span className={`rounded-md px-2 py-0.5 text-[11px] ${selected ? 'bg-white/15 text-white' : 'bg-amber-100 text-amber-800'}`}>
                                No-reply
                              </span>
                            ) : null}
                            {row.hasNoActions ? (
                              <span className={`rounded-md px-2 py-0.5 text-[11px] ${selected ? 'bg-white/15 text-white' : 'bg-slate-100 text-slate-700'}`}>
                                No actions
                              </span>
                            ) : null}
                          </div>
                        </button>
                      )
                    })}
                    {!applicationRows.length ? (
                      <EmptyState
                        title="No applications in this filter"
                        body="Adjust search or pipeline filter to see more applications."
                      />
                    ) : null}
                  </div>
                </Panel>

                <div className="space-y-4">
                  <Panel
                    title={selectedApplicationTracker.data?.job_title ?? 'Select an application'}
                    subtitle={
                      selectedApplicationTracker.data
                        ? `${selectedApplicationTracker.data.company_name ?? 'Unknown company'} - ${selectedApplicationTracker.data.status}`
                        : 'Pick an application from the left column to inspect tracker state and next actions.'
                    }
                  >
                    <ResourceBanner
                      title="Application tracker"
                      state={selectedApplicationTracker}
                    />

                    {selectedApplicationTracker.data ? (
                      <div className="space-y-4">
                        <div className="flex justify-end">
                          <button
                            type="button"
                            onClick={() => void handleDeleteSelectedApplication()}
                            disabled={operationMutating['delete-application']}
                            className="crm-button border border-rose-300 bg-white text-xs text-rose-700 hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {operationMutating['delete-application'] ? 'Deleting...' : 'Delete application'}
                          </button>
                        </div>

                        <div className="crm-subcard p-4">
                          <p className="crm-label">
                            Origin
                          </p>
                          <p className="mt-2 text-sm text-[color:var(--app-muted)]">
                            Source: <span className="font-medium text-[color:var(--app-ink)]">{selectedApplicationJob?.source ?? selectedApplication?.job_source ?? 'unknown'}</span>
                          </p>
                          {selectedApplicationJob?.source_url ? (
                            <p className="mt-2 text-sm">
                              <a
                                href={selectedApplicationJob.source_url}
                                target="_blank"
                                rel="noreferrer"
                                className="font-medium text-[color:var(--app-ink)] underline decoration-[color:var(--app-border-strong)] underline-offset-4"
                              >
                                Open original job posting
                              </a>
                            </p>
                          ) : null}
                          {jobGmailThreadUrl(selectedApplicationJob) ? (
                            <p className="mt-2 text-sm">
                              <a
                                href={jobGmailThreadUrl(selectedApplicationJob) ?? undefined}
                                target="_blank"
                                rel="noreferrer"
                                className="font-medium text-[color:var(--app-ink)] underline decoration-[color:var(--app-border-strong)] underline-offset-4"
                              >
                                Open Gmail thread source
                              </a>
                            </p>
                          ) : null}
                          {selectedApplicationSourceEmail && gmailThreadUrl(selectedApplicationSourceEmail) ? (
                            <p className="mt-2 text-sm">
                              <a
                                href={gmailThreadUrl(selectedApplicationSourceEmail) ?? undefined}
                                target="_blank"
                                rel="noreferrer"
                                className="font-medium text-[color:var(--app-ink)] underline decoration-[color:var(--app-border-strong)] underline-offset-4"
                              >
                                Open source email
                              </a>
                            </p>
                          ) : null}
                        </div>

                        <div className="rounded-[1.35rem] border border-[color:var(--app-border)] bg-white p-4">
                          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                            <div>
                              <p className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[color:var(--app-muted)]">
                                Application job description
                              </p>
                              <p className="mt-2 text-sm leading-6 text-[color:var(--app-muted)]">
                                Save the full role text here when this application needs better title, role, requirements, reply, or CV tailoring context.
                              </p>
                            </div>
                            <button
                              type="button"
                              onClick={() => void handleUpdateApplicationJobDescription()}
                              disabled={
                                operationMutating['application-job-description'] ||
                                !selectedApplication?.job_id ||
                                applicationJobDescriptionInput.trim().length < 20
                              }
                              className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
                            >
                              {operationMutating['application-job-description']
                                ? 'Saving...'
                                : 'Save under this application'}
                            </button>
                          </div>
                          <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(280px,0.8fr)]">
                            <textarea
                              value={applicationJobDescriptionInput}
                                onChange={(event) => {
                                  if (selectedApplication) {
                                    setApplicationJobDescriptionDrafts((current) => ({
                                      ...current,
                                      [selectedApplication.id]: event.target.value,
                                    }))
                                  }
                                }}
                              rows={9}
                              placeholder="Paste the job description for this exact application."
                              className="min-h-52 w-full resize-y rounded-2xl border border-[color:var(--app-border-strong)] bg-[color:var(--app-bg-soft)] px-4 py-3 text-sm leading-6 text-[color:var(--app-ink)] outline-none transition focus:border-[color:var(--app-accent)]"
                            />
                            <div>
                              <div className="flex items-center justify-between gap-3">
                                <p className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[color:var(--app-muted)]">
                                  Reply for contact
                                </p>
                                <button
                                  type="button"
                                  onClick={() => {
                                    if (applicationJobReplyInfo) {
                                      void navigator.clipboard.writeText(applicationJobReplyInfo)
                                    }
                                  }}
                                  disabled={!applicationJobReplyInfo}
                                  className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-800 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                                >
                                  Copy
                                </button>
                              </div>
                              {applicationJobReplyInfo ? (
                                <div className="mt-3 rounded-lg border border-[color:var(--app-border)] bg-white p-3">
                                  <AiText>{applicationJobReplyInfo}</AiText>
                                </div>
                              ) : null}
                              <textarea
                                value={applicationJobReplyInfo}
                                onChange={(event) => setApplicationJobReplyInfo(event.target.value)}
                                rows={7}
                                placeholder="After saving, a message for this application appears here."
                                className="mt-3 min-h-44 w-full resize-y rounded-2xl border border-[color:var(--app-border-strong)] bg-[color:var(--app-bg-soft)] px-4 py-3 text-sm leading-6 text-[color:var(--app-ink)] outline-none transition focus:border-[color:var(--app-accent)]"
                              />
                            </div>
                          </div>
                        </div>

                        <div className="grid gap-4 md:grid-cols-3">
                          <MetricCard
                            label="Score ready"
                            value={selectedApplicationTracker.data.artifact_state.has_score ? 'Yes' : 'No'}
                            note="Job fit analysis available"
                          />
                          <MetricCard
                            label="Approved CV"
                            value={
                              selectedApplicationTracker.data.artifact_state.has_approved_cv
                                ? 'Yes'
                                : 'No'
                            }
                            note="Human-approved before use"
                          />
                          <MetricCard
                            label="Approved draft"
                            value={
                              selectedApplicationTracker.data.artifact_state.has_approved_message
                                ? 'Yes'
                                : 'No'
                            }
                            note="At least one message approved"
                          />
                        </div>

                        {selectedApplication?.notes ? (
                          <div className="rounded-lg border border-[color:var(--app-border)] bg-white p-3">
                            <p className="crm-label">Latest application message</p>
                            <div className="mt-2 max-h-40 overflow-auto rounded-md bg-[color:var(--app-bg-soft)] p-3">
                              <AiText>{cleanDisplayText(selectedApplication.notes)}</AiText>
                            </div>
                          </div>
                        ) : null}

                        <div className="crm-subcard p-4">
                          <p className="crm-label">
                            Current action
                          </p>
                          <p className="mt-2 text-sm font-medium text-[color:var(--app-ink)]">
                            {selectedApplicationTracker.data.current_action}
                          </p>
                          {selectedApplicationTracker.data.next_steps.length ? (
                            <ul className="mt-3 space-y-2 text-sm text-[color:var(--app-muted)]">
                              {selectedApplicationTracker.data.next_steps.map((step) => (
                                <li key={step}>- {step}</li>
                              ))}
                            </ul>
                          ) : (
                            <p className="mt-3 text-sm text-[color:var(--app-muted)]">
                              No additional next steps currently suggested.
                            </p>
                          )}
                        </div>

                        <div className="rounded-[1.35rem] border border-[color:var(--app-border)] bg-white p-4">
                          <div className="flex flex-wrap items-start justify-between gap-3">
                            <div>
                              <p className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[color:var(--app-muted)]">
                                Candidate portal
                              </p>
                              <p className="mt-2 text-sm leading-6 text-[color:var(--app-muted)]">
                                Add credentials only for official company or ATS portals. Passwords are encrypted on the backend and never shown again.
                              </p>
                            </div>
                            <span className="rounded-full bg-[color:var(--app-bg-soft)] px-3 py-1 text-xs font-medium text-[color:var(--app-muted)]">
                              {selectedPortalCredentials.data.length} saved
                            </span>
                          </div>
                          <ResourceBanner
                            title="Portal credentials"
                            state={selectedPortalCredentials}
                          />
                          <div className="mt-4 grid gap-3 md:grid-cols-3">
                            <MetricCard
                              label="Public status"
                              value={selectedApplication?.latest_portal_status ?? 'Unknown'}
                              note={`Confidence: ${selectedApplication?.latest_portal_confidence ?? 'not checked'}`}
                            />
                            <MetricCard
                              label="Login required"
                              value={selectedApplication?.portal_login_required ? 'Yes' : 'No'}
                              note={selectedApplication?.portal_user_action_required ? 'User action required' : 'No blocker tracked'}
                            />
                            <MetricCard
                              label="Last checked"
                              value={formatDate(selectedApplication?.latest_portal_checked_at ?? null)}
                              note="Official page or ATS status"
                            />
                          </div>
                          <div className="mt-4 flex flex-wrap gap-3">
                            <button
                              type="button"
                              onClick={() => void handleRunPortalStatusCheck()}
                              disabled={operationMutating['portal-status-check']}
                              className="rounded-2xl border border-[color:var(--app-border-strong)] bg-white px-4 py-2 text-sm font-medium text-[color:var(--app-ink)] transition hover:bg-[color:var(--app-bg-soft)] disabled:cursor-not-allowed disabled:opacity-60"
                            >
                              {operationMutating['portal-status-check'] ? 'Checking...' : 'Check official status now'}
                            </button>
                            <button
                              type="button"
                              onClick={() => void handleGeneratePortalFollowUpDraft()}
                              disabled={operationMutating['portal-follow-up-draft']}
                              className="rounded-2xl border border-[color:var(--app-border-strong)] bg-white px-4 py-2 text-sm font-medium text-[color:var(--app-ink)] transition hover:bg-[color:var(--app-bg-soft)] disabled:cursor-not-allowed disabled:opacity-60"
                            >
                              {operationMutating['portal-follow-up-draft'] ? 'Drafting...' : 'Draft recruiter follow-up'}
                            </button>
                          </div>
                          {selectedApplicationRow?.hasNoReply ? (
                            <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50/60 p-4">
                              <p className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-amber-800">
                                No-reply fallback
                              </p>
                              <p className="mt-2 text-sm text-amber-900">
                                This application is blocked by a no-reply sender. Generate a reusable follow-up and paste it when you find a valid contact.
                              </p>
                              <textarea
                                value={selectedNoReplyDraft}
                                onChange={(event) => setSelectedNoReplyDraft(event.target.value)}
                                placeholder="Use Generate no-reply draft to fill this text."
                                className="mt-3 min-h-32 w-full rounded-2xl border border-amber-200 bg-white px-3 py-2 text-sm text-[color:var(--app-ink)] outline-none focus:border-amber-400"
                              />
                              <div className="mt-3 flex flex-wrap gap-3">
                                <button
                                  type="button"
                                  onClick={() => void handleGeneratePortalFollowUpDraft()}
                                  disabled={operationMutating['portal-follow-up-draft']}
                                  className="rounded-2xl border border-amber-300 bg-white px-4 py-2 text-sm font-medium text-amber-900 transition hover:bg-amber-100 disabled:cursor-not-allowed disabled:opacity-60"
                                >
                                  {operationMutating['portal-follow-up-draft'] ? 'Drafting...' : 'Generate no-reply draft'}
                                </button>
                                <button
                                  type="button"
                                  onClick={() => void handleCopyNoReplyDraft()}
                                  className="rounded-2xl border border-[color:var(--app-border-strong)] bg-white px-4 py-2 text-sm font-medium text-[color:var(--app-ink)] transition hover:bg-[color:var(--app-bg-soft)]"
                                >
                                  Copy draft
                                </button>
                              </div>
                            </div>
                          ) : null}
                          <ResourceBanner
                            title="Status history"
                            state={selectedStatusChecks}
                          />
                          {selectedStatusChecks.data.length ? (
                            <div className="mt-4 space-y-2">
                              {selectedStatusChecks.data.slice(0, 4).map((event) => (
                                <div
                                  key={event.id}
                                  className="rounded-2xl border border-[color:var(--app-border)] bg-[color:var(--app-bg-soft)] px-4 py-3"
                                >
                                  <div className="flex flex-wrap items-center justify-between gap-2">
                                    <p className="text-sm font-semibold text-[color:var(--app-ink)]">
                                      {event.new_status} - {event.confidence}
                                    </p>
                                    <p className="text-xs text-[color:var(--app-muted)]">
                                      {formatDate(event.checked_at)}
                                    </p>
                                  </div>
                                  <p className="mt-1 text-xs leading-5 text-[color:var(--app-muted)]">
                                    {event.evidence_summary ?? 'No evidence summary stored.'}
                                  </p>
                                  <p className="mt-1 text-xs text-[color:var(--app-muted)]">
                                    Login required: {event.login_required ? 'yes' : 'no'} - Credentials used: {event.credentials_used ? 'yes' : 'no'} - User action: {event.user_action_required ? 'yes' : 'no'}
                                  </p>
                                </div>
                              ))}
                            </div>
                          ) : null}
                          {selectedPortalCredentials.data.length ? (
                            <div className="mt-4 space-y-2">
                              {selectedPortalCredentials.data.map((credential) => (
                                <div
                                  key={credential.id}
                                  className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[color:var(--app-border)] bg-[color:var(--app-bg-soft)] px-4 py-3"
                                >
                                  <div>
                                    <p className="text-sm font-semibold text-[color:var(--app-ink)]">
                                      {credential.portal_name}
                                    </p>
                                    <p className="mt-1 text-xs text-[color:var(--app-muted)]">
                                      {credential.username} - MFA {credential.mfa_enabled ? 'enabled' : 'not marked'} - Daily check {credential.daily_check_allowed ? 'allowed' : 'off'}
                                    </p>
                                    <p className="mt-1 text-xs text-[color:var(--app-muted)]">
                                      Last checked: {formatDate(credential.last_checked_at)}
                                    </p>
                                  </div>
                                  <button
                                    type="button"
                                    onClick={() => void handleDeletePortalCredential(credential.id)}
                                    disabled={operationMutating[`portal-credential-delete-${credential.id}`]}
                                    className="rounded-2xl border border-rose-200 bg-white px-3 py-1.5 text-xs font-medium text-rose-700 transition hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-60"
                                  >
                                    Delete
                                  </button>
                                </div>
                              ))}
                            </div>
                          ) : null}
                          <div className="mt-4 grid gap-3 md:grid-cols-2">
                            <label className="block">
                              <span className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--app-muted)]">
                                Portal name
                              </span>
                              <input
                                value={portalCredentialForm.portal_name}
                                onChange={(event) =>
                                  setPortalCredentialForm((current) => ({
                                    ...current,
                                    portal_name: event.target.value,
                                  }))
                                }
                                placeholder="Workday, Greenhouse, company careers"
                                className="mt-2 w-full rounded-2xl border border-[color:var(--app-border)] bg-white px-3 py-2 text-sm text-[color:var(--app-ink)] outline-none focus:border-[color:var(--app-accent)]"
                              />
                            </label>
                            <label className="block">
                              <span className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--app-muted)]">
                                Portal URL
                              </span>
                              <input
                                value={portalCredentialForm.portal_url}
                                onChange={(event) =>
                                  setPortalCredentialForm((current) => ({
                                    ...current,
                                    portal_url: event.target.value,
                                  }))
                                }
                                placeholder="https://company.example/careers"
                                className="mt-2 w-full rounded-2xl border border-[color:var(--app-border)] bg-white px-3 py-2 text-sm text-[color:var(--app-ink)] outline-none focus:border-[color:var(--app-accent)]"
                              />
                            </label>
                            <label className="block">
                              <span className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--app-muted)]">
                                Username or email
                              </span>
                              <input
                                value={portalCredentialForm.username}
                                onChange={(event) =>
                                  setPortalCredentialForm((current) => ({
                                    ...current,
                                    username: event.target.value,
                                  }))
                                }
                                autoComplete="username"
                                className="mt-2 w-full rounded-2xl border border-[color:var(--app-border)] bg-white px-3 py-2 text-sm text-[color:var(--app-ink)] outline-none focus:border-[color:var(--app-accent)]"
                              />
                            </label>
                            <label className="block">
                              <span className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--app-muted)]">
                                Password
                              </span>
                              <input
                                type="password"
                                value={portalCredentialForm.password}
                                onChange={(event) =>
                                  setPortalCredentialForm((current) => ({
                                    ...current,
                                    password: event.target.value,
                                  }))
                                }
                                autoComplete="current-password"
                                className="mt-2 w-full rounded-2xl border border-[color:var(--app-border)] bg-white px-3 py-2 text-sm text-[color:var(--app-ink)] outline-none focus:border-[color:var(--app-accent)]"
                              />
                            </label>
                          </div>
                          <div className="mt-4 flex flex-wrap gap-4 text-sm text-[color:var(--app-muted)]">
                            <label className="inline-flex items-center gap-2">
                              <input
                                type="checkbox"
                                checked={portalCredentialForm.mfa_enabled}
                                onChange={(event) =>
                                  setPortalCredentialForm((current) => ({
                                    ...current,
                                    mfa_enabled: event.target.checked,
                                  }))
                                }
                              />
                              MFA enabled
                            </label>
                            <label className="inline-flex items-center gap-2">
                              <input
                                type="checkbox"
                                checked={portalCredentialForm.daily_check_allowed}
                                onChange={(event) =>
                                  setPortalCredentialForm((current) => ({
                                    ...current,
                                    daily_check_allowed: event.target.checked,
                                  }))
                                }
                              />
                              Allow one daily check
                            </label>
                          </div>
                          <button
                            type="button"
                            onClick={() => void handleSavePortalCredential()}
                            disabled={operationMutating['portal-credential-save']}
                            className="mt-4 rounded-2xl bg-[color:var(--app-ink)] px-4 py-2 text-sm font-medium text-white transition hover:opacity-92 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {operationMutating['portal-credential-save'] ? 'Saving...' : 'Save encrypted credential'}
                          </button>
                        </div>

                        <div className="flex flex-wrap gap-3">
                          <button
                            type="button"
                            onClick={() => void handleSyncNextActions()}
                            disabled={applicationMutating}
                            className="rounded-2xl bg-[color:var(--app-ink)] px-4 py-2 text-sm font-medium text-white transition hover:opacity-92 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {applicationMutating ? 'Working...' : 'Sync next actions'}
                          </button>
                          {!selectedApplicationTracker.data.applied_at ? (
                            <button
                              type="button"
                              onClick={() => void handleMarkApplied()}
                              disabled={applicationMutating}
                              className="rounded-2xl border border-[color:var(--app-border-strong)] bg-white px-4 py-2 text-sm font-medium text-[color:var(--app-ink)] transition hover:bg-[color:var(--app-bg-soft)] disabled:cursor-not-allowed disabled:opacity-60"
                            >
                              Mark applied
                            </button>
                          ) : null}
                        </div>
                      </div>
                    ) : (
                      <EmptyState
                        title="No application selected"
                        body="Choose an application to review its artifact readiness and next actions."
                      />
                    )}
                  </Panel>

                  <Panel
                    title="Action queue"
                    subtitle={`${selectedApplicationActions.data.length} actions linked to the selected application`}
                  >
                    <ResourceBanner
                      title="Application actions"
                      state={selectedApplicationActions}
                    />
                    <div className="mb-3 flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => setActionFilter('all')}
                        className={`rounded-2xl px-3 py-1.5 text-xs font-medium ring-1 ${actionFilter === 'all' ? 'bg-[color:var(--app-ink)] text-white ring-[color:var(--app-ink)]' : 'bg-white text-[color:var(--app-muted)] ring-[color:var(--app-border)]'}`}
                      >
                        All
                      </button>
                      <button
                        type="button"
                        onClick={() => setActionFilter('possible')}
                        className={`rounded-2xl px-3 py-1.5 text-xs font-medium ring-1 ${actionFilter === 'possible' ? 'bg-emerald-600 text-white ring-emerald-600' : 'bg-white text-[color:var(--app-muted)] ring-[color:var(--app-border)]'}`}
                      >
                        Action possible
                      </button>
                      <button
                        type="button"
                        onClick={() => setActionFilter('blocked')}
                        className={`rounded-2xl px-3 py-1.5 text-xs font-medium ring-1 ${actionFilter === 'blocked' ? 'bg-amber-600 text-white ring-amber-600' : 'bg-white text-[color:var(--app-muted)] ring-[color:var(--app-border)]'}`}
                      >
                        Action blocked
                      </button>
                      <button
                        type="button"
                        onClick={() => setActionFilter('none')}
                        className={`rounded-2xl px-3 py-1.5 text-xs font-medium ring-1 ${actionFilter === 'none' ? 'bg-slate-700 text-white ring-slate-700' : 'bg-white text-[color:var(--app-muted)] ring-[color:var(--app-border)]'}`}
                      >
                        No action
                      </button>
                    </div>
                    {appIsRejected ? (
                      <p className="mb-3 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-800">
                        Application is rejected. No outbound recruiter action is expected.
                      </p>
                    ) : null}
                    {appIsWaiting ? (
                      <p className="mb-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                        Application is in waiting state. Actions may depend on new recruiter emails.
                      </p>
                    ) : null}
                    {actionRows.length ? (
                      <div className="space-y-4">
                        {actionRows.map(({ action, blockedReply }) => (
                          <article
                            key={action.id}
                            className="rounded-[1.35rem] border border-[color:var(--app-border)] bg-[color:var(--app-surface-strong)] p-4"
                          >
                            <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                              <div>
                                <p className="text-sm font-medium text-[color:var(--app-ink)]">{action.title}</p>
                                <p className="mt-1 text-sm text-[color:var(--app-muted)]">
                                  {action.action_type}
                                </p>
                              </div>
                              <div className="flex flex-wrap gap-2">
                                <span
                                  className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${getPriorityTone(action.priority)}`}
                                >
                                  {action.priority}
                                </span>
                                <span
                                  className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${getStatusTone(action.status)}`}
                                >
                                  {action.status}
                                </span>
                              </div>
                            </div>

                            <p className="mt-3 text-sm leading-6 text-[color:var(--app-muted)]">
                              {truncate(action.details, 220)}
                            </p>
                            <p className="mt-3 text-xs text-[color:var(--app-muted)]/80">
                              Due {formatDate(action.due_at)} - Updated {formatRelativeDate(action.updated_at)}
                            </p>

                            {action.status === 'open' ? (
                              <div className="mt-4 flex flex-wrap gap-3">
                                {(action.action_type === 'respond_to_recruiter' || action.action_type === 'send_follow_up') ? (
                                  (() => {
                                    const blocked = blockedReply
                                    const emailMutatingKey = action.email_id ?? ''
                                    return (
                                  <button
                                    type="button"
                                    onClick={() => action.email_id ? void handleCreateGmailReplyDraft(action.email_id as string) : undefined}
                                    disabled={Boolean(emailMutating[emailMutatingKey]) || blocked}
                                    className="rounded-2xl border border-[color:var(--app-border-strong)] bg-white px-3 py-2 text-sm font-medium text-[color:var(--app-ink)] transition hover:bg-[color:var(--app-bg-soft)] disabled:cursor-not-allowed disabled:opacity-60"
                                  >
                                    {!action.email_id ? 'No linked email' : blocked ? 'No-reply sender' : emailMutating[emailMutatingKey] ? 'Creating draft...' : 'Reply in Gmail'}
                                  </button>
                                    )
                                  })()
                                ) : null}
                                <button
                                  type="button"
                                  onClick={() => void handleUpdateAction(action.id, 'completed')}
                                  disabled={actionMutating[action.id]}
                                  className="rounded-2xl bg-emerald-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
                                >
                                  {actionMutating[action.id] ? 'Saving...' : 'Mark complete'}
                                </button>
                                <button
                                  type="button"
                                  onClick={() => void handleUpdateAction(action.id, 'dismissed')}
                                  disabled={actionMutating[action.id]}
                                  className="rounded-2xl border border-[color:var(--app-border-strong)] bg-white px-3 py-2 text-sm font-medium text-[color:var(--app-ink)] transition hover:bg-[color:var(--app-bg-soft)] disabled:cursor-not-allowed disabled:opacity-60"
                                >
                                  Dismiss
                                </button>
                              </div>
                            ) : null}
                          </article>
                        ))}
                      </div>
                    ) : (
                      <EmptyState
                        title="No actions in this filter"
                        body="Switch filter or sync next actions if you expect additional tasks."
                      />
                    )}
                  </Panel>
                </div>
              </div>
            ) : null}

            {activeSection === 'inbox' ? (
              <InboxSection
                emails={emails}
                inboxEmails={inboxEmails}
                applications={applications}
                jobsById={jobsById}
                emailMutating={emailMutating}
                formatDate={formatDate}
                getPriorityTone={getPriorityTone}
                gmailThreadUrl={gmailThreadUrl}
                isNoReplySender={isNoReplySender}
                handleLinkEmail={handleLinkEmail}
                handleCreateGmailReplyDraft={handleCreateGmailReplyDraft}
                getEmailApplicationOptions={getEmailApplicationOptions}
                Panel={Panel}
                ResourceBanner={ResourceBanner}
                TriageAuditPanel={TriageAuditPanel}
              />
            ) : null}

            {activeSection === 'profile' ? (
              <ProfileSection profile={profile} Panel={Panel} ResourceBanner={ResourceBanner} />
            ) : null}
          </main>
        </div>
      </div>
    </div>
  )
}

export default App

