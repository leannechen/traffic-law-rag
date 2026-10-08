# 交通法規資料庫（Traffic Law RAG）

[![CI](https://github.com/leannechen/traffic-law-rag/actions/workflows/ci.yml/badge.svg)](https://github.com/leannechen/traffic-law-rag/actions/workflows/ci.yml)

用白話問台灣交通法規，系統只根據條文回答，並標註每一句話的出處。FastAPI 後端＋React 前端。

> 這份 README 是 Step 11 暫放的簡版（讓 CI badge 有地方放）；完整的介紹、架構圖、評估結果與技術取捨會在 Step 13 改寫。

## 快速開始

```bash
cp .env.example .env            # 填入 ANTHROPIC_API_KEY、VOYAGE_API_KEY
docker compose up --build       # 前端 http://localhost:5173、後端 http://localhost:8010
```

開發與測試指令見 [CLAUDE.md](CLAUDE.md)；實作規格見 [docs/02-implementation-spec.md](docs/02-implementation-spec.md)，技術決策見 [docs/decisions/](docs/decisions/)。
