const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000/api/v1'

export { API_BASE_URL }

export async function requestApi<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)
  if (init?.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
    credentials: init?.credentials ?? 'include',
  })

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`
    try {
      const payload = await response.json()
      if (typeof payload?.detail === 'string') {
        message = payload.detail
      } else if (Array.isArray(payload?.detail)) {
        message = payload.detail
          .map((item: { msg?: string }) => item.msg)
          .filter(Boolean)
          .join('; ') || message
      }
    } catch {
      // Keep the generic status message if the backend did not return JSON.
    }
    const error = new Error(message)
    ;(error as Error & { status?: number }).status = response.status
    throw error
  }

  return (await response.json()) as T
}

export async function requestCareerInboxSync<T extends { id: string }>(): Promise<T[]> {
  try {
    return await requestApi<T[]>('/gmail/sync-career', {
      method: 'POST',
    })
  } catch (error) {
    const status = (error as Error & { status?: number }).status
    if (status !== 404) {
      throw error
    }
  }

  const fallbackQueries = [
    'newer_than:180d {application interview assessment recruiter "coding challenge" "thank you for applying" "we received your application"}',
    'newer_than:180d {from:greenhouse-mail.io from:greenhouse.io from:lever.co from:ashbyhq.com from:myworkday.com from:icims.com from:smartrecruiters.com}',
  ]
  const emailsById = new Map<string, T>()
  for (const query of fallbackQueries) {
    const controller = new AbortController()
    const timer = window.setTimeout(() => controller.abort(), 20000)
    try {
      const syncedEmails = await requestApi<T[]>('/gmail/sync', {
        method: 'POST',
        signal: controller.signal,
        body: JSON.stringify({
          query,
          max_results: 50,
          skip_existing: true,
        }),
      })
      syncedEmails.forEach((email) => emailsById.set(email.id, email))
    } catch {
      // Keep the dashboard responsive if one Gmail search is slow or unsupported.
    } finally {
      window.clearTimeout(timer)
    }
  }
  return [...emailsById.values()]
}

export function cvArtifactUrl(cvVersionId: string, artifactFormat: 'pdf' | 'tex'): string {
  return `${API_BASE_URL}/cv-versions/${cvVersionId}/download?artifact_format=${artifactFormat}`
}
