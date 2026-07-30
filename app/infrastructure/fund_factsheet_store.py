"""Fund fact-sheet retrieval store.

Backs the "File Search" tool. In real (`OPENAI_API_KEY` set) mode, these same text
files are uploaded to an OpenAI vector store and attached to the Assistant via the
native `file_search` tool (see `openai_assistants_client.py`). In offline/mock mode,
this class does the retrieval itself with a small dependency-free keyword-overlap
ranking -- good enough to demonstrate the retrieval-augmented pattern deterministically
without needing embeddings or a paid API call.

SECURITY NOTE: retrieved fact-sheet text is treated as *untrusted* content once it
flows into a prompt -- see README "Security" section. We never interpolate retrieved
text into anything executed as code or as instructions to the model; it is only ever
surfaced as quoted reference material with a clear citation.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("fund_factsheet_store")

_WORD_RE = re.compile(r"[a-zA-Z']+")


def _tokenize(text: str) -> set[str]:
    return {w.lower() for w in _WORD_RE.findall(text) if len(w) > 2}


@dataclass(frozen=True)
class FactsheetMatch:
    """A single retrieval hit, with a citation back to its source file."""

    source_file: str
    fund_name: str
    snippet: str
    score: float


class FundFactsheetStore:
    """Loads all `*.txt` fund fact sheets from a directory into memory and supports
    simple keyword-overlap search over them."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory
        self._documents: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if not self._directory.is_dir():
            logger.warning("fund_factsheets_dir_missing", extra={"directory": str(self._directory)})
            return
        for path in sorted(self._directory.glob("*.txt")):
            self._documents[path.name] = path.read_text(encoding="utf-8")
        logger.info("fund_factsheets_loaded", extra={"count": len(self._documents)})

    @property
    def file_paths(self) -> list[Path]:
        """Absolute paths of all loaded fact sheets -- used to seed a real OpenAI
        vector store when running in live mode."""
        return sorted(self._directory.glob("*.txt")) if self._directory.is_dir() else []

    def _fund_name(self, text: str) -> str:
        first_line = text.strip().splitlines()[0] if text.strip() else "Unknown Fund"
        return first_line.replace("Fund Name:", "").strip()

    def search(self, query: str, top_k: int = 2) -> list[FactsheetMatch]:
        """Return up to `top_k` fact sheets ranked by token overlap with `query`.

        This is intentionally simple (no embeddings) so it stays deterministic and
        dependency-free for offline mode. It's a reasonable stand-in for semantic
        search at this scale (a handful of short fact sheets).
        """
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        scored: list[FactsheetMatch] = []
        for filename, text in self._documents.items():
            doc_tokens = _tokenize(text)
            overlap = query_tokens & doc_tokens
            if not overlap:
                continue
            score = len(overlap) / len(query_tokens)
            snippet = self._best_snippet(text, overlap)
            scored.append(
                FactsheetMatch(
                    source_file=filename,
                    fund_name=self._fund_name(text),
                    snippet=snippet,
                    score=round(score, 3),
                )
            )

        scored.sort(key=lambda m: m.score, reverse=True)
        return scored[:top_k]

    @staticmethod
    def _best_snippet(text: str, overlap_tokens: set[str], max_len: int = 320) -> str:
        """Return the paragraph containing the most overlap tokens, truncated."""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if not paragraphs:
            return text[:max_len]
        best = max(paragraphs, key=lambda p: len(_tokenize(p) & overlap_tokens))
        return best[:max_len]
