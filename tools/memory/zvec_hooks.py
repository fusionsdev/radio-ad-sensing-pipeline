"""
Phase 2 architecture hooks — zvec semantic index (NOT implemented in Phase 1).

Planned flow:
  project-memory/*.md → markdown indexer → zvec → semantic search → Hermes agent

Repository: https://github.com/alibaba/zvec
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VAULT_ROOT = PROJECT_ROOT / "project-memory"
INDEX_DIR = PROJECT_ROOT / "data" / "memory-index"


@dataclass(frozen=True)
class ZvecIndexConfig:
    vault_root: Path = VAULT_ROOT
    index_dir: Path = INDEX_DIR
    embedding_model: str = "phase2-tbd"
    enabled: bool = False  # Phase 1: hooks only


def list_indexable_markdown(config: ZvecIndexConfig | None = None) -> list[Path]:
    """Return vault markdown paths that would be indexed in Phase 2."""
    cfg = config or ZvecIndexConfig()
    if not cfg.vault_root.exists():
        return []
    return sorted(cfg.vault_root.rglob("*.md"))


def build_index_manifest(config: ZvecIndexConfig | None = None) -> dict:
    """
    Stub manifest for future zvec indexer.
    Phase 1 harness may call this to verify vault discoverability.
    """
    cfg = config or ZvecIndexConfig()
    files = list_indexable_markdown(cfg)
    return {
        "phase": 1,
        "zvec_enabled": cfg.enabled,
        "vault_root": str(cfg.vault_root),
        "index_dir": str(cfg.index_dir),
        "markdown_count": len(files),
        "files": [str(p.relative_to(PROJECT_ROOT)) for p in files[:50]],
        "truncated": len(files) > 50,
    }


def index_vault(_config: ZvecIndexConfig | None = None) -> None:
    """Phase 2 placeholder — raises until zvec integration ships."""
    raise NotImplementedError(
        "zvec indexing is Phase 2 only. Use Obsidian MCP + project-memory/ in Phase 1."
    )