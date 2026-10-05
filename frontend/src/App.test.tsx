import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import App, { healthLabel } from './App'

afterEach(() => vi.unstubAllGlobals())

describe('healthLabel', () => {
  it('maps each query status to text', () => {
    expect(healthLabel('success')).toBe('後端連線正常')
    expect(healthLabel('error')).toBe('後端無法連線')
    expect(healthLabel('pending')).toBe('檢查中…')
  })
})

describe('App', () => {
  it('shows connected when /api/health returns ok', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: 'ok' }) }),
    )
    render(
      <QueryClientProvider client={new QueryClient()}>
        <App />
      </QueryClientProvider>,
    )
    expect(await screen.findByText('後端連線正常')).toBeInTheDocument()
  })
})
