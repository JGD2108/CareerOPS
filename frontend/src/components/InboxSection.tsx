import type { ComponentType, ReactNode } from 'react'

import { cleanDisplayText, truncate } from '../lib/text'
import type { Application, Email, Job, ResourceState } from '../types/dashboard'

type BannerComponent = ComponentType<{ title: string; state: ResourceState<unknown> }>
type PanelComponent = ComponentType<{ title: string; subtitle?: string; children: ReactNode }>

type Props = {
  emails: ResourceState<Email[]>
  inboxEmails: Email[]
  applications: ResourceState<Application[]>
  jobsById: Map<string, Job>
  emailMutating: Record<string, boolean>
  formatDate: (value: string | null) => string
  getPriorityTone: (priority: string) => string
  gmailThreadUrl: (email: Email) => string | null
  isNoReplySender: (fromEmail: string | null | undefined) => boolean
  handleLinkEmail: (emailId: string, applicationId: string) => Promise<void>
  handleCreateGmailReplyDraft: (emailId: string) => Promise<void>
  getEmailApplicationOptions: (email: Email) => Application[]
  Panel: PanelComponent
  ResourceBanner: BannerComponent
  TriageAuditPanel: ComponentType
}

export function InboxSection(props: Props) {
  const {
    emails,
    inboxEmails,
    applications,
    jobsById,
    emailMutating,
    formatDate,
    getPriorityTone,
    gmailThreadUrl,
    isNoReplySender,
    handleLinkEmail,
    handleCreateGmailReplyDraft,
    getEmailApplicationOptions,
    Panel,
    ResourceBanner,
    TriageAuditPanel,
  } = props

  return (
    <Panel
      title="Inbox triage"
      subtitle="Only application, recruiter, interview, assessment, offer, and other work-related Gmail signals are surfaced here."
    >
      <div className="mb-4 rounded-lg border border-[color:var(--app-border)] bg-[color:var(--app-bg-soft)] p-3">
        <h3 className="crm-label">
          Recent triage audit
        </h3>
        <TriageAuditPanel />
      </div>
      <ResourceBanner title="Emails" state={emails} />
      <div className="space-y-3">
        {inboxEmails.map((email) => {
          const replyBlocked = isNoReplySender(email.from_email)
          return (
          <article
            key={email.id}
            className="crm-card p-4"
          >
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div className="min-w-0">
                <p className="text-sm font-medium text-[color:var(--app-ink)]">
                  {email.company_name ?? email.from_name ?? email.from_email}
                </p>
                <p className="mt-1 text-sm text-[color:var(--app-muted)]">{email.subject ?? '(No subject)'}</p>
                <p className="mt-3 text-sm leading-6 text-[color:var(--app-muted)]">
                  {truncate(cleanDisplayText(email.snippet ?? email.body_text ?? ''), 260)}
                </p>
              </div>
              <div className="flex shrink-0 flex-wrap gap-2 lg:max-w-[280px] lg:justify-end">
                <span
                  className={`inline-flex rounded-md px-2 py-1 text-xs font-medium ${getPriorityTone(email.urgency)}`}
                >
                  {email.urgency}
                </span>
                <span className="inline-flex rounded-md bg-[color:var(--app-bg-soft)] px-2 py-1 text-xs font-medium text-[color:var(--app-muted)] ring-1 ring-[color:var(--app-border)]">
                  {email.category}
                </span>
                {email.requires_reply ? (
                  <span className="inline-flex rounded-md bg-sky-100 px-2 py-1 text-xs font-medium text-sky-800 ring-1 ring-sky-200">
                    Reply needed
                  </span>
                ) : null}
                {email.gmail_draft_id ? (
                  <span className="inline-flex rounded-md bg-emerald-100 px-2 py-1 text-xs font-medium text-emerald-800 ring-1 ring-emerald-200">
                    Gmail draft ready
                  </span>
                ) : null}
              </div>
            </div>
            <div className="mt-3 flex flex-col gap-1 text-sm text-[color:var(--app-muted)]/80 lg:flex-row lg:items-center lg:justify-between">
              <span>{email.from_email}</span>
              <span>{formatDate(email.received_at ?? email.created_at)}</span>
            </div>
            <div className="mt-4 rounded-lg border border-[color:var(--app-border)] bg-[color:var(--app-bg-soft)] p-3">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <p className="crm-label">
                    Email source trace
                  </p>
                  <p className="mt-2 text-sm text-[color:var(--app-muted)]">
                    Gmail message {email.gmail_message_id ?? 'not available'} from{' '}
                    {email.gmail_label_ids?.length ? email.gmail_label_ids.join(', ') : 'stored inbox sync'}
                  </p>
                  {email.gmail_history_id ? (
                    <p className="mt-1 text-xs text-[color:var(--app-muted)]/80">Gmail history: {email.gmail_history_id}</p>
                  ) : null}
                </div>
                <div className="flex shrink-0 flex-wrap gap-2">
                  {gmailThreadUrl(email) ? (
                    <a
                      href={gmailThreadUrl(email) ?? undefined}
                      target="_blank"
                      rel="noreferrer"
                      className="crm-button bg-[color:var(--app-ink)] text-xs text-white hover:opacity-92"
                    >
                      Open in Gmail
                    </a>
                  ) : null}
                  <button
                    type="button"
                    onClick={() => void handleCreateGmailReplyDraft(email.id)}
                    disabled={emailMutating[email.id] || !email.application_id || replyBlocked}
                    className="crm-button border border-[color:var(--app-border-strong)] bg-white text-xs text-[color:var(--app-ink)] hover:bg-[color:var(--app-bg-soft)] disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {emailMutating[email.id] ? 'Creating draft...' : 'Reply in Gmail'}
                  </button>
                </div>
              </div>
            </div>
            <div className="mt-4 rounded-lg border border-[color:var(--app-border)] bg-white p-3">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <p className="crm-label">
                    Application link
                  </p>
                  <p className="mt-2 text-sm text-[color:var(--app-muted)]">
                    {email.application_id
                      ? `Linked to ${
                          jobsById.get(
                            applications.data.find((application) => application.id === email.application_id)?.job_id ?? '',
                          )?.company?.name ?? 'application'
                        }`
                      : 'This email is not linked to an application yet.'}
                  </p>
                </div>
                <div className="flex min-w-0 flex-col gap-2 lg:w-[380px]">
                  <label className="crm-label">
                    Select application
                  </label>
                  <select
                    value={email.application_id ?? ''}
                    onChange={(event) => void handleLinkEmail(email.id, event.target.value)}
                    disabled={emailMutating[email.id]}
                    className="crm-select px-3 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    <option value="">Unlinked</option>
                    {getEmailApplicationOptions(email).map((application) => {
                      const job = jobsById.get(application.job_id)
                      return (
                        <option key={application.id} value={application.id}>
                          {job?.company?.name ?? 'Unknown company'} - {job?.title ?? 'Unknown role'} - {application.status}
                        </option>
                      )
                    })}
                  </select>
                  {emailMutating[email.id] ? (
                    <p className="text-xs text-[color:var(--app-muted)]">Updating link and refreshing tracker...</p>
                  ) : null}
                  {replyBlocked ? (
                    <p className="text-xs text-rose-700">Reply blocked: this sender is no-reply.</p>
                  ) : null}
                </div>
              </div>
            </div>
            {email.suggested_action ? (
              <p className="mt-3 text-sm text-[color:var(--app-muted)]">
                Suggested action: {email.suggested_action}
              </p>
            ) : null}
          </article>
          )
        })}
      </div>
    </Panel>
  )
}
