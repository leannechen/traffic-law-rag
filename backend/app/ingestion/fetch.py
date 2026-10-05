"""下載全國法規資料庫開放資料（data.gov.tw 18289、18290）的 ZIP 到 data/raw/{date}/。

下載網址是 data.gov.tw 資料集頁面登記的官方檔案連結，不是 law.moj.gov.tw 的網頁。
"""

import argparse
import shutil
import urllib.request
from datetime import date
from pathlib import Path

from app.core.config import get_settings

DATASETS: dict[str, str] = {
    "law.zip": "https://sendlaw.moj.gov.tw/PublicData/GetFile.ashx?DType=XML&AuData=CF",
    "order.zip": "https://sendlaw.moj.gov.tw/PublicData/GetFile.ashx?DType=XML&AuData=CM",
}


def fetch(raw_dir: Path) -> list[Path]:
    """下載缺少的 ZIP；已存在的直接跳過。回傳所有 ZIP 路徑。"""
    raw_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, url in DATASETS.items():
        dest = raw_dir / name
        paths.append(dest)
        if dest.exists():
            print(f"skip   {dest}（已有快取）")
            continue
        tmp = dest.with_suffix(".part")
        print(f"fetch  {url}")
        with urllib.request.urlopen(url, timeout=120) as res, tmp.open("wb") as out:
            shutil.copyfileobj(res, out)
        tmp.rename(dest)
        print(f"saved  {dest}（{dest.stat().st_size / 1e6:.1f} MB）")
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default=date.today().isoformat(), help="YYYY-MM-DD，預設今天")
    args = parser.parse_args()
    fetch(get_settings().data_dir / "raw" / args.date)


if __name__ == "__main__":
    main()
