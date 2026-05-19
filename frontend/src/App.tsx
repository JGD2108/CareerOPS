import { useEffect, useMemo, useState } from 'react'
import type { Dispatch, ReactNode, SetStateAction } from 'react'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000/api/v1'
const CAREEROPS_API_KEY = import.meta.env.VITE_CAREEROPS_API_KEY ?? ''
const API_HOSTNAME = (() => {
  try {
    return new URL(API_BASE_URL).hostname
  } catch {
    return ''
  }
})()
const IS_LOCAL_API = API_HOSTNAME === '127.0.0.1' || API_HOSTNAME === 'localhost'

type Company = {
  id: string
  name: string
  website_url: string | null
  notes: string | null
  created_at: string
  updated_at: string
}

type Job = {
  id: string
  title: string
  source: string
  source_url: string | null
  location: string | null
  work_mode: string | null
  seniority: string | null
  description: string
  raw_payload: Record<string, unknown> | null
  source_trace: Record<string, unknown> | null
  company: Company | null
  created_at: string
  updated_at: string
}

type Application = {
  id: string
  job_id: string
  status: string
  notes: string | null
  applied_at: string | null
  created_at: string
  updated_at: string
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

type Email = {
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

type ProfileSkill = {
  id: string
  name: string
  category: string | null
  evidence_level: string
  evidence_text: string
}

type ProfileProject = {
  id: string
  name: string
  description: string | null
  technologies: string[] | null
  impact: string | null
  evidence_text: string
}

type ProfileExperience = {
  id: string
  company: string
  title: string
  location: string | null
  start_date: string | null
  end_date: string | null
  bullets: string[] | null
  evidence_text: string
}

type CandidateProfile = {
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

type GmailStatus = {
  credentials_file_exists: boolean
  token_file_exists: boolean
  authenticated: boolean
  scopes: string[]
}

type GmailOAuthStart = {
  authorization_url: string
  state: string
  redirect_uri: string
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

type ResourceState<T> = {
  data: T
  loading: boolean
  error: string | null
  unavailable: boolean
}

type AppSection = 'overview' | 'setup' | 'jobs' | 'applications' | 'inbox' | 'profile'
type ActionMutationState = Record<string, boolean>
type EmailMutationState = Record<string, boolean>

const DEFAULT_SECTIONS: Array<{ id: AppSection; label: string }> = [
  { id: 'overview', label: 'Overview' },
  { id: 'setup', label: 'Setup' },
  { id: 'jobs', label: 'Jobs' },
  { id: 'applications', label: 'Applications' },
  { id: 'inbox', label: 'Inbox' },
  { id: 'profile', label: 'Profile' },
]

function createInitialResource<T>(initialData: T): ResourceState<T> {
  return {
    data: initialData,
    loading: true,
    error: null,
    unavailable: false,
  }
}

async function requestApi<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)
  if (init?.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  if (CAREEROPS_API_KEY && !headers.has('X-CareerOps-Key')) {
    headers.set('X-CareerOps-Key', CAREEROPS_API_KEY)
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
  })

  if (!response.ok) {
    const error = new Error(`Request failed with status ${response.status}`)
    ;(error as Error & { status?: number }).status = response.status
    throw error
  }

  return (await response.json()) as T
}

function cvArtifactUrl(cvVersionId: string, artifactFormat: 'pdf' | 'tex'): string {
  return `${API_BASE_URL}/cv-versions/${cvVersionId}/download?artifact_format=${artifactFormat}`
}

async function loadResource<T>(
  path: string,
  setter: Dispatch<SetStateAction<ResourceState<T>>>,
  initialData: T,
) {
  setter({
    data: initialData,
    loading: true,
    error: null,
    unavailable: false,
  })

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
    setter({
      data: initialData,
      loading: false,
      error: error instanceof Error ? error.message : 'Unknown error',
      unavailable: status === 404,
    })
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

function truncate(text: string | null | undefined, maxLength: number): string {
  if (!text) {
    return 'No content available.'
  }

  if (text.length <= maxLength) {
    return text
  }

  return `${text.slice(0, maxLength - 3)}...`
}

function formatSourceLabel(source: string): string {
  return source
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

function gmailThreadUrl(email: Email): string | null {
  if (!email.gmail_thread_id) {
    return null
  }
  return `https://mail.google.com/mail/u/0/#inbox/${email.gmail_thread_id}`
}

function payloadText(value: unknown): string {
  if (!value) {
    return 'No raw source metadata stored yet.'
  }
  return JSON.stringify(value, null, 2)
}

function cleanDisplayName(name: string | null | undefined): string {
  if (!name) {
    return 'Profile not loaded'
  }

  return cleanDisplayText(name)
    .replace(/[´`']\s*([AEIOUaeiou])/g, (_, vowel: string) => {
      const accents: Record<string, string> = {
        a: 'á',
        e: 'é',
        i: 'í',
        o: 'ó',
        u: 'ú',
        A: 'Á',
        E: 'É',
        I: 'Í',
        O: 'Ó',
        U: 'Ú',
      }
      return accents[vowel] ?? vowel
    })
    .replace(/\s+/g, ' ')
    .trim()
}

function cleanDisplayText(text: string): string {
  return text
    .replace(/Ã¡/g, 'á')
    .replace(/Ã©/g, 'é')
    .replace(/Ã­/g, 'í')
    .replace(/Ã³/g, 'ó')
    .replace(/Ãº/g, 'ú')
    .replace(/Ã±/g, 'ñ')
    .replace(/Ã/g, 'Á')
    .replace(/Ã‰/g, 'É')
    .replace(/Ã/g, 'Í')
    .replace(/Ã“/g, 'Ó')
    .replace(/Ãš/g, 'Ú')
    .replace(/Ã‘/g, 'Ñ')
    .replace(/â/g, '—')
    .replace(/â/g, '–')
    .replace(/â/g, "'")
    .replace(/â/g, '"')
    .replace(/â/g, '"')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .replace(/\u00c2/g, '')
    .replace(/\u0091/g, '')
    .replace(/\u0098/g, '')
    .replace(/\u0099/g, '')
    .trim()
}

function getProfilePreference(
  preferences: Record<string, unknown> | null | undefined,
  key: string,
): string | null {
  const value = preferences?.[key]
  if (typeof value === 'string' && value.trim()) {
    return value.trim()
  }
  if (Array.isArray(value)) {
    const tokens = value
      .filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
      .map((item) => cleanDisplayText(item))
    return tokens.length ? tokens.join(', ') : null
  }
  return null
}

function normalizeForMatch(value: string | null | undefined): string {
  return cleanDisplayText(value ?? '').toLowerCase()
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

function MetricCard(props: { label: string; value: string | number; note: string }) {
  return (
    <article className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-sm font-medium text-slate-500">{props.label}</p>
      <p className="mt-2 text-3xl font-semibold text-slate-900">{props.value}</p>
      <p className="mt-2 text-sm text-slate-600">{props.note}</p>
    </article>
  )
}

function ResourceBanner(props: { title: string; state: ResourceState<unknown> }) {
  if (props.state.loading) {
    return (
      <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
        Loading {props.title.toLowerCase()}...
      </div>
    )
  }

  if (props.state.unavailable) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        {props.title} endpoint is currently unavailable. The dashboard stays usable, but this section needs the latest FastAPI server build.
      </div>
    )
  }

  if (props.state.error) {
    return (
      <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-900">
        {props.title} could not be loaded: {props.state.error}
      </div>
    )
  }

  return null
}

function Panel(props: { title: string; subtitle?: string; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <div>
        <h2 className="text-lg font-semibold text-slate-950">{props.title}</h2>
        {props.subtitle ? (
          <p className="mt-1 text-sm text-slate-600">{props.subtitle}</p>
        ) : null}
      </div>
      <div className="mt-4">{props.children}</div>
    </section>
  )
}

function EmptyState(props: { title: string; body: string }) {
  return (
    <div className="rounded-md border border-dashed border-slate-300 bg-slate-50 p-4">
      <p className="text-sm font-medium text-slate-900">{props.title}</p>
      <p className="mt-1 text-sm text-slate-600">{props.body}</p>
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
      className={`flex items-center justify-between rounded-md px-3 py-2 text-left text-sm font-medium transition ${
        props.active
          ? 'bg-slate-900 text-white'
          : 'text-slate-700 hover:bg-slate-100'
      }`}
    >
      <span>{props.label}</span>
      {props.badge !== undefined ? (
        <span
          className={`rounded-sm px-2 py-0.5 text-xs ${
            props.active ? 'bg-white/15 text-white' : 'bg-slate-200 text-slate-700'
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
        ? 'border-slate-200 bg-slate-50 text-slate-700'
        : 'border-amber-200 bg-amber-50 text-amber-950'

  return (
    <article className={`rounded-md border p-4 ${tone}`}>
      <div className="flex items-start gap-3">
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-sm bg-white/70 text-sm font-semibold">
          {props.status === 'done' ? 'OK' : props.index}
        </span>
        <div>
          <p className="text-sm font-semibold">{props.title}</p>
          <p className="mt-1 text-sm leading-6">{props.body}</p>
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
  onConnectGmail: () => void
  onOpenSetup: () => void
  onEnterDashboard: () => void
}) {
  const gmailReady = Boolean(props.gmailStatus.data?.authenticated)
  const profileReady = Boolean(props.profile.data)
  const documentsReady = props.documents.data.length > 0
  const loading =
    props.gmailStatus.loading || props.profile.loading || props.documents.loading

  return (
    <div className="min-h-screen bg-slate-100 px-4 py-6 text-slate-900 lg:px-8">
      <main className="mx-auto flex min-h-[calc(100vh-3rem)] max-w-6xl flex-col justify-center">
        <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm lg:p-8">
          <div className="grid gap-8 lg:grid-cols-[minmax(0,1.1fr)_minmax(360px,0.9fr)] lg:items-center">
            <div>
              <p className="text-sm font-semibold text-sky-700">CareerOps Agent</p>
              <h1 className="mt-3 max-w-3xl text-3xl font-semibold tracking-tight text-slate-950 lg:text-5xl">
                Private job-search operations for better applications.
              </h1>
              <p className="mt-5 max-w-2xl text-base leading-7 text-slate-600">
                Connect Gmail, load your verified profile sources, then use the dashboard
                to review jobs, recruiter signals, CV drafts, and next actions with a human
                approval loop.
              </p>

              <div className="mt-6 flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={props.onConnectGmail}
                  disabled={props.gmailConnecting || !props.gmailStatus.data?.credentials_file_exists}
                  className="rounded-md bg-slate-950 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {props.gmailConnecting
                    ? 'Opening Google...'
                    : gmailReady
                      ? 'Reconnect Gmail'
                      : 'Connect Gmail'}
                </button>
                <button
                  type="button"
                  onClick={props.onOpenSetup}
                  className="rounded-md border border-slate-300 bg-white px-5 py-3 text-sm font-semibold text-slate-800 transition hover:bg-slate-50"
                >
                  Upload CV and LinkedIn
                </button>
                <button
                  type="button"
                  onClick={props.onEnterDashboard}
                  className="rounded-md border border-slate-300 bg-slate-50 px-5 py-3 text-sm font-semibold text-slate-800 transition hover:bg-slate-100"
                >
                  Enter dashboard
                </button>
              </div>

              {props.operationMessage ? (
                <div className="mt-5 rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
                  {props.operationMessage}
                </div>
              ) : null}
              {props.operationError ? (
                <div className="mt-5 rounded-md border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-900">
                  {props.operationError}
                </div>
              ) : null}
            </div>

            <div className="space-y-3">
              <SetupStep
                index={1}
                title="Gmail OAuth"
                body={
                  gmailReady
                    ? 'Gmail is authenticated. The inbox agent can sync and classify recruiter signals.'
                    : props.gmailStatus.data?.credentials_file_exists
                      ? 'Connect your Gmail account so CareerOps can read relevant alerts and recruiter emails.'
                      : 'Gmail credentials are missing in the backend environment.'
                }
                status={loading ? 'loading' : gmailReady ? 'done' : 'pending'}
              />
              <SetupStep
                index={2}
                title="Evidence documents"
                body={
                  documentsReady
                    ? `${props.documents.data.length} source document(s) are stored for profile extraction.`
                    : 'Upload your CV, LinkedIn PDF/text, and LaTeX template before generating tailored materials.'
                }
                status={props.documents.loading ? 'loading' : documentsReady ? 'done' : 'pending'}
              />
              <SetupStep
                index={3}
                title="Candidate profile"
                body={
                  profileReady
                    ? `${cleanDisplayName(props.profile.data?.display_name)} is ready for scoring and CV tailoring.`
                    : 'Run the AI profile agent after uploading documents. The system will use only supported evidence.'
                }
                status={props.profile.loading ? 'loading' : profileReady ? 'done' : 'pending'}
              />
            </div>
          </div>
        </section>
      </main>
    </div>
  )
}

function App() {
  const [activeSection, setActiveSection] = useState<AppSection>('overview')
  const [dashboardUnlocked, setDashboardUnlocked] = useState(() => {
    const params = new URLSearchParams(window.location.search)
    return window.location.hash === '#dashboard' || params.get('gmail') === 'connected'
  })
  const [jobSearch, setJobSearch] = useState('')
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null)
  const [selectedApplicationId, setSelectedApplicationId] = useState<string | null>(null)
  const [applicationMutating, setApplicationMutating] = useState(false)
  const [actionMutating, setActionMutating] = useState<ActionMutationState>({})
  const [emailMutating, setEmailMutating] = useState<EmailMutationState>({})
  const [operationMutating, setOperationMutating] = useState<Record<string, boolean>>({})
  const [operationMessage, setOperationMessage] = useState<string | null>(null)
  const [operationError, setOperationError] = useState<string | null>(null)
  const [documentSourceType, setDocumentSourceType] = useState('linkedin')
  const [selectedDocument, setSelectedDocument] = useState<File | null>(null)
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
  const [selectedJobSemanticMatches, setSelectedJobSemanticMatches] = useState<
    ResourceState<SemanticMatch[]>
  >(createInitialResource([]))
  const [selectedApplicationTracker, setSelectedApplicationTracker] = useState<
    ResourceState<ApplicationTracker | null>
  >(createInitialResource<ApplicationTracker | null>(null))
  const [selectedApplicationActions, setSelectedApplicationActions] = useState<
    ResourceState<Action[]>
  >(createInitialResource([]))

  useEffect(() => {
    void loadResource<Job[]>('/jobs', setJobs, [])
    void loadResource<Application[]>('/applications', setApplications, [])
    void loadResource<Action[]>('/actions', setActions, [])
    void loadResource<Email[]>('/emails', setEmails, [])
    void loadResource<CandidateProfile | null>('/profile', setProfile, null)
    void loadResource<DocumentRecord[]>('/documents', setDocuments, [])
    void loadResource<GmailStatus | null>('/gmail/status', setGmailStatusState, null)
    void loadResource<NotificationSummary[]>('/notifications/daily-summary', setSummaries, [])
  }, [])

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
    )
    void loadResource<CVVersion[]>(
      `/jobs/${effectiveSelectedJobId}/cv-tailoring-plans`,
      setSelectedJobCvVersions,
      [],
    )
    void loadResource<MessageDraft[]>(
      `/jobs/${effectiveSelectedJobId}/message-drafts`,
      setSelectedJobDrafts,
      [],
    )
    void loadResource<SemanticMatch[]>(
      `/jobs/${effectiveSelectedJobId}/semantic-matches`,
      setSelectedJobSemanticMatches,
      [],
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
    )
    void loadResource<Action[]>(
      `/applications/${effectiveSelectedApplicationId}/actions`,
      setSelectedApplicationActions,
      [],
    )
  }, [effectiveSelectedApplicationId])

  const jobsById = useMemo(() => new Map(jobs.data.map((job) => [job.id, job])), [jobs.data])

  const latestSummary = useMemo(() => {
    return [...summaries.data].sort((left, right) =>
      right.summary_date.localeCompare(left.summary_date),
    )[0]
  }, [summaries.data])

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

  const selectedJobScore = selectedJobScores.data[0] ?? null
  const approvedCvCount = selectedJobCvVersions.data.filter(
    (version) => version.status === 'approved',
  ).length
  const approvedDraftCount = selectedJobDrafts.data.filter(
    (draft) => draft.status === 'approved',
  ).length

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

  async function runOperation(label: string, operation: () => Promise<string>) {
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
  }

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
    ])
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
      return `Uploaded ${selectedDocument.name}. You can now extract the profile from stored sources.`
    })
  }

  async function handleExtractProfile() {
    await runOperation('extract-profile', async () => {
      if (!latestCvDocument) {
        throw new Error('Upload your base CV as source type "Base CV" before building the profile.')
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

  async function handleSyncGmail() {
    await runOperation('sync-gmail', async () => {
      const syncedEmails = await requestApi<Email[]>('/gmail/sync', {
        method: 'POST',
        body: JSON.stringify({
          query: 'category:primary newer_than:30d',
          max_results: 25,
          skip_existing: true,
        }),
      })
      await Promise.all([
        loadResource<Email[]>('/emails', setEmails, []),
        loadResource<GmailStatus | null>('/gmail/status', setGmailStatusState, null),
      ])
      return `Gmail incremental sync finished: ${syncedEmails.length} new relevant emails normalized and classified.`
    })
  }

  async function handleRunGmailAuth() {
    await runOperation('gmail-auth', async () => {
      const status = await requestApi<GmailStatus>('/gmail/auth', {
        method: 'POST',
      })
      await loadResource<GmailStatus | null>('/gmail/status', setGmailStatusState, null)
      return status.authenticated
        ? 'Gmail OAuth completed. You can now sync recruiter emails and LinkedIn alerts.'
        : 'Gmail OAuth finished, but the token was not detected yet. Refresh status and try again.'
    })
  }

  async function handleStartGmailWebOAuth() {
    await runOperation('gmail-web-oauth', async () => {
      const result = await requestApi<GmailOAuthStart>('/gmail/oauth/start')
      window.location.href = result.authorization_url
      return `Gmail OAuth opened. Redirect URI: ${result.redirect_uri}`
    })
  }

  function enterDashboard(section: AppSection = 'overview') {
    setActiveSection(section)
    setDashboardUnlocked(true)
    window.history.replaceState(null, '', '#dashboard')
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
      return `LinkedIn via Gmail synced: ${result.job_alerts} job alerts, ${result.application_confirmations} application confirmations, ${result.jobs_imported} new jobs, ${result.applications_marked_applied} applied records, ${result.jobs_auto_scored} auto-scored jobs.`
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
      return `AI email triage reviewed ${triagedEmails.length} filtered unlinked emails using the low-cost inbox model.`
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
      return `Reclassified ${updatedEmails.length} emails and imported LinkedIn job alerts where possible.`
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
      loadResource<Application[]>('/applications', setApplications, []),
      loadResource<Action[]>('/actions', setActions, []),
      loadResource<ApplicationTracker | null>(
        `/applications/${applicationId}`,
        setSelectedApplicationTracker,
        null,
      ),
      loadResource<Action[]>(
        `/applications/${applicationId}/actions`,
        setSelectedApplicationActions,
        [],
      ),
    ])
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

  if (!dashboardUnlocked) {
    return (
      <SetupHome
        gmailStatus={gmailStatusState}
        profile={profile}
        documents={documents}
        operationMessage={operationMessage}
        operationError={operationError}
        gmailConnecting={Boolean(operationMutating['gmail-web-oauth'])}
        onConnectGmail={() => void handleStartGmailWebOAuth()}
        onOpenSetup={() => enterDashboard('setup')}
        onEnterDashboard={() => enterDashboard('overview')}
      />
    )
  }

  return (
    <div className="min-h-screen bg-slate-100 text-slate-900">
      <div className="mx-auto flex min-h-screen max-w-[1680px] flex-col gap-6 px-4 py-4 lg:px-6">
        <header className="rounded-lg border border-slate-200 bg-white px-5 py-4 shadow-sm">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="space-y-1">
              <p className="text-sm font-medium text-sky-700">CareerOps Agent</p>
              <h1 className="text-2xl font-semibold tracking-tight text-slate-950">
                Search operations dashboard
              </h1>
              <p className="max-w-3xl text-sm text-slate-600">
                One place to review discovery, active applications, recruiter inbox
                signals, and the next action queue without leaving the system.
              </p>
            </div>
            <div className="grid grid-cols-2 gap-3 lg:min-w-[420px] lg:grid-cols-3">
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
        </header>

        <div className="grid min-h-0 flex-1 gap-6 lg:grid-cols-[240px_minmax(0,1fr)]">
          <aside className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
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

            <div className="mt-6 rounded-md border border-slate-200 bg-slate-50 p-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Current profile
              </p>
              <p className="mt-2 text-sm font-medium text-slate-900">
                {cleanDisplayName(profile.data?.display_name)}
              </p>
              <p className="mt-1 text-sm text-slate-600">
                {profile.data?.headline
                  ? cleanDisplayText(profile.data.headline)
                  : 'Waiting for profile extraction'}
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                <span className="rounded-sm bg-slate-200 px-2 py-1 text-xs text-slate-700">
                  {profile.data?.skills.length ?? 0} skills
                </span>
                <span className="rounded-sm bg-slate-200 px-2 py-1 text-xs text-slate-700">
                  {profile.data?.projects.length ?? 0} projects
                </span>
                <span className="rounded-sm bg-slate-200 px-2 py-1 text-xs text-slate-700">
                  {profile.data?.experiences.length ?? 0} experiences
                </span>
              </div>
            </div>
          </aside>

          <main className="min-w-0 space-y-6">
            {operationMessage ? (
              <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
                {operationMessage}
              </div>
            ) : null}
            {operationError ? (
              <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-900">
                {operationError}
              </div>
            ) : null}

            {activeSection === 'overview' ? (
              <>
                <div className="grid gap-6 xl:grid-cols-[minmax(0,1.7fr)_minmax(320px,1fr)]">
                  <Panel
                    title="Daily operating picture"
                    subtitle="Snapshot of the current pipeline using the latest stored summary, with fallback to live collections where available."
                  >
                    <ResourceBanner title="Daily summary" state={summaries} />
                    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
                      <MetricCard
                        label="New jobs"
                        value={latestSummary?.content.counts?.new_jobs ?? jobs.data.length}
                        note="Tracked in the discovery layer"
                      />
                      <MetricCard
                        label="Top matches"
                        value={latestSummary?.content.counts?.top_matches ?? 0}
                        note="Highest confidence jobs already scored"
                      />
                      <MetricCard
                        label="Important emails"
                        value={
                          latestSummary?.content.counts?.important_emails ??
                          importantEmails.length
                        }
                        note="High urgency or reply-required inbox items"
                      />
                      <MetricCard
                        label="Open actions"
                        value={latestSummary?.content.counts?.open_actions ?? openActions.length}
                        note="Follow-ups, interview prep, or submission tasks"
                      />
                      <MetricCard
                        label="Pending applications"
                        value={
                          latestSummary?.content.counts?.pending_applications ??
                          pendingApplications.length
                        }
                        note="Still waiting for manual submission or review"
                      />
                    </div>

                    {latestSummary?.content.top_matches?.length ? (
                      <div className="mt-5 grid gap-3 xl:grid-cols-2">
                        {latestSummary.content.top_matches.map((match, index) => (
                          <article
                            key={`${match.title ?? 'job'}-${index}`}
                            className="rounded-md border border-slate-200 bg-slate-50 p-4"
                          >
                            <div className="flex items-center justify-between gap-3">
                              <div>
                                <p className="text-sm font-medium text-slate-900">
                                  {match.company ?? 'Unknown company'}
                                </p>
                                <p className="mt-1 text-sm text-slate-600">
                                  {match.title ?? 'Unknown role'}
                                </p>
                              </div>
                              <span
                                className={`inline-flex rounded-sm px-2 py-1 text-xs font-medium ${getRecommendationTone(match.recommendation)}`}
                              >
                                {match.recommendation}
                              </span>
                            </div>
                            <p className="mt-3 text-sm text-slate-700">
                              Score: {match.score}
                            </p>
                          </article>
                        ))}
                      </div>
                    ) : null}
                  </Panel>

                  <Panel title="Profile readiness">
                    <ResourceBanner title="Profile" state={profile} />
                    {profile.data ? (
                      <div className="space-y-4">
                        <div>
                          <p className="text-sm font-medium text-slate-800">
                            {cleanDisplayName(profile.data.display_name)}
                          </p>
                          <p className="mt-1 text-sm text-slate-600">
                            {profile.data.headline
                              ? cleanDisplayText(profile.data.headline)
                              : 'Headline not set yet'}
                          </p>
                          <p className="mt-1 text-sm text-slate-500">
                            {profile.data.location
                              ? cleanDisplayText(profile.data.location)
                              : 'Location not set yet'}
                          </p>
                        </div>
                        <p className="text-sm leading-6 text-slate-700">
                          {truncate(
                            profile.data.summary
                              ? cleanDisplayText(profile.data.summary)
                              : profile.data.summary,
                            320,
                          )}
                        </p>
                        <div className="flex flex-wrap gap-2">
                          {profile.data.skills.slice(0, 8).map((skill) => (
                            <span
                              key={skill.id}
                              className="rounded-sm bg-sky-50 px-2 py-1 text-xs font-medium text-sky-800 ring-1 ring-sky-200"
                            >
                              {skill.name}
                            </span>
                          ))}
                        </div>
                      </div>
                    ) : null}
                  </Panel>
                </div>

                <div className="grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
                  <Panel
                    title="Priority pipeline"
                    subtitle="Applications that still need a human move or already have a live signal."
                  >
                    <div className="overflow-hidden rounded-md border border-slate-200">
                      <table className="min-w-full divide-y divide-slate-200">
                        <thead className="bg-slate-50">
                          <tr>
                            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                              Company / role
                            </th>
                            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                              Status
                            </th>
                            <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                              Timing
                            </th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-200 bg-white">
                          {applications.data.slice(0, 6).map((application) => {
                            const job = jobsById.get(application.job_id)
                            return (
                              <tr key={application.id}>
                                <td className="px-4 py-3 align-top">
                                  <p className="text-sm font-medium text-slate-900">
                                    {job?.company?.name ?? 'Unknown company'}
                                  </p>
                                  <p className="mt-1 text-sm text-slate-600">
                                    {job?.title ?? 'Unknown role'}
                                  </p>
                                </td>
                                <td className="px-4 py-3 align-top">
                                  <span
                                    className={`inline-flex rounded-sm px-2 py-1 text-xs font-medium ${getStatusTone(application.status)}`}
                                  >
                                    {application.status}
                                  </span>
                                </td>
                                <td className="px-4 py-3 align-top text-sm text-slate-600">
                                  <p>{formatRelativeDate(application.updated_at)}</p>
                                  <p className="mt-1 text-xs text-slate-500">
                                    {application.applied_at
                                      ? `Applied ${formatDate(application.applied_at)}`
                                      : 'Not applied yet'}
                                  </p>
                                </td>
                              </tr>
                            )
                          })}
                        </tbody>
                      </table>
                    </div>
                  </Panel>

                  <Panel title="Inbox and actions">
                    <ResourceBanner title="Actions" state={actions} />
                    <ResourceBanner title="Emails" state={emails} />

                    <div className="space-y-3">
                      {openActions.slice(0, 4).map((action) => {
                        const application = applications.data.find(
                          (candidate) => candidate.id === action.application_id,
                        )
                        const job = application ? jobsById.get(application.job_id) : null
                        return (
                          <article
                            key={action.id}
                            className="rounded-md border border-slate-200 bg-slate-50 p-3"
                          >
                            <div className="flex items-center justify-between gap-3">
                              <p className="text-sm font-medium text-slate-900">{action.title}</p>
                              <span
                                className={`inline-flex rounded-sm px-2 py-1 text-xs font-medium ${getPriorityTone(action.priority)}`}
                              >
                                {action.priority}
                              </span>
                            </div>
                            <p className="mt-1 text-sm text-slate-600">
                              {job?.company?.name ?? 'Unknown company'} -{' '}
                              {job?.title ?? 'Unknown role'}
                            </p>
                            <p className="mt-2 text-sm text-slate-700">
                              {truncate(action.details, 140)}
                            </p>
                          </article>
                        )
                      })}

                      {openActions.length === 0 ? (
                        <EmptyState
                          title="No open actions right now"
                          body="The queue is either clear or waiting for the next recruiter signal."
                        />
                      ) : null}

                      {importantEmails.slice(0, 3).map((email) => (
                        <article
                          key={email.id}
                          className="rounded-md border border-slate-200 bg-white p-3"
                        >
                          <div className="flex items-center justify-between gap-3">
                            <p className="text-sm font-medium text-slate-900">
                              {email.company_name ?? email.from_name ?? email.from_email}
                            </p>
                            <span
                              className={`inline-flex rounded-sm px-2 py-1 text-xs font-medium ${getPriorityTone(email.urgency)}`}
                            >
                              {email.category}
                            </span>
                          </div>
                          <p className="mt-1 text-sm text-slate-600">
                            {truncate(email.subject, 100)}
                          </p>
                          <p className="mt-2 text-sm text-slate-700">
                            {truncate(cleanDisplayText(email.snippet ?? email.body_text ?? ''), 160)}
                          </p>
                        </article>
                      ))}
                    </div>
                  </Panel>
                </div>
              </>
            ) : null}

            {activeSection === 'setup' ? (
              <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                <Panel
                  title="Profile setup"
                  subtitle="Upload CV, LinkedIn export, or LaTeX template files, then rebuild the structured candidate profile from stored evidence."
                >
                  <div className="space-y-4">
                    <div className="rounded-md border border-slate-200 bg-slate-50 p-4">
                      <p className="text-sm font-medium text-slate-900">
                        Safe LinkedIn workflow
                      </p>
                      <p className="mt-2 text-sm leading-6 text-slate-700">
                        CareerOps uses your exported PDF or copied LinkedIn text as a document
                        source. It does not automate LinkedIn login, browsing, or scraping.
                      </p>
                    </div>

                    <div className="grid gap-3 lg:grid-cols-[180px_minmax(0,1fr)]">
                      <label className="block">
                        <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                          Source type
                        </span>
                        <select
                          value={documentSourceType}
                          onChange={(event) => setDocumentSourceType(event.target.value)}
                          className="mt-2 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-sky-500"
                        >
                          <option value="linkedin">LinkedIn PDF/text</option>
                          <option value="cv">Base CV</option>
                          <option value="manual">Manual profile note</option>
                          <option value="portfolio">Portfolio/GitHub note</option>
                        </select>
                      </label>

                      <label className="block">
                        <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                          Document
                        </span>
                        <input
                          type="file"
                          accept=".pdf,.docx,.txt,.md,.tex"
                          onChange={(event) =>
                            setSelectedDocument(event.target.files?.[0] ?? null)
                          }
                          className="mt-2 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 file:mr-3 file:rounded-sm file:border-0 file:bg-slate-900 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-white"
                        />
                      </label>
                    </div>

                    <div className="flex flex-wrap gap-3">
                      <button
                        type="button"
                        onClick={() => void handleUploadDocument()}
                        disabled={operationMutating['upload-document']}
                        className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {operationMutating['upload-document']
                          ? 'Uploading...'
                          : 'Upload document'}
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleExtractProfile()}
                        disabled={operationMutating['extract-profile']}
                        className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {operationMutating['extract-profile']
                          ? 'Extracting...'
                          : 'Build profile'}
                      </button>
                    </div>

                    <div className="rounded-md border border-sky-200 bg-sky-50 p-4">
                      <p className="text-sm font-medium text-sky-950">
                        AI profile extraction with LangGraph
                      </p>
                      <p className="mt-2 text-sm leading-6 text-sky-900">
                        This path uses your OpenAI project and the profile agent to read only
                        the stored CV document, extract supported facts, and rebuild the
                        structured profile with evidence. No unsupported experience should be
                        invented.
                      </p>

                      {IS_LOCAL_API ? (
                        <label className="mt-4 block">
                          <span className="text-xs font-semibold uppercase tracking-wide text-sky-800">
                            Local CV path
                          </span>
                          <input
                            type="text"
                            value={localDocumentPath}
                            onChange={(event) => setLocalDocumentPath(event.target.value)}
                            className="mt-2 w-full rounded-md border border-sky-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-sky-500"
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
                            className="rounded-md bg-sky-700 px-4 py-2 text-sm font-medium text-white transition hover:bg-sky-800 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {operationMutating['ai-profile-import-run']
                              ? 'Running AI profile agent...'
                              : 'Import local CV + run AI profile agent'}
                          </button>
                        ) : null}
                        <button
                          type="button"
                          onClick={() => void handleRunAiProfileAgentOnLatestCv()}
                          disabled={
                            operationMutating['ai-profile-latest-cv'] || !latestCvDocument
                          }
                          className="rounded-md border border-sky-300 bg-white px-4 py-2 text-sm font-medium text-sky-900 transition hover:bg-sky-100 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          {operationMutating['ai-profile-latest-cv']
                            ? 'Refreshing AI profile...'
                            : 'Run AI profile agent on latest CV'}
                        </button>
                      </div>

                      <p className="mt-3 text-xs text-sky-800">
                        Model policy: `gpt-5-mini` for profile extraction, because this is a
                        high-value step and still relatively cheap.
                      </p>
                    </div>

                    <ResourceBanner title="Documents" state={documents} />
                    <div className="space-y-3">
                      {documents.data.map((document) => (
                        <article
                          key={document.id}
                          className="rounded-md border border-slate-200 bg-white p-3"
                        >
                          <div className="flex items-center justify-between gap-3">
                            <p className="text-sm font-medium text-slate-900">
                              {document.original_filename}
                            </p>
                            <span className="rounded-sm bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700 ring-1 ring-slate-200">
                              {document.source_type}
                            </span>
                          </div>
                          <p className="mt-2 text-xs text-slate-500">
                            {document.extracted_text
                              ? `${document.extracted_text.length} extracted characters`
                              : 'Stored without extracted text yet'}
                          </p>
                        </article>
                      ))}
                      {documents.data.length === 0 ? (
                        <EmptyState
                          title="No documents uploaded"
                          body="Upload the LinkedIn PDF and your LaTeX CV/template before rebuilding the profile."
                        />
                      ) : null}
                    </div>
                  </div>
                </Panel>

                <Panel
                  title="Agent controls"
                  subtitle="Run the daily workflow manually while we are still local: discovery, Gmail sync, and notification summary."
                >
                  <div className="space-y-5">
                    <div className="grid gap-3 md:grid-cols-2">
                      <MetricCard
                        label="Gmail"
                        value={gmailStatusState.data?.authenticated ? 'Ready' : 'Needs auth'}
                        note={
                          gmailStatusState.data?.token_file_exists
                            ? 'OAuth token found locally'
                            : 'Run Gmail auth before syncing'
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
                            Gmail OAuth
                          </p>
                          <p className="mt-1 text-sm leading-6 text-slate-600">
                            Credentials file:{' '}
                            {gmailStatusState.data?.credentials_file_exists ? 'found' : 'missing'}.
                            Token: {gmailStatusState.data?.token_file_exists ? 'stored' : 'not stored'}.
                          </p>
                        </div>
                        {IS_LOCAL_API ? (
                          <button
                            type="button"
                            onClick={() => void handleRunGmailAuth()}
                            disabled={
                              operationMutating['gmail-auth'] ||
                              !gmailStatusState.data?.credentials_file_exists
                            }
                            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {operationMutating['gmail-auth']
                              ? 'Waiting for Google...'
                              : gmailStatusState.data?.authenticated
                                ? 'Refresh Gmail OAuth'
                                : 'Authenticate Gmail'}
                          </button>
                        ) : null}
                        <button
                          type="button"
                          onClick={() => void handleStartGmailWebOAuth()}
                          disabled={
                            operationMutating['gmail-web-oauth'] ||
                            !gmailStatusState.data?.credentials_file_exists
                          }
                          className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          {operationMutating['gmail-web-oauth']
                            ? 'Opening OAuth...'
                            : 'Open web OAuth URL'}
                        </button>
                      </div>
                      <p className="mt-3 text-xs text-slate-500">
                        This opens the Google OAuth web flow. CareerOps uses readonly and compose
                        scopes, and still never sends email automatically.
                      </p>
                    </div>

                    <div className="rounded-md border border-amber-200 bg-amber-50 p-4">
                      <p className="text-sm font-medium text-amber-950">
                        AI inbox triage
                      </p>
                      <p className="mt-2 text-sm leading-6 text-amber-900">
                        The email agent does not read your full inbox. It first filters for
                        career-related, unlinked emails. Gmail sync is incremental by default,
                        so new messages are normalized and classified as they arrive instead of
                        reprocessing the whole mailbox.
                      </p>
                      <div className="mt-4 grid gap-3 sm:grid-cols-[160px_minmax(0,1fr)]">
                        <label className="block">
                          <span className="text-xs font-semibold uppercase tracking-wide text-amber-800">
                            AI batch size
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
                              ? 'Triaging with AI...'
                              : 'Triage unlinked emails with AI'}
                          </button>
                        </div>
                      </div>
                      <p className="mt-3 text-xs text-amber-800">
                        Model policy: `gpt-5-nano` for inbox triage to keep costs tight.
                      </p>
                    </div>

                    <div className="rounded-md border border-sky-200 bg-sky-50 p-4">
                      <p className="text-sm font-medium text-sky-950">
                        Semantic matching with pgvector
                      </p>
                      <p className="mt-2 text-sm leading-6 text-sky-900">
                        Builds embeddings for your verified profile and recent jobs using the
                        low-cost embedding model. Job scoring can then cite semantic evidence
                        in addition to rule-based skill matches.
                      </p>
                      <button
                        type="button"
                        onClick={() => void handleRebuildEmbeddings()}
                        disabled={operationMutating['rebuild-embeddings']}
                        className="mt-4 rounded-md bg-sky-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {operationMutating['rebuild-embeddings']
                          ? 'Building embeddings...'
                          : 'Rebuild profile/job embeddings'}
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
                          ? 'Running discovery...'
                          : 'Run Job Discovery Agent'}
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
                        {operationMutating['sync-gmail'] ? 'Syncing...' : 'Sync Gmail'}
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
                          ? 'Syncing LinkedIn...'
                          : 'Sync LinkedIn via Gmail'}
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleReclassifyEmails()}
                        disabled={operationMutating['reclassify-emails']}
                        className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {operationMutating['reclassify-emails']
                          ? 'Reclassifying...'
                          : 'Reclassify inbox'}
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleGenerateDailySummary()}
                        disabled={operationMutating['daily-summary']}
                        className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {operationMutating['daily-summary']
                          ? 'Generating...'
                          : 'Generate daily summary'}
                      </button>
                      <button
                        type="button"
                        onClick={() => void refreshCoreData()}
                        className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 transition hover:bg-slate-50"
                      >
                        Refresh dashboard
                      </button>
                    </div>

                    <div className="rounded-md border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950">
                      Login for the CareerOps web app is not enabled yet because this is still
                      a local single-user build. Gmail OAuth is already configured; app-level
                      login should be added before cloud deploy.
                    </div>
                  </div>
                </Panel>
              </div>
            ) : null}

            {activeSection === 'jobs' ? (
              <div className="grid gap-6 xl:grid-cols-[minmax(360px,0.95fr)_minmax(0,1.25fr)]">
                <Panel
                  title="Job inventory"
                  subtitle="Discovered and manually added roles across all configured sources."
                >
                  <div className="mb-4">
                    <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500">
                      Search jobs
                    </label>
                    <input
                      type="text"
                      value={jobSearch}
                      onChange={(event) => setJobSearch(event.target.value)}
                      placeholder="Title, company, source, location"
                      className="mt-2 w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-sky-500"
                    />
                  </div>
                  <ResourceBanner title="Jobs" state={jobs} />
                  <div className="space-y-3">
                    {filteredJobs.slice(0, 40).map((job) => {
                      const selected = job.id === effectiveSelectedJobId
                      return (
                        <button
                          key={job.id}
                          type="button"
                          onClick={() => setSelectedJobId(job.id)}
                          className={`w-full rounded-md border p-4 text-left transition ${
                            selected
                              ? 'border-slate-900 bg-slate-900 text-white'
                              : 'border-slate-200 bg-slate-50 text-slate-900 hover:bg-slate-100'
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
                            </div>
                            <span
                              className={`rounded-sm px-2 py-1 text-xs ${
                                selected
                                  ? 'bg-white/15 text-white'
                                  : 'bg-slate-200 text-slate-700'
                              }`}
                            >
                              {formatSourceLabel(job.source)}
                            </span>
                          </div>
                          <p
                            className={`mt-3 text-sm leading-6 ${
                              selected ? 'text-slate-200' : 'text-slate-600'
                            }`}
                          >
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
                        ? `${selectedJob.company?.name ?? 'Unknown company'} - ${selectedJob.location ?? 'Location not parsed'}`
                        : 'Pick a job from the list to inspect score evidence and generated artifacts.'
                    }
                  >
                    {selectedJob ? (
                      <div className="space-y-5">
                        <div className="flex flex-wrap gap-2">
                          <span className="rounded-sm bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700 ring-1 ring-slate-200">
                            {formatSourceLabel(selectedJob.source)}
                          </span>
                          <span className="rounded-sm bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700 ring-1 ring-slate-200">
                            {selectedJob.work_mode ?? 'Work mode not parsed'}
                          </span>
                          <span className="rounded-sm bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700 ring-1 ring-slate-200">
                            {selectedJob.seniority ?? 'Seniority not parsed'}
                          </span>
                        </div>

                        <div className="rounded-md border border-slate-200 bg-slate-50 p-4">
                          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                            <div>
                              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                                Source trace
                              </p>
                              <p className="mt-1 text-sm text-slate-700">
                                Imported from {formatSourceLabel(selectedJob.source)}
                                {selectedJob.source_trace?.email_subject
                                  ? ` via email "${String(selectedJob.source_trace.email_subject)}"`
                                  : selectedJob.source_trace?.subject
                                    ? ` via email "${String(selectedJob.source_trace.subject)}"`
                                  : ''}
                              </p>
                              {selectedJob.source_trace?.gmail_message_id ? (
                                <p className="mt-1 text-xs text-slate-500">
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
                                  className="rounded-md bg-white px-3 py-2 text-xs font-medium text-slate-800 ring-1 ring-slate-300 transition hover:bg-slate-100"
                                >
                                  Open original job
                                </a>
                              ) : null}
                              {selectedJob.source_trace?.gmail_thread_id ? (
                                <a
                                  href={`https://mail.google.com/mail/u/0/#inbox/${String(selectedJob.source_trace.gmail_thread_id)}`}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="rounded-md bg-white px-3 py-2 text-xs font-medium text-slate-800 ring-1 ring-slate-300 transition hover:bg-slate-100"
                                >
                                  Open source email
                                </a>
                              ) : null}
                            </div>
                          </div>
                          <details className="mt-3">
                            <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-slate-500">
                              Raw source metadata
                            </summary>
                            <pre className="mt-2 max-h-64 overflow-auto rounded-md bg-white p-3 text-xs leading-5 text-slate-700 ring-1 ring-slate-200">
                              {payloadText(selectedJob.source_trace ?? selectedJob.raw_payload)}
                            </pre>
                          </details>
                        </div>

                        <div className="flex flex-wrap gap-3 rounded-md border border-slate-200 bg-slate-50 p-3">
                          <button
                            type="button"
                            onClick={() => void handleScoreSelectedJob()}
                            disabled={operationMutating['score-job']}
                            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {operationMutating['score-job'] ? 'Scoring...' : 'Score match'}
                          </button>
                          <button
                            type="button"
                            onClick={() => void handleCreateCvPlan()}
                            disabled={operationMutating['cv-plan']}
                            className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {operationMutating['cv-plan'] ? 'Planning...' : 'Create CV plan'}
                          </button>
                          <button
                            type="button"
                            onClick={() => void handleGenerateFinalCv()}
                            disabled={operationMutating['final-cv']}
                            className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {operationMutating['final-cv']
                              ? 'Generating...'
                              : 'Generate LaTeX CV'}
                          </button>
                          <button
                            type="button"
                            onClick={() => void handleGenerateMessageDrafts()}
                            disabled={operationMutating['message-drafts']}
                            className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {operationMutating['message-drafts']
                              ? 'Drafting...'
                              : 'Generate messages'}
                          </button>
                          <button
                            type="button"
                            onClick={() => void handleCreateSelectedJobEmbedding()}
                            disabled={operationMutating['job-embedding']}
                            className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {operationMutating['job-embedding']
                              ? 'Embedding...'
                              : 'Refresh semantic match'}
                          </button>
                        </div>

                        <p className="text-sm leading-7 text-slate-700">
                          {cleanDisplayText(selectedJob.description)}
                        </p>

                        <div className="rounded-md border border-slate-200 bg-white p-4">
                          <ResourceBanner
                            title="Semantic evidence"
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
                                    Fit recommendation
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
                        body="Pick a role from the left column to inspect its score, CV plan, and message drafts."
                      />
                    )}
                  </Panel>

                  <div className="grid gap-6 xl:grid-cols-2">
                    <Panel
                      title="CV artifacts"
                      subtitle={`${selectedJobCvVersions.data.length} tailoring records for the selected job`}
                    >
                      <ResourceBanner title="CV tailoring plans" state={selectedJobCvVersions} />
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
                          title="No CV versions for this job"
                          body="Once a tailoring plan exists, the selected bullets, focus areas, and generated file path will appear here."
                        />
                      )}
                    </Panel>

                    <Panel
                      title="Message drafts"
                      subtitle={`${approvedDraftCount} approved drafts and ${approvedCvCount} approved CV versions for this role`}
                    >
                      <ResourceBanner title="Message drafts" state={selectedJobDrafts} />
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
                              <p className="mt-3 whitespace-pre-line text-sm leading-6 text-slate-700">
                                {truncate(draft.body, 360)}
                              </p>
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
                          body="Drafts appear here after message generation or recruiter reply preparation."
                        />
                      )}
                    </Panel>
                  </div>
                </div>
              </div>
            ) : null}

            {activeSection === 'applications' ? (
              <div className="grid gap-6 xl:grid-cols-[minmax(360px,0.9fr)_minmax(0,1.3fr)]">
                <Panel
                  title="Application tracker"
                  subtitle="Human-reviewed pipeline across found roles, ready-to-apply items, and post-submit follow-up."
                >
                  <ResourceBanner title="Applications" state={applications} />
                  <div className="space-y-3">
                    {applications.data.map((application) => {
                      const job = jobsById.get(application.job_id)
                      const selected = application.id === effectiveSelectedApplicationId
                      return (
                        <button
                          key={application.id}
                          type="button"
                          onClick={() => setSelectedApplicationId(application.id)}
                          className={`w-full rounded-md border p-4 text-left transition ${
                            selected
                              ? 'border-slate-900 bg-slate-900 text-white'
                              : 'border-slate-200 bg-slate-50 text-slate-900 hover:bg-slate-100'
                          }`}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <p className="text-sm font-medium">
                                {job?.company?.name ?? 'Unknown company'}
                              </p>
                              <p
                                className={`mt-1 text-sm ${
                                  selected ? 'text-slate-300' : 'text-slate-600'
                                }`}
                              >
                                {job?.title ?? 'Unknown role'}
                              </p>
                            </div>
                            <span
                              className={`rounded-sm px-2 py-1 text-xs ${
                                selected
                                  ? 'bg-white/15 text-white'
                                  : 'bg-slate-200 text-slate-700'
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
                        </button>
                      )
                    })}
                  </div>
                </Panel>

                <div className="space-y-6">
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
                      <div className="space-y-5">
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

                        <div className="rounded-md border border-slate-200 bg-slate-50 p-4">
                          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                            Current action
                          </p>
                          <p className="mt-2 text-sm font-medium text-slate-900">
                            {selectedApplicationTracker.data.current_action}
                          </p>
                          {selectedApplicationTracker.data.next_steps.length ? (
                            <ul className="mt-3 space-y-2 text-sm text-slate-700">
                              {selectedApplicationTracker.data.next_steps.map((step) => (
                                <li key={step}>- {step}</li>
                              ))}
                            </ul>
                          ) : (
                            <p className="mt-3 text-sm text-slate-600">
                              No additional next steps currently suggested.
                            </p>
                          )}
                        </div>

                        <div className="flex flex-wrap gap-3">
                          <button
                            type="button"
                            onClick={() => void handleSyncNextActions()}
                            disabled={applicationMutating}
                            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {applicationMutating ? 'Working...' : 'Sync next actions'}
                          </button>
                          {!selectedApplicationTracker.data.applied_at ? (
                            <button
                              type="button"
                              onClick={() => void handleMarkApplied()}
                              disabled={applicationMutating}
                              className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-900 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
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
                    {selectedApplicationActions.data.length ? (
                      <div className="space-y-4">
                        {selectedApplicationActions.data.map((action) => (
                          <article
                            key={action.id}
                            className="rounded-md border border-slate-200 bg-slate-50 p-4"
                          >
                            <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                              <div>
                                <p className="text-sm font-medium text-slate-900">{action.title}</p>
                                <p className="mt-1 text-sm text-slate-600">
                                  {action.action_type}
                                </p>
                              </div>
                              <div className="flex flex-wrap gap-2">
                                <span
                                  className={`inline-flex rounded-sm px-2 py-1 text-xs font-medium ${getPriorityTone(action.priority)}`}
                                >
                                  {action.priority}
                                </span>
                                <span
                                  className={`inline-flex rounded-sm px-2 py-1 text-xs font-medium ${getStatusTone(action.status)}`}
                                >
                                  {action.status}
                                </span>
                              </div>
                            </div>

                            <p className="mt-3 text-sm leading-6 text-slate-700">
                              {truncate(action.details, 220)}
                            </p>
                            <p className="mt-3 text-xs text-slate-500">
                              Due {formatDate(action.due_at)} - Updated {formatRelativeDate(action.updated_at)}
                            </p>

                            {action.status === 'open' ? (
                              <div className="mt-4 flex flex-wrap gap-3">
                                <button
                                  type="button"
                                  onClick={() => void handleUpdateAction(action.id, 'completed')}
                                  disabled={actionMutating[action.id]}
                                  className="rounded-md bg-emerald-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
                                >
                                  {actionMutating[action.id] ? 'Saving...' : 'Mark complete'}
                                </button>
                                <button
                                  type="button"
                                  onClick={() => void handleUpdateAction(action.id, 'dismissed')}
                                  disabled={actionMutating[action.id]}
                                  className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-900 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
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
                        title="No actions attached"
                        body="Sync next actions from the tracker to create follow-ups, interview tasks, or submission steps."
                      />
                    )}
                  </Panel>
                </div>
              </div>
            ) : null}

            {activeSection === 'inbox' ? (
              <Panel
                title="Recruiter inbox"
                subtitle="Synced Gmail signals, sorted by urgency and whether they need a human response."
              >
                <ResourceBanner title="Emails" state={emails} />
                <div className="space-y-3">
                  {emails.data.map((email) => (
                    <article
                      key={email.id}
                      className="rounded-md border border-slate-200 bg-slate-50 p-4"
                    >
                      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                        <div className="min-w-0">
                          <p className="text-sm font-medium text-slate-900">
                            {email.company_name ?? email.from_name ?? email.from_email}
                          </p>
                          <p className="mt-1 text-sm text-slate-600">
                            {email.subject ?? '(No subject)'}
                          </p>
                          <p className="mt-2 text-sm leading-6 text-slate-700">
                            {truncate(cleanDisplayText(email.snippet ?? email.body_text ?? ''), 260)}
                          </p>
                        </div>
                        <div className="flex shrink-0 flex-wrap gap-2 lg:max-w-[280px] lg:justify-end">
                          <span
                            className={`inline-flex rounded-sm px-2 py-1 text-xs font-medium ${getPriorityTone(email.urgency)}`}
                          >
                            {email.urgency}
                          </span>
                          <span className="inline-flex rounded-sm bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700 ring-1 ring-slate-200">
                            {email.category}
                          </span>
                          {email.requires_reply ? (
                            <span className="inline-flex rounded-sm bg-sky-100 px-2 py-1 text-xs font-medium text-sky-800 ring-1 ring-sky-200">
                              Reply needed
                            </span>
                          ) : null}
                          {email.gmail_draft_id ? (
                            <span className="inline-flex rounded-sm bg-emerald-100 px-2 py-1 text-xs font-medium text-emerald-800 ring-1 ring-emerald-200">
                              Gmail draft ready
                            </span>
                          ) : null}
                        </div>
                      </div>
                      <div className="mt-3 flex flex-col gap-1 text-sm text-slate-500 lg:flex-row lg:items-center lg:justify-between">
                        <span>{email.from_email}</span>
                        <span>{formatDate(email.received_at ?? email.created_at)}</span>
                      </div>
                      <div className="mt-3 rounded-md border border-slate-200 bg-white p-3">
                        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                          <div>
                            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                              Email source trace
                            </p>
                            <p className="mt-1 text-sm text-slate-700">
                              Gmail message {email.gmail_message_id ?? 'not available'} from{' '}
                              {email.gmail_label_ids?.length
                                ? email.gmail_label_ids.join(', ')
                                : 'stored inbox sync'}
                            </p>
                            {email.gmail_history_id ? (
                              <p className="mt-1 text-xs text-slate-500">
                                Gmail history: {email.gmail_history_id}
                              </p>
                            ) : null}
                          </div>
                          <div className="flex shrink-0 flex-wrap gap-2">
                            {gmailThreadUrl(email) ? (
                              <a
                                href={gmailThreadUrl(email) ?? undefined}
                                target="_blank"
                                rel="noreferrer"
                                className="rounded-md bg-slate-900 px-3 py-2 text-xs font-medium text-white transition hover:bg-slate-700"
                              >
                                Open in Gmail
                              </a>
                            ) : null}
                          </div>
                        </div>
                      </div>
                      <div className="mt-4 rounded-md border border-slate-200 bg-white p-3">
                        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                          <div>
                            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                              Application link
                            </p>
                            <p className="mt-1 text-sm text-slate-700">
                              {email.application_id
                                ? `Linked to ${
                                    jobsById.get(
                                      applications.data.find(
                                        (application) => application.id === email.application_id,
                                      )?.job_id ?? '',
                                    )?.company?.name ?? 'application'
                                  }`
                                : 'This email is not linked to an application yet.'}
                            </p>
                          </div>
                          <div className="flex min-w-0 flex-col gap-2 lg:w-[380px]">
                            <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                              Select application
                            </label>
                            <select
                              value={email.application_id ?? ''}
                              onChange={(event) =>
                                void handleLinkEmail(email.id, event.target.value)
                              }
                              disabled={emailMutating[email.id]}
                              className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-sky-500 disabled:cursor-not-allowed disabled:opacity-60"
                            >
                              <option value="">Unlinked</option>
                              {getEmailApplicationOptions(email).map((application) => {
                                const job = jobsById.get(application.job_id)
                                return (
                                  <option key={application.id} value={application.id}>
                                    {job?.company?.name ?? 'Unknown company'} -{' '}
                                    {job?.title ?? 'Unknown role'} - {application.status}
                                  </option>
                                )
                              })}
                            </select>
                            {emailMutating[email.id] ? (
                              <p className="text-xs text-slate-500">
                                Updating link and refreshing tracker...
                              </p>
                            ) : null}
                          </div>
                        </div>
                      </div>
                      {email.suggested_action ? (
                        <p className="mt-3 text-sm text-slate-700">
                          Suggested action: {email.suggested_action}
                        </p>
                      ) : null}
                    </article>
                  ))}
                </div>
              </Panel>
            ) : null}

            {activeSection === 'profile' ? (
              <Panel
                title="Candidate knowledge base"
                subtitle="Structured profile extracted from your CV and supporting documents."
              >
                <ResourceBanner title="Profile" state={profile} />

                {profile.data ? (
                  <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                    <section className="space-y-5">
                      <div className="rounded-md border border-slate-200 bg-slate-50 p-4">
                        <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
                          Identity and preferences
                        </h3>
                        <div className="mt-3 space-y-2 text-sm text-slate-700">
                          <p>
                            <span className="font-medium text-slate-900">Name:</span>{' '}
                            {cleanDisplayName(profile.data.display_name)}
                          </p>
                          <p>
                            <span className="font-medium text-slate-900">Headline:</span>{' '}
                            {profile.data.headline
                              ? cleanDisplayText(profile.data.headline)
                              : 'Not set yet'}
                          </p>
                          <p>
                            <span className="font-medium text-slate-900">Location:</span>{' '}
                            {profile.data.location
                              ? cleanDisplayText(profile.data.location)
                              : 'Not set yet'}
                          </p>
                          <p>
                            <span className="font-medium text-slate-900">
                              Communication style:
                            </span>{' '}
                            {getProfilePreference(
                              profile.data.preferences,
                              'communication_style',
                            ) ?? 'Not extracted yet'}
                          </p>
                          <p>
                            <span className="font-medium text-slate-900">
                              Work preferences:
                            </span>{' '}
                            {getProfilePreference(
                              profile.data.preferences,
                              'work_preferences',
                            ) ?? 'Not extracted yet'}
                          </p>
                        </div>
                      </div>

                      <div className="rounded-md border border-slate-200 bg-slate-50 p-4">
                        <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
                          Summary
                        </h3>
                        <p className="mt-3 text-sm leading-6 text-slate-700">
                          {profile.data.summary
                            ? cleanDisplayText(profile.data.summary)
                            : 'No summary extracted yet.'}
                        </p>
                      </div>

                      <div className="rounded-md border border-slate-200 bg-slate-50 p-4">
                        <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
                          Experience
                        </h3>
                        <div className="mt-4 space-y-4">
                          {profile.data.experiences.map((experience) => (
                            <article key={experience.id}>
                              <p className="text-sm font-medium text-slate-900">
                                {experience.title}
                              </p>
                              <p className="mt-1 text-sm text-slate-600">
                                {experience.company} - {experience.location ?? 'Location not set'}
                              </p>
                              <p className="mt-1 text-sm text-slate-500">
                                {experience.start_date} - {experience.end_date}
                              </p>
                              <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-700">
                                {experience.bullets?.map((bullet) => (
                                  <li key={bullet}>- {bullet}</li>
                                ))}
                              </ul>
                            </article>
                          ))}
                        </div>
                      </div>
                    </section>

                    <section className="space-y-5">
                      <div className="rounded-md border border-slate-200 bg-slate-50 p-4">
                        <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
                          Skills
                        </h3>
                        <div className="mt-4 flex flex-wrap gap-2">
                          {profile.data.skills.map((skill) => (
                            <span
                              key={skill.id}
                              className="rounded-sm bg-white px-2 py-1 text-xs font-medium text-slate-700 ring-1 ring-slate-200"
                            >
                              {skill.name}
                            </span>
                          ))}
                        </div>
                      </div>

                      <div className="rounded-md border border-slate-200 bg-slate-50 p-4">
                        <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
                          Projects
                        </h3>
                        <div className="mt-4 space-y-4">
                          {profile.data.projects.map((project) => (
                            <article key={project.id}>
                              <p className="text-sm font-medium text-slate-900">
                                {project.name}
                              </p>
                              <p className="mt-1 text-sm text-slate-600">
                                {project.description}
                              </p>
                              <div className="mt-2 flex flex-wrap gap-2">
                                {project.technologies?.map((technology) => (
                                  <span
                                    key={technology}
                                    className="rounded-sm bg-white px-2 py-1 text-xs font-medium text-slate-700 ring-1 ring-slate-200"
                                  >
                                    {technology}
                                  </span>
                                ))}
                              </div>
                              <p className="mt-3 text-sm leading-6 text-slate-700">
                                {project.impact}
                              </p>
                            </article>
                          ))}
                        </div>
                      </div>
                    </section>
                  </div>
                ) : null}
              </Panel>
            ) : null}
          </main>
        </div>
      </div>
    </div>
  )
}

export default App
