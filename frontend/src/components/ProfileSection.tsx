import type { ComponentType, ReactNode } from 'react'

import { cleanDisplayName, cleanDisplayText, getProfilePreference } from '../lib/text'
import type { CandidateProfile, ResourceState } from '../types/dashboard'

type BannerComponent = ComponentType<{ title: string; state: ResourceState<unknown> }>
type PanelComponent = ComponentType<{ title: string; subtitle?: string; children: ReactNode }>

type ProfileProjectForm = {
  name: string
  description: string
  technologies: string
  impact: string
  project_url: string
  repo_url: string
  metric_bullets: string
}

type Props = {
  profile: ResourceState<CandidateProfile | null>
  Panel: PanelComponent
  ResourceBanner: BannerComponent
  projectForm: ProfileProjectForm
  projectMutating: boolean
  deletingProjectIds: Record<string, boolean>
  onProjectFormChange: (next: ProfileProjectForm) => void
  onAddProject: () => void
  onDeleteProject: (projectId: string, projectName: string) => void
}

export function ProfileSection({
  profile,
  Panel,
  ResourceBanner,
  projectForm,
  projectMutating,
  deletingProjectIds,
  onProjectFormChange,
  onAddProject,
  onDeleteProject,
}: Props) {
  const updateProjectForm = (field: keyof ProfileProjectForm, value: string) => {
    onProjectFormChange({ ...projectForm, [field]: value })
  }

  return (
    <Panel
      title="Profile evidence"
      subtitle="Structured profile extracted from your CV and supporting documents, kept visible as the source of truth for every downstream artifact."
    >
      <ResourceBanner title="Profile" state={profile} />

      {profile.data ? (
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <section className="space-y-4">
            <div className="crm-card p-4">
              <h3 className="crm-label">
                Identity and preferences
              </h3>
              <div className="mt-4 space-y-2 text-sm leading-6 text-[color:var(--app-muted)]">
                <p>
                  <span className="font-medium text-[color:var(--app-ink)]">Name:</span>{' '}
                  {cleanDisplayName(profile.data.display_name)}
                </p>
                <p>
                  <span className="font-medium text-[color:var(--app-ink)]">Headline:</span>{' '}
                  {profile.data.headline ? cleanDisplayText(profile.data.headline) : 'Not set yet'}
                </p>
                <p>
                  <span className="font-medium text-[color:var(--app-ink)]">Location:</span>{' '}
                  {profile.data.location ? cleanDisplayText(profile.data.location) : 'Not set yet'}
                </p>
                <p>
                  <span className="font-medium text-[color:var(--app-ink)]">Communication style:</span>{' '}
                  {getProfilePreference(profile.data.preferences, 'communication_style') ??
                    'Not extracted yet'}
                </p>
                <p>
                  <span className="font-medium text-[color:var(--app-ink)]">Work preferences:</span>{' '}
                  {getProfilePreference(profile.data.preferences, 'work_preferences') ??
                    'Not extracted yet'}
                </p>
              </div>
            </div>

            <div className="crm-subcard p-4">
              <h3 className="crm-label">
                Summary
              </h3>
              <p className="mt-4 text-sm leading-7 text-[color:var(--app-muted)]">
                {profile.data.summary
                  ? cleanDisplayText(profile.data.summary)
                  : 'No summary extracted yet.'}
              </p>
            </div>

            <div className="crm-card p-4">
              <h3 className="crm-label">
                Experience
              </h3>
              <div className="mt-4 space-y-4">
                {profile.data.experiences.map((experience) => (
                  <article key={experience.id} className="crm-subcard p-3">
                    <p className="text-sm font-medium text-[color:var(--app-ink)]">{experience.title}</p>
                    <p className="mt-1 text-sm text-[color:var(--app-muted)]">
                      {experience.company} - {experience.location ?? 'Location not set'}
                    </p>
                    <p className="mt-1 text-sm text-[color:var(--app-muted)]/80">
                      {experience.start_date} - {experience.end_date}
                    </p>
                    <ul className="mt-3 space-y-2 text-sm leading-6 text-[color:var(--app-muted)]">
                      {experience.bullets?.map((bullet) => (
                        <li key={bullet}>- {bullet}</li>
                      ))}
                    </ul>
                  </article>
                ))}
              </div>
            </div>
          </section>

          <section className="space-y-4">
            <div className="crm-card p-4">
              <h3 className="crm-label">
                Skills
              </h3>
              <div className="mt-4 flex flex-wrap gap-2">
                {profile.data.skills.map((skill) => (
                  <span
                    key={skill.id}
                    className="rounded-md bg-[color:var(--app-accent-soft)] px-2 py-1 text-xs font-medium text-[color:var(--app-accent)] ring-1 ring-[color:var(--app-accent)]/10"
                  >
                    {skill.name}
                  </span>
                ))}
              </div>
            </div>

            <div className="crm-subcard p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <h3 className="crm-label">
                  Projects
                </h3>
                <button
                  type="button"
                  onClick={onAddProject}
                  disabled={projectMutating}
                  className="rounded-md bg-[color:var(--app-ink)] px-3 py-1.5 text-xs font-medium text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {projectMutating ? 'Adding...' : 'Add project'}
                </button>
              </div>

              <div className="mt-4 grid gap-3 rounded-md border border-[color:var(--app-border)] bg-white p-3">
                <div className="grid gap-3 md:grid-cols-2">
                  <label className="block">
                    <span className="crm-label">Name</span>
                    <input
                      type="text"
                      value={projectForm.name}
                      onChange={(event) => updateProjectForm('name', event.target.value)}
                      className="crm-input mt-1 w-full px-3 py-2 text-sm"
                      placeholder="Project name"
                    />
                  </label>
                  <label className="block">
                    <span className="crm-label">Technologies</span>
                    <input
                      type="text"
                      value={projectForm.technologies}
                      onChange={(event) => updateProjectForm('technologies', event.target.value)}
                      className="crm-input mt-1 w-full px-3 py-2 text-sm"
                      placeholder="Python, React, Docker"
                    />
                  </label>
                </div>
                <label className="block">
                  <span className="crm-label">Description</span>
                  <textarea
                    value={projectForm.description}
                    onChange={(event) => updateProjectForm('description', event.target.value)}
                    rows={2}
                    className="crm-textarea mt-1 w-full px-3 py-2 text-sm"
                    placeholder="What the project does"
                  />
                </label>
                <label className="block">
                  <span className="crm-label">Impact</span>
                  <textarea
                    value={projectForm.impact}
                    onChange={(event) => updateProjectForm('impact', event.target.value)}
                    rows={2}
                    className="crm-textarea mt-1 w-full px-3 py-2 text-sm"
                    placeholder="Evidence-backed result or responsibility"
                  />
                </label>
                <div className="grid gap-3 md:grid-cols-2">
                  <label className="block">
                    <span className="crm-label">Project URL</span>
                    <input
                      type="url"
                      value={projectForm.project_url}
                      onChange={(event) => updateProjectForm('project_url', event.target.value)}
                      className="crm-input mt-1 w-full px-3 py-2 text-sm"
                      placeholder="https://..."
                    />
                  </label>
                  <label className="block">
                    <span className="crm-label">Repo URL</span>
                    <input
                      type="url"
                      value={projectForm.repo_url}
                      onChange={(event) => updateProjectForm('repo_url', event.target.value)}
                      className="crm-input mt-1 w-full px-3 py-2 text-sm"
                      placeholder="https://github.com/..."
                    />
                  </label>
                </div>
                <label className="block">
                  <span className="crm-label">Metric bullets</span>
                  <textarea
                    value={projectForm.metric_bullets}
                    onChange={(event) => updateProjectForm('metric_bullets', event.target.value)}
                    rows={2}
                    className="crm-textarea mt-1 w-full px-3 py-2 text-sm"
                    placeholder="One explicit metric per line"
                  />
                </label>
              </div>

              <div className="mt-4 space-y-4">
                {profile.data.projects.length === 0 ? (
                  <p className="text-sm text-[color:var(--app-muted)]">No projects extracted yet.</p>
                ) : null}
                {profile.data.projects.map((project) => (
                  <article key={project.id} className="crm-card p-3">
                    <div className="flex items-center justify-between gap-2">
                      <p className="min-w-0 break-words text-sm font-medium text-[color:var(--app-ink)]">{project.name}</p>
                      <div className="flex shrink-0 items-center gap-2">
                        {project.source_type ? (
                          <span className="rounded-full bg-[color:var(--app-bg-soft)] px-2 py-0.5 text-[11px] font-medium text-[color:var(--app-muted)]">
                            {project.source_type}
                          </span>
                        ) : null}
                        <button
                          type="button"
                          onClick={() => onDeleteProject(project.id, project.name)}
                          disabled={Boolean(deletingProjectIds[`delete-profile-project-${project.id}`])}
                          className="rounded-md border border-rose-300 bg-white px-2 py-1 text-[11px] font-medium text-rose-700 transition hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          {deletingProjectIds[`delete-profile-project-${project.id}`] ? 'Deleting...' : 'Delete'}
                        </button>
                      </div>
                    </div>
                    <p className="mt-1 text-sm text-[color:var(--app-muted)]">{project.description}</p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {project.technologies?.map((technology) => (
                        <span
                          key={technology}
                          className="rounded-md bg-white px-2 py-1 text-xs font-medium text-[color:var(--app-muted)] ring-1 ring-[color:var(--app-border)]"
                        >
                          {technology}
                        </span>
                      ))}
                    </div>
                    <p className="mt-3 text-sm leading-6 text-[color:var(--app-muted)]">{project.impact}</p>
                    {project.repo_url || project.project_url ? (
                      <p className="mt-2 text-xs text-[color:var(--app-muted)]">
                        Source:{' '}
                        <a
                          href={project.repo_url ?? project.project_url ?? '#'}
                          target="_blank"
                          rel="noreferrer"
                          className="font-medium text-[color:var(--app-accent)] underline decoration-[color:var(--app-border-strong)] underline-offset-2"
                        >
                          {project.repo_url ? 'Repository' : 'Project page'}
                        </a>
                      </p>
                    ) : null}
                    {project.metric_bullets?.length ? (
                      <div className="mt-3 rounded-md border border-[color:var(--app-border)] bg-white p-2">
                        <p className="text-xs font-semibold uppercase tracking-wide text-[color:var(--app-muted)]">
                          Metric evidence
                        </p>
                        <ul className="mt-1 space-y-1 text-xs text-[color:var(--app-muted)]">
                          {project.metric_bullets.map((bullet) => (
                            <li key={bullet}>- {bullet}</li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                  </article>
                ))}
              </div>
            </div>
          </section>
        </div>
      ) : null}
    </Panel>
  )
}
