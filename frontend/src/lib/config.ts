// 建置時由 VITE_GITHUB_URL 注入（見 .env.example）；沒設就用公開 repo
export const GITHUB_URL: string =
  import.meta.env.VITE_GITHUB_URL || 'https://github.com/leannechen/traffic-law'
