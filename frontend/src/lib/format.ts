/** 資料裡的日期是 YYYYMMDD；顯示成 YYYY-MM-DD。其他格式原樣回傳。 */
export function formatDate(value: string): string {
  const m = /^(\d{4})(\d{2})(\d{2})$/.exec(value)
  return m ? `${m[1]}-${m[2]}-${m[3]}` : value
}
