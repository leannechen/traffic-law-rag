from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    anthropic_api_key: str = ""
    voyage_api_key: str = ""
    embedding_model: str = "voyage-4"
    llm_model: str = "claude-sonnet-5-5"
    llm_use_fallbacks: bool = True
    # 拒答門檻：只當第一道粗篩（寧可漏拒交給模型，不要誤拒），依據見 ADR 0004／0005
    gate_threshold: float = 0.40
    # 問題改寫預設關閉；評估顯示有益才開啟（ADR 0005）
    rewrite_enabled: bool = False
    # /api/ask 速率限制：每個來源 IP 在視窗內最多幾次（單一實例、記憶體內計數）
    rate_limit_requests: int = Field(default=10, ge=1)
    rate_limit_window_seconds: int = Field(default=60, ge=1)
    # 部署在反向代理後面時才開，否則 X-Forwarded-For 可被偽造
    trust_proxy: bool = False
    cors_origins: list[str] = ["http://localhost:5173"]
    data_dir: Path = REPO_ROOT / "data"
    # 設了才由後端一併提供前端建置檔（部署用，同源所以不需要 CORS；ADR 0007）
    static_dir: Path | None = None

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def index_dir(self) -> Path:
        return self.data_dir / "index"

    @property
    def eval_latest_path(self) -> Path:
        """評估頁顯示的那一份結果（用 run_generation_eval --publish 產生）。"""
        return REPO_ROOT / "backend" / "eval" / "results" / "latest.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()
