type Props = {
  tone: 'good' | 'warning' | 'bad' | 'neutral'
  children: React.ReactNode
}

export function StatusPill({ tone, children }: Props) {
  return <span className={`status-pill ${tone}`}>{children}</span>
}
