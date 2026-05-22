import type { ComponentType, ReactNode } from 'react'

import { cleanDisplayName, cleanDisplayText, getProfilePreference } from '../lib/text'
import type { CandidateProfile, ResourceState } from '../types/dashboard'

type BannerComponent = ComponentType<{ title: string; state: ResourceState<unknown> }>
type PanelComponent = ComponentType<{ title: string; subtitle?: string; children: ReactNode }>

type Props = {
  profile: ResourceState<CandidateProfile | null>
  Panel: PanelComponent
  ResourceBanner: BannerComponent
}

export function ProfileSection({ profile, Panel, ResourceBanner }: Props) {
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
              <h3 className="crm-label">
                Projects
              </h3>
              <div className="mt-4 space-y-4">
                {profile.data.projects.map((project) => (
                  <article key={project.id} className="crm-card p-3">
                    <p className="text-sm font-medium text-[color:var(--app-ink)]">{project.name}</p>
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
