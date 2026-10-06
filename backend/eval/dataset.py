from pathlib import Path

from pydantic import BaseModel

DATASET_PATH = Path(__file__).with_name("dataset.jsonl")


class EvalQuestion(BaseModel):
    id: str
    question: str
    category: str
    # 填的是「條」的 article_id（如 K0040012:53），不是切塊 id；範圍外題目為空
    expected_chunk_ids: list[str]
    expected_facts: list[str]
    should_refuse: bool
    verified: bool


def load_dataset(path: Path = DATASET_PATH) -> list[EvalQuestion]:
    with path.open(encoding="utf-8") as f:
        return [EvalQuestion.model_validate_json(line) for line in f if line.strip()]
