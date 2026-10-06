"""產生 eval/review.md：給人工逐題確認評估集用的審核單。

    uv run python -m eval.make_review

標準答案是我（Claude Code）讀條文擬的，沒有參考檢索結果；審核單把每題的條文原文攤開，
由 human 判斷是否正確，確認後把 dataset.jsonl 該題的 verified 改成 true。
"""

import re

from app.core.config import get_settings
from app.ingestion.chunk import load_processed
from eval.dataset import DATASET_PATH, load_dataset

MONEY_RE = re.compile(r"新臺幣[零一二三四五六七八九十百千萬]+元")
REVIEW_PATH = DATASET_PATH.with_name("review.md")

HEADER = """# 評估集審核單

資料版本：{data_version}。題目與標準答案是 Claude Code 讀條文草擬的，**沒有參考檢索結果**
（否則評估會變成系統自己打自己）。請逐題確認後，把 `eval/dataset.jsonl` 該題的
`"verified": false` 改成 `true`。

## 怎麼審

每題看三件事：

1. **條文選對了嗎？** 下方列出完整原文。答案要的資訊都在這些條文裡嗎？
   有沒有**漏掉**同樣能回答問題的條？（漏列會讓正確的檢索結果被算成沒命中。）列出的條都**必要**嗎？
2. **重點事實（expected_facts）對嗎？** 每項都要能在原文找到，數字不能抄錯。
   標「⚠」的是金額在條文原文找不到，請特別留意。
3. **範圍外的題目**：只要確認這題真的不在收錄的 5 部法規範圍內。

不確定的題目就保持 `verified: false`，它不會被計入指標。想改條文清單或事實，直接改 `dataset.jsonl`。
"""


def main() -> None:
    laws = load_processed(get_settings().data_dir / "processed")
    articles = {
        f"{law.pcode}:{a.article_no}": (law.law_name, a.article_no, a.text)
        for law in laws
        for a in law.articles
    }
    questions = load_dataset()
    out = [HEADER.format(data_version=laws[0].data_version)]
    for q in questions:
        out.append(f"---\n\n## {q.id}　{q.question}\n")
        out.append(
            f"- 類別：`{q.category}`　應拒答：{'是' if q.should_refuse else '否'}　"
            f"已驗證：{'是' if q.verified else '否'}"
        )
        if q.should_refuse:
            out.append("- 標準答案：（無，應拒答）\n- [ ] 確認這題不在收錄範圍內\n")
            continue
        combined = ""
        out.append("- 標準答案條文：" + "、".join(f"`{i}`" for i in q.expected_chunk_ids))
        for article_id in q.expected_chunk_ids:
            law_name, no, text = articles[article_id]
            combined += text
            quoted = "\n".join(f"> {line}" for line in text.split("\n"))
            out.append(f"\n### {article_id}　{law_name} 第 {no} 條\n\n{quoted}")
        out.append("\n**重點事實**")
        for fact in q.expected_facts:
            missing = [m for m in MONEY_RE.findall(fact) if m not in combined]
            flag = f"　⚠ 金額 {missing} 在條文中找不到" if missing else ""
            out.append(f"- [ ] {fact}{flag}")
        out.append("")
    REVIEW_PATH.write_text("\n".join(out), encoding="utf-8")
    print(f"寫入 {REVIEW_PATH}（{len(questions)} 題）")


if __name__ == "__main__":
    main()
