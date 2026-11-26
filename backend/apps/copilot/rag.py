import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

POLICIES_DIR = Path(__file__).resolve().parent / "policies"
_TOKEN_RE = re.compile(r"[a-z0-9]{2,}")
_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "are",
        "was",
        "were",
        "have",
        "has",
        "can",
        "may",
        "must",
        "will",
        "when",
        "any",
        "all",
        "into",
        "their",
        "within",
        "what",
        "how",
        "about",
        "your",
    }
)


@dataclass(frozen=True)
class PolicyChunk:
    source: str
    section: str
    content: str
    tokens: tuple[str, ...]


def _tokenize(text: str) -> list[str]:
    return [tok for tok in _TOKEN_RE.findall(text.lower()) if tok not in _STOPWORDS]


class PolicyKnowledgeBase:
    """Lightweight, deterministic TF-IDF RAG retriever over DjangoAir policy Markdown docs."""

    def __init__(self, policies_dir: Path = POLICIES_DIR):
        self.chunks: list[PolicyChunk] = []
        self.doc_freq: Counter[str] = Counter()
        self._load(policies_dir)

    def _load(self, policies_dir: Path) -> None:
        if not policies_dir.exists():
            return
        for md_file in sorted(policies_dir.glob("*.md")):
            raw = md_file.read_text(encoding="utf-8")
            current_section = md_file.stem.replace("_", " ").title()
            buffer: list[str] = []

            def _flush(section: str, lines: list[str], filename: str = md_file.name) -> None:
                body = "\n".join(lines).strip()
                if not body:
                    return
                toks = tuple(_tokenize(f"{section} {body}"))
                self.chunks.append(
                    PolicyChunk(source=filename, section=section, content=body, tokens=toks)
                )
                for unique_tok in set(toks):
                    self.doc_freq[unique_tok] += 1

            for line in raw.splitlines():
                if line.startswith("## "):
                    _flush(current_section, buffer)
                    current_section = line[3:].strip()
                    buffer = []
                elif line.startswith("# "):
                    continue
                else:
                    buffer.append(line)
            _flush(current_section, buffer)

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        query_tokens = _tokenize(query)
        if not query_tokens or not self.chunks:
            return []

        n_docs = len(self.chunks)
        q_counts = Counter(query_tokens)
        q_weights: dict[str, float] = {}
        for tok, cnt in q_counts.items():
            idf = math.log((1 + n_docs) / (1 + self.doc_freq.get(tok, 0))) + 1.0
            q_weights[tok] = (1.0 + math.log(cnt)) * idf
        q_norm = math.sqrt(sum(v * v for v in q_weights.values())) or 1.0

        scored: list[tuple[float, PolicyChunk]] = []
        for chunk in self.chunks:
            if not chunk.tokens:
                continue
            c_counts = Counter(chunk.tokens)
            dot = 0.0
            c_sq = 0.0
            for tok, cnt in c_counts.items():
                idf = math.log((1 + n_docs) / (1 + self.doc_freq.get(tok, 0))) + 1.0
                w = (1.0 + math.log(cnt)) * idf
                c_sq += w * w
                if tok in q_weights:
                    dot += w * q_weights[tok]
            if dot > 0:
                score = dot / (q_norm * (math.sqrt(c_sq) or 1.0))
                scored.append((score, chunk))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            {
                "source": chunk.source,
                "section": chunk.section,
                "score": round(score, 4),
                "excerpt": chunk.content,
            }
            for score, chunk in scored[: max(1, min(top_k, 5))]
        ]


@lru_cache(maxsize=1)
def get_policy_kb() -> PolicyKnowledgeBase:
    return PolicyKnowledgeBase()
