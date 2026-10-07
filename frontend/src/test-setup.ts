import '@testing-library/jest-dom/vitest'

// jsdom 沒有實作 scrollTo
window.scrollTo = () => {}
