import '@testing-library/jest-dom/vitest'

// jsdom 沒有實作 scrollTo、scrollIntoView
window.scrollTo = () => {}

Element.prototype.scrollIntoView = () => {}

// jsdom 沒有 matchMedia：預設是桌面版面；測試手機版面時再覆寫
window.matchMedia = (query: string) =>
  ({
    matches: false,
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  }) as unknown as MediaQueryList
