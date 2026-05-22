export function truncate(text: string | null | undefined, maxLength: number): string {
  if (!text) {
    return 'No content available.'
  }

  if (text.length <= maxLength) {
    return text
  }

  return `${text.slice(0, maxLength - 3)}...`
}

export function unknownToDisplayString(value: unknown): string {
  if (typeof value === 'string') {
    return value
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value)
  }
  return ''
}

export function payloadText(value: unknown): string {
  if (!value) {
    return 'No raw source metadata stored yet.'
  }
  return JSON.stringify(value, null, 2)
}

export function cleanDisplayText(text: string): string {
  return text.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim()
}

export function cleanDisplayName(name: string | null | undefined): string {
  if (!name) {
    return 'Profile not loaded'
  }
  return cleanDisplayText(name)
}

export function getProfilePreference(
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

export function normalizeForMatch(value: string | null | undefined): string {
  return cleanDisplayText(value ?? '').toLowerCase()
}
