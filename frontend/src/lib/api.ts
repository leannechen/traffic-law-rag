export type HealthResponse = { status: string }

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch('/api/health')
  if (!res.ok) throw new Error(`health check failed: ${res.status}`)
  return res.json()
}
