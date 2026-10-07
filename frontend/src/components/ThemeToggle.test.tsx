import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeToggle } from './ThemeToggle'

beforeEach(() => {
  localStorage.clear()
  delete document.documentElement.dataset.theme
})

describe('ThemeToggle', () => {
  it('starts on following the system and says what the next click does', () => {
    render(<ThemeToggle />)
    expect(
      screen.getByRole('button', { name: '外觀：跟隨系統，點一下切換為亮色' }),
    ).toBeInTheDocument()
    expect(document.documentElement.dataset.theme).toBeUndefined()
  })

  it('cycles through light, dark and system, applying and remembering each', async () => {
    const user = userEvent.setup()
    render(<ThemeToggle />)
    await user.click(screen.getByRole('button'))
    expect(document.documentElement.dataset.theme).toBe('light')
    expect(localStorage.getItem('theme')).toBe('light')
    await user.click(screen.getByRole('button'))
    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(screen.getByRole('button', { name: /外觀：暗色/ })).toBeInTheDocument()
    await user.click(screen.getByRole('button'))
    expect(document.documentElement.dataset.theme).toBeUndefined()
    expect(localStorage.getItem('theme')).toBeNull()
  })

  it('restores the saved choice on the next visit', () => {
    localStorage.setItem('theme', 'dark')
    render(<ThemeToggle />)
    expect(screen.getByRole('button', { name: /外觀：暗色/ })).toBeInTheDocument()
  })
})
