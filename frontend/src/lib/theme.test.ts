import { applyMode, nextMode, readMode, saveMode } from './theme'

beforeEach(() => {
  localStorage.clear()
  delete document.documentElement.dataset.theme
})

describe('theme', () => {
  it('cycles system -> light -> dark -> system', () => {
    expect(nextMode('system')).toBe('light')
    expect(nextMode('light')).toBe('dark')
    expect(nextMode('dark')).toBe('system')
  })

  it('defaults to following the system when nothing is saved or the value is unknown', () => {
    expect(readMode()).toBe('system')
    localStorage.setItem('theme', 'purple')
    expect(readMode()).toBe('system')
  })

  it('saves light and dark, and forgets the choice for system', () => {
    saveMode('dark')
    expect(readMode()).toBe('dark')
    saveMode('system')
    expect(localStorage.getItem('theme')).toBeNull()
  })

  it('sets data-theme for light and dark, removes it for system', () => {
    applyMode('dark')
    expect(document.documentElement.dataset.theme).toBe('dark')
    applyMode('light')
    expect(document.documentElement.dataset.theme).toBe('light')
    applyMode('system')
    expect(document.documentElement.dataset.theme).toBeUndefined()
  })

  it('does not throw when storage is unavailable', () => {
    const broken = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    const broken2 = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    expect(readMode()).toBe('system')
    expect(() => saveMode('dark')).not.toThrow()
    broken.mockRestore()
    broken2.mockRestore()
  })
})
