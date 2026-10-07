export type ExampleQuestion = { category: string; question: string }

// 桌面顯示 6 題、手機顯示前 4 題；拒答頁的「可以試著這樣問」取前 2 題。
export const EXAMPLE_QUESTIONS: ExampleQuestion[] = [
  { category: '罰鍰', question: '紅燈右轉會被罰多少錢？' },
  { category: '處罰', question: '酒駕被抓到會有什麼處罰？' },
  { category: '事故處理', question: '發生小擦撞，一定要報警嗎？' },
  { category: '行為規範', question: '騎機車可以載幾個人？' },
  { category: '拖吊', question: '違規停車被拖吊，要去哪裡領車？' },
  { category: '強制險', question: '強制險可以理賠哪些項目？' },
]
