type Props = {
  children: string
}

export function AiText({ children }: Props) {
  const blocks = children
    .split(/\n{2,}/)
    .map((block) => block.trim())
    .filter(Boolean)

  return (
    <div className="space-y-3 text-sm leading-6 text-[color:var(--app-ink)]">
      {blocks.map((block, index) => {
        const lines = block.split('\n').filter(Boolean)
        const isList = lines.every((line) => /^[-*]\s+/.test(line.trim()))
        if (isList) {
          return (
            <ul key={`${block}-${index}`} className="list-disc space-y-1 pl-5 text-[color:var(--app-muted)]">
              {lines.map((line) => (
                <li key={line}>{line.replace(/^[-*]\s+/, '')}</li>
              ))}
            </ul>
          )
        }
        return (
          <p key={`${block}-${index}`} className="whitespace-pre-line">
            {block}
          </p>
        )
      })}
    </div>
  )
}
