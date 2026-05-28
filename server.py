#!/usr/bin/env python3
"""
Oracle Fusion Docs MCP Server
─────────────────────────────
Universal access to Oracle Fusion Cloud documentation (HCM, ERP, EPM, SCM, CX, Projects).
No API keys required. No maintenance. Always up-to-date.

Uses Jina Reader (https://r.jina.ai/) for server-side rendering of Oracle's
JavaScript-heavy documentation pages into clean markdown.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
import sys
import time
from typing import Optional
from urllib.parse import quote

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

# ── Config ───────────────────────────────────────────────────

mcp = FastMCP("oracle-fusion-docs")

MAX_PAGE_CHARS = 15_000
JINA_READER_URL = "https://r.jina.ai/"
REQUEST_TIMEOUT = 25.0
_user_agent = "OracleDocsMCP/2.0"

# Logger setup (MCP hosts capture standard error for logging)
logger = logging.getLogger(__name__)

# ── Caching ──────────────────────────────────────────────────

class ResponseCache:
    """Lightweight in-memory LRU cache with time-to-live (TTL) expiration,
    backed by a persistent disk cache at ~/.cache/oracle-fusion-docs/.
    """
    def __init__(self, max_size: int = 50, ttl_seconds: int = 3600, disk_ttl_seconds: int = 86400, max_disk_entries: int = 200):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.disk_ttl_seconds = disk_ttl_seconds
        self.max_disk_entries = max_disk_entries
        # Maps URL -> (content_string, expiration_timestamp)
        self.cache: dict[str, tuple[str, float]] = {}
        self.hits = 0
        self.misses = 0
        
        # Disk cache directory setup
        try:
            self.cache_dir = Path.home() / ".cache" / "oracle-fusion-docs"
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self.disk_enabled = True
        except Exception as e:
            logger.warning(
                "Failed to initialize persistent disk cache directory: %s. "
                "Falling back to in-memory caching only.",
                e
            )
            self.disk_enabled = False

        # Load valid entries from disk to warm in-memory cache on startup
        if self.disk_enabled:
            self._warm_cache_from_disk()

    def _warm_cache_from_disk(self) -> None:
        """Scan persistent cache directory and load unexpired entries into memory."""
        try:
            now = time.time()
            expired_entries = 0
            corrupt_entries = 0
            
            # 1. Clean expired and corrupt files from disk
            for p in self.cache_dir.glob("*.json"):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    
                    timestamp = data["timestamp"]
                    ttl = data.get("ttl", self.disk_ttl_seconds)
                    
                    if now >= timestamp + ttl:
                        expired_entries += 1
                        try:
                            p.unlink()
                        except Exception:
                            pass
                except Exception:
                    corrupt_entries += 1
                    try:
                        p.unlink()
                    except Exception:
                        pass

            # 2. Collect remaining valid files sorted by modification time descending
            valid_files = []
            for p in self.cache_dir.glob("*.json"):
                try:
                    mtime = p.stat().st_mtime
                    valid_files.append((p, mtime))
                except Exception:
                    pass
            
            valid_files.sort(key=lambda x: x[1], reverse=True)

            # 3. Load up to `max_size` newest entries into memory
            loaded_entries = 0
            for p, _ in reversed(valid_files[:self.max_size]):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    url = data["url"]
                    content = data["content"]
                    timestamp = data["timestamp"]
                    ttl = data.get("ttl", self.disk_ttl_seconds)
                    
                    remaining_disk_ttl = (timestamp + ttl) - now
                    if remaining_disk_ttl > 0:
                        in_memory_ttl = min(self.ttl_seconds, remaining_disk_ttl)
                        expires_at = now + in_memory_ttl
                        self.cache[url] = (content, expires_at)
                        loaded_entries += 1
                except Exception:
                    pass

            if loaded_entries > 0 or expired_entries > 0 or corrupt_entries > 0:
                logger.info(
                    "Warmed cache from disk: loaded %d valid entries. "
                    "Cleaned %d expired and %d corrupt entries on disk.",
                    loaded_entries,
                    expired_entries,
                    corrupt_entries
                )
        except Exception as e:
            logger.warning("Error during warming cache from disk: %s", e)

    def _save_to_disk(self, url: str, content: str) -> None:
        """Persist a cache entry to disk and enforce the 200-file limit."""
        if not self.disk_enabled:
            return

        try:
            filename = hashlib.md5(url.encode("utf-8")).hexdigest() + ".json"
            filepath = self.cache_dir / filename
            
            # Enforce max disk entries (200) by evicting oldest by mtime
            if not filepath.exists():
                disk_files = list(self.cache_dir.glob("*.json"))
                if len(disk_files) >= self.max_disk_entries:
                    files_with_mtime = []
                    for p in disk_files:
                        try:
                            files_with_mtime.append((p, p.stat().st_mtime))
                        except Exception:
                            pass
                    
                    if files_with_mtime:
                        files_with_mtime.sort(key=lambda x: x[1])
                        oldest_path = files_with_mtime[0][0]
                        try:
                            oldest_path.unlink()
                            logger.info("Evicted oldest disk cache entry: %s", oldest_path.name)
                        except Exception as e:
                            logger.warning(
                                "Failed to evict oldest disk cache entry %s: %s",
                                oldest_path.name,
                                e
                            )

            # Save the entry
            data = {
                "url": url,
                "content": content,
                "timestamp": time.time(),
                "ttl": self.disk_ttl_seconds
            }
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning("Failed to save entry to disk cache for URL %s: %s", url, e)

    def _set_memory(self, url: str, content: str, expires_at: float) -> None:
        """Helper to write to in-memory cache with LRU eviction."""
        if url in self.cache:
            self.cache.pop(url)
        
        if len(self.cache) >= self.max_size:
            oldest_key = next(iter(self.cache))
            self.cache.pop(oldest_key)
            
        self.cache[url] = (content, expires_at)

    def get(self, url: str) -> str | None:
        """Retrieve from in-memory cache or persistent disk cache."""
        now = time.time()

        # 1. Check in-memory cache
        if url in self.cache:
            content, expires_at = self.cache[url]
            if now < expires_at:
                self.hits += 1
                # Move to end to maintain LRU order in memory
                self.cache.pop(url)
                self.cache[url] = (content, expires_at)
                return content
            else:
                self.cache.pop(url)

        # 2. Check disk cache
        if self.disk_enabled:
            filename = hashlib.md5(url.encode("utf-8")).hexdigest() + ".json"
            filepath = self.cache_dir / filename
            if filepath.exists():
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    
                    url_on_disk = data["url"]
                    content = data["content"]
                    timestamp = data["timestamp"]
                    ttl = data.get("ttl", self.disk_ttl_seconds)
                    
                    if now < timestamp + ttl:
                        # Valid disk entry! Load into memory
                        remaining_disk_ttl = (timestamp + ttl) - now
                        in_memory_ttl = min(self.ttl_seconds, remaining_disk_ttl)
                        expires_at = now + in_memory_ttl
                        self._set_memory(url, content, expires_at)
                        
                        self.hits += 1
                        logger.info("fetch_oracle_page: disk cache HIT for URL: %s", url)
                        return content
                    else:
                        # Expired on disk
                        try:
                            filepath.unlink()
                        except Exception:
                            pass
                except Exception as e:
                    logger.debug("Failed to read disk cache file %s: %s", filepath.name, e)

        self.misses += 1
        return None

    def set(self, url: str, content: str) -> None:
        """Write-through: store in memory and on disk."""
        # 1. Store in memory (1 hour TTL)
        expires_at = time.time() + self.ttl_seconds
        self._set_memory(url, content, expires_at)
        
        # 2. Store on disk (24 hour TTL)
        self._save_to_disk(url, content)

    def get_disk_stats(self) -> tuple[int, float]:
        """Return (number of files on disk, total size of files on disk in KB)."""
        if not self.disk_enabled:
            return 0, 0.0
        try:
            count = 0
            total_bytes = 0
            for p in self.cache_dir.glob("*.json"):
                try:
                    count += 1
                    total_bytes += p.stat().st_size
                except Exception:
                    pass
            return count, total_bytes / 1024.0
        except Exception:
            return 0, 0.0

    def get_stats(self) -> dict[str, int | float]:
        total = self.hits + self.misses
        ratio = (self.hits / total) if total > 0 else 0.0
        disk_count, disk_size_kb = self.get_disk_stats()
        return {
            "hits": self.hits,
            "misses": self.misses,
            "total_requests": total,
            "hit_ratio": ratio,
            "size": len(self.cache),
            "disk_count": disk_count,
            "disk_size_kb": disk_size_kb,
        }

_page_cache = ResponseCache(max_size=50, ttl_seconds=3600)

def _cache_stats() -> None:
    """Log cache hit/miss ratio and statistics at INFO level."""
    stats = _page_cache.get_stats()
    logger.info(
        "Cache Statistics: Hits: %d, Misses: %d, Hit Ratio: %.2f%%, "
        "Active Entries: %d/%d (Disk: %d entries, %.2f KB)",
        stats["hits"],
        stats["misses"],
        stats["hit_ratio"] * 100,
        stats["size"],
        _page_cache.max_size,
        stats["disk_count"],
        stats["disk_size_kb"]
    )

# ── Retry with Exponential Backoff ──────────────────────────

def _should_retry(exception: Exception) -> bool:
    """Predicate function to determine if an exception warrants a retry."""
    if isinstance(exception, (httpx.TimeoutException, httpx.NetworkError)):
        return True
    if isinstance(exception, httpx.HTTPStatusError):
        return exception.response.status_code == 429
    return False

def _log_retry_attempt(retry_state) -> None:
    """Log retry details at WARNING level."""
    exc = retry_state.outcome.exception()
    next_action = f"waiting {retry_state.next_action.sleep:.1f}s before next attempt" if retry_state.next_action else "no more retries"
    url = retry_state.args[0] if retry_state.args else "unknown URL"
    logger.warning(
        "Retry attempt %d failed for URL %s: %s. %s.",
        retry_state.attempt_number,
        url,
        f"{type(exc).__name__}: {exc}" if exc else "No exception",
        next_action
    )

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=8),
    retry=retry_if_exception(_should_retry),
    before_sleep=_log_retry_attempt,
    reraise=True
)
async def _jina_get(url: str) -> httpx.Response:
    """Fetch URL via Jina Reader proxy with retry logic."""
    async with httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT,
        follow_redirects=True,
        headers={"Accept": "text/markdown", "User-Agent": _user_agent},
    ) as client:
        resp = await client.get(f"{JINA_READER_URL}{url}")
        resp.raise_for_status()
        return resp


# ── Pydantic Models ─────────────────────────────────────────

class SearchInput(BaseModel):
    """Input for search_oracle_docs."""
    query: str = Field(
        ...,
        description="Natural language search query (e.g. 'payroll fast formula', "
                    "'absence management implementation', 'otbi subject areas')",
        min_length=2,
        max_length=500,
    )
    max_results: int = Field(
        default=10,
        description="Maximum number of results to return (1-10)",
        ge=1,
        le=10,
    )


class FetchInput(BaseModel):
    """Input for fetch_oracle_page."""
    url: str = Field(
        ...,
        description="Full URL of an Oracle documentation page under docs.oracle.com",
        min_length=20,
        max_length=1000,
    )


# ── Keyword → URL Index ──────────────────────────────────────
# Maps common Oracle Fusion topics to documentation URLs.
# Jina Reader fetches the live page, so content is always current.
# ~200 entries covering all major Fusion Cloud modules.

_HCM = "https://docs.oracle.com/en/cloud/saas/human-resources"
_ERP = "https://docs.oracle.com/en/cloud/saas/financials"
_EPM = "https://docs.oracle.com/en/cloud/saas/enterprise-performance-management-common"
_SCM = "https://docs.oracle.com/en/cloud/saas/supply-chain-management"
_PR  = "https://docs.oracle.com/en/cloud/saas/procurement"
_PRJ = "https://docs.oracle.com/en/cloud/saas/projects"
_CX  = "https://docs.oracle.com/en/cloud/saas"
_COM = "https://docs.oracle.com/en/cloud/saas/applications-common"

TOPIC_INDEX: dict[str, str] = {
    # ━━━ HCM — Core HR & Workforce ━━━
    "implementing global hr": f"{_HCM}/faigh/index.html",
    "global hr implementation": f"{_HCM}/faigh/index.html",
    "workforce structures": f"{_HCM}/faigh/index.html",
    "person management": f"{_HCM}/faigh/index.html",
    "employment information": f"{_HCM}/faigh/index.html",
    "document records": f"{_HCM}/faigh/index.html",
    "checklists": f"{_HCM}/faigh/index.html",
    "workforce lifecycle": f"{_HCM}/faigh/index.html",
    "work directory": f"{_HCM}/faigh/index.html",
    "line manager": f"{_HCM}/faigh/index.html",

    # ━━━ HCM — Recruiting ━━━
    "recruiting": f"{_HCM}/fairs/index.html",
    "recruiting implementation": f"{_HCM}/fairs/index.html",
    "implementing recruiting": f"{_HCM}/fairs/index.html",
    "candidate experience": f"{_HCM}/fairs/index.html",
    "career sites": f"{_HCM}/fairs/index.html",
    "career site": f"{_HCM}/fairs/index.html",
    "job requisitions": f"{_HCM}/fairs/index.html",
    "offer management": f"{_HCM}/fairs/index.html",
    "recruiting agency": f"{_HCM}/fairs/index.html",
    "recruiting analytics": f"{_HCM}/fairs/index.html",

    # ━━━ HCM — Talent ━━━
    "talent management": f"{_HCM}/faits/index.html",
    "talent review": f"{_HCM}/faits/index.html",
    "succession planning": f"{_HCM}/faits/index.html",
    "talent profiles": f"{_HCM}/faits/index.html",
    "talent pools": f"{_HCM}/faits/index.html",
    "career development": f"{_HCM}/faits/index.html",
    "performance management": f"{_HCM}/faits/index.html",
    "goal management": f"{_HCM}/faits/index.html",
    "goals": f"{_HCM}/faits/index.html",

    # ━━━ HCM — Payroll ━━━
    "implementing payroll": f"{_HCM}/faipy/index.html",
    "payroll implementation": f"{_HCM}/faipy/index.html",
    "payroll": f"{_HCM}/faipy/index.html",
    "element entries": f"{_HCM}/faipy/index.html",
    "balance definitions": f"{_HCM}/faipy/index.html",
    "payroll flow": f"{_HCM}/faipy/index.html",
    "payroll costing": f"{_HCM}/faipy/index.html",
    "payroll batch loader": f"{_HCM}/faipy/index.html",

    # ━━━ HCM — Fast Formulas ━━━
    "fast formula": f"{_HCM}/faihf/index.html",
    "fast formulas": f"{_HCM}/faihf/index.html",
    "administering fast formulas": f"{_HCM}/oapff/index.html",

    # ━━━ HCM — Compensation ━━━
    "compensation": f"{_HCM}/faicw/index.html",
    "compensation management": f"{_HCM}/faicw/index.html",
    "salary basis": f"{_HCM}/faicw/index.html",
    "grade rates": f"{_HCM}/faicw/index.html",
    "variable allocation": f"{_HCM}/faicw/index.html",
    "total compensation": f"{_HCM}/faicw/index.html",
    "implementing compensation": f"{_HCM}/faicw/index.html",

    # ━━━ HCM — Benefits ━━━
    "benefits": f"{_HCM}/faibn/index.html",
    "benefits implementation": f"{_HCM}/faibn/index.html",
    "implementing benefits": f"{_HCM}/faibn/index.html",
    "benefit programs": f"{_HCM}/faibn/index.html",
    "life events": f"{_HCM}/faibn/index.html",
    "open enrollment": f"{_HCM}/faibn/index.html",

    # ━━━ HCM — Absence Management ━━━
    "implementing absence management": f"{_HCM}/faiaa/index.html",
    "absence management": f"{_HCM}/faiaa/index.html",
    "absence types": f"{_HCM}/faiaa/index.html",
    "absence plans": f"{_HCM}/faiaa/index.html",
    "accrual": f"{_HCM}/faiaa/index.html",
    "accrual plans": f"{_HCM}/faiaa/index.html",

    # ━━━ HCM — Time & Labor ━━━
    "implementing time and labor": f"{_HCM}/faitl/index.html",
    "time and labor": f"{_HCM}/faitl/index.html",
    "time cards": f"{_HCM}/faitl/index.html",
    "time categories": f"{_HCM}/faitl/index.html",
    "time entry": f"{_HCM}/faitl/index.html",

    # ━━━ HCM — Learning ━━━
    "implementing learning": f"{_HCM}/failm/index.html",
    "learning management": f"{_HCM}/failm/index.html",
    "learning": f"{_HCM}/failm/index.html",
    "learning catalog": f"{_HCM}/failm/index.html",
    "required learning": f"{_HCM}/failm/index.html",
    "certifications": f"{_HCM}/failm/index.html",

    # ━━━ HCM — Workforce Management ━━━
    "workforce management": f"{_HCM}/faiwm/index.html",
    "workforce scheduling": f"{_HCM}/faiws/index.html",
    "implementing workforce scheduling": f"{_HCM}/faiws/index.html",

    # ━━━ HCM — Journeys ━━━
    "journeys": f"{_HCM}/faijh/index.html",
    "implementing journeys": f"{_HCM}/faijh/index.html",
    "journey tasks": f"{_HCM}/faijh/index.html",

    # ━━━ HCM — Help Desk ━━━
    "help desk": f"{_HCM}/faihd/index.html",
    "implementing help desk": f"{_HCM}/faihd/index.html",

    # ━━━ HCM — Health & Safety ━━━
    "workforce health and safety": f"{_HCM}/faiwh/index.html",
    "incidents": f"{_HCM}/faiwh/index.html",
    "safety incidents": f"{_HCM}/faiwh/index.html",

    # ━━━ HCM — Analytics & OTBI ━━━
    "administering analytics": f"{_HCM}/fahca/index.html",
    "otbi": f"{_HCM}/fahca/index.html",
    "otbi hcm": f"{_HCM}/fahca/index.html",
    "otbi subject areas": f"{_HCM}/faohb/index.html",
    "subject areas for otbi": f"{_HCM}/faohb/index.html",
    "bi publisher": f"{_HCM}/fahca/index.html",
    "bi publisher hcm": f"{_HCM}/fahca/index.html",
    "hcm analytics": f"{_HCM}/fahca/index.html",
    "transactional business intelligence": f"{_HCM}/fahca/index.html",
    "workforce analytics": f"{_HCM}/fahca/index.html",

    # ━━━ HCM — Security ━━━
    "securing hcm": f"{_HCM}/ochus/index.html",
    "hcm security": f"{_HCM}/ochus/index.html",
    "data roles": f"{_HCM}/oawpm/index.html",
    "job roles": f"{_HCM}/oawpm/index.html",
    "duty roles": f"{_HCM}/oawpm/index.html",
    "security profiles": f"{_HCM}/oawpm/index.html",
    "security reference hcm": f"{_HCM}/oawpm/index.html",

    # ━━━ HCM — Data Loading ━━━
    "hcm data loader": f"{_HCM}/fahdl/index.html",
    "hcm spreadsheet data loader": f"{_HCM}/fahdl/index.html",
    "hcm extract": f"{_HCM}/fahex/index.html",
    "hcm extracts": f"{_HCM}/fahex/index.html",

    # ━━━ HCM — Autocomplete Rules ━━━
    "autocomplete rules": f"{_HCM}/faiau/index.html",
    "configuring hcm": f"{_HCM}/faiau/index.html",

    # ━━━ HCM — AI Agent Studio ━━━
    "ai agent studio": f"{_HCM}/fairs/index.html",
    "ai agent": f"{_HCM}/fairs/index.html",
    "career coach": f"{_HCM}/fairs/index.html",
    "agent team": f"{_HCM}/fairs/index.html",
    "agent configuration": f"{_HCM}/fairs/index.html",
    "intelligent advisor": f"{_HCM}/fairs/index.html",

    # ━━━ HCM — Digital Assistant ━━━
    "digital assistant": f"{_HCM}/faoda/index.html",
    "oracle digital assistant": f"{_HCM}/faoda/index.html",
    "chatbot": f"{_HCM}/faoda/index.html",

    # ━━━ HCM — Common Features ━━━
    "using common features hcm": f"{_HCM}/faucf/index.html",
    "using global hr": f"{_HCM}/fawhr/index.html",

    # ━━━ HCM — Payroll by Country ━━━
    "payroll canada": f"{_HCM}/fapcd/index.html",
    "payroll usa": f"{_HCM}/fapus/index.html",
    "payroll uk": f"{_HCM}/fapuk/index.html",
    "canadian payroll": f"{_HCM}/fapcd/index.html",
    "us payroll": f"{_HCM}/fapus/index.html",

    # ━━━ ERP — General Ledger ━━━
    "implementing general ledger": f"{_ERP}/faigl/index.html",
    "general ledger": f"{_ERP}/faigl/index.html",
    "gl": f"{_ERP}/faigl/index.html",
    "journal entries": f"{_ERP}/faigl/index.html",
    "chart of accounts": f"{_ERP}/faigl/index.html",
    "allocations": f"{_ERP}/faigl/index.html",
    "period close gl": f"{_ERP}/faigl/index.html",
    "financial reporting": f"{_ERP}/fcucs/index.html",
    "smartview": f"{_ERP}/fcucs/index.html",

    # ━━━ ERP — Payables ━━━
    "implementing payables": f"{_ERP}/faiap/index.html",
    "payables": f"{_ERP}/faiap/index.html",
    "ap": f"{_ERP}/faiap/index.html",
    "invoices": f"{_ERP}/faiap/index.html",
    "invoice approval": f"{_ERP}/faiap/index.html",
    "payments": f"{_ERP}/faiap/index.html",
    "suppliers": f"{_ERP}/faiap/index.html",

    # ━━━ ERP — Receivables ━━━
    "implementing receivables": f"{_ERP}/faiar/index.html",
    "receivables": f"{_ERP}/faiar/index.html",
    "ar": f"{_ERP}/faiar/index.html",
    "customer invoices": f"{_ERP}/faiar/index.html",
    "receipts": f"{_ERP}/faiar/index.html",
    "collections": f"{_ERP}/faiar/index.html",
    "revenue recognition": f"{_ERP}/faiar/index.html",

    # ━━━ ERP — Assets ━━━
    "implementing assets": f"{_ERP}/faifa/index.html",
    "fixed assets": f"{_ERP}/faifa/index.html",
    "fa": f"{_ERP}/faifa/index.html",
    "asset additions": f"{_ERP}/faifa/index.html",
    "depreciation": f"{_ERP}/faifa/index.html",
    "asset retirement": f"{_ERP}/faifa/index.html",
    "group assets": f"{_ERP}/faifa/index.html",

    # ━━━ ERP — Cash Management ━━━
    "cash management": f"{_ERP}/faicm/index.html",
    "bank statements": f"{_ERP}/faicm/index.html",
    "bank reconciliation": f"{_ERP}/faicm/index.html",
    "cash positioning": f"{_ERP}/faicm/index.html",
    "cash forecasting": f"{_ERP}/faicm/index.html",

    # ━━━ ERP — Expenses ━━━
    "expenses": f"{_ERP}/faiex/index.html",
    "expense reports": f"{_ERP}/faiex/index.html",
    "expense policies": f"{_ERP}/faiex/index.html",
    "per diem": f"{_ERP}/faiex/index.html",
    "travel": f"{_ERP}/faiex/index.html",

    # ━━━ ERP — Tax ━━━
    "implementing tax": f"{_ERP}/faitx/index.html",
    "tax": f"{_ERP}/faitx/index.html",
    "tax rules": f"{_ERP}/faitx/index.html",
    "tax regimes": f"{_ERP}/faitx/index.html",
    "withholding tax": f"{_ERP}/faitx/index.html",
    "tax reporting": f"{_ERP}/faitx/index.html",

    # ━━━ ERP — Subledger Accounting ━━━
    "implementing subledger accounting": f"{_ERP}/faisl/index.html",
    "subledger accounting": f"{_ERP}/faisl/index.html",
    "accounting methods": f"{_ERP}/faisl/index.html",
    "accounting rules": f"{_ERP}/faisl/index.html",
    "sla": f"{_ERP}/faisl/index.html",

    # ━━━ ERP — Intercompany ━━━
    "intercompany": f"{_ERP}/faiic/index.html",
    "intercompany transactions": f"{_ERP}/faiic/index.html",
    "intercompany balancing": f"{_ERP}/faiic/index.html",

    # ━━━ ERP — Lease Accounting ━━━
    "lease accounting": f"{_ERP}/faila/index.html",
    "leases": f"{_ERP}/faila/index.html",
    "ifrs 16": f"{_ERP}/faila/index.html",
    "asc 842": f"{_ERP}/faila/index.html",

    # ━━━ ERP — Joint Venture ━━━
    "joint venture": f"{_ERP}/faijv/index.html",
    "joint venture management": f"{_ERP}/faijv/index.html",

    # ━━━ ERP — Common ━━━
    "implementing common features financials": f"{_ERP}/faicf/index.html",
    "financials common": f"{_ERP}/faicf/index.html",

    # ━━━ EPM — Planning ━━━
    "planning": f"{_EPM}/index.html",
    "enterprise planning": f"{_EPM}/index.html",
    "financial planning": f"{_EPM}/index.html",
    "workforce planning": f"{_EPM}/index.html",
    "capital planning": f"{_EPM}/index.html",
    "epm": f"{_EPM}/index.html",
    "enterprise performance management": f"{_EPM}/index.html",
    "epm overview": f"{_EPM}/index.html",

    # ━━━ EPM — Consolidation ━━━
    "financial consolidation": f"{_EPM}/index.html",
    "consolidation": f"{_EPM}/index.html",
    "eliminations": f"{_EPM}/index.html",

    # ━━━ EPM — Close ━━━
    "close manager": f"{_EPM}/index.html",
    "period close epm": f"{_EPM}/index.html",
    "close scheduling": f"{_EPM}/index.html",

    # ━━━ EPM — Account Reconciliation ━━━
    "account reconciliation": f"{_EPM}/index.html",
    "reconciliation compliance": f"{_EPM}/index.html",
    "transaction matching": f"{_EPM}/index.html",

    # ━━━ EPM — Profitability ━━━
    "profitability and cost management": f"{_EPM}/index.html",
    "cost allocation": f"{_EPM}/index.html",
    "profitability analysis": f"{_EPM}/index.html",

    # ━━━ EPM — Data Integration ━━━
    "data integration epm": f"{_EPM}/index.html",
    "data management epm": f"{_EPM}/index.html",
    "epm integration": f"{_EPM}/index.html",

    # ━━━ SCM — Inventory ━━━
    "inventory management": f"{_SCM}/faimm/index.html",
    "inventory": f"{_SCM}/faimm/index.html",
    "item organizations": f"{_SCM}/faimm/index.html",
    "on-hand quantities": f"{_SCM}/faimm/index.html",
    "inventory transactions": f"{_SCM}/faimm/index.html",
    "consignment": f"{_SCM}/faimm/index.html",

    # ━━━ SCM — Order Management ━━━
    "order management": f"{_SCM}/faiom/index.html",
    "sales orders": f"{_SCM}/faiom/index.html",
    "order fulfillment": f"{_SCM}/faiom/index.html",
    "pricing": f"{_SCM}/faiom/index.html",
    "returns": f"{_SCM}/faiom/index.html",
    "drop ship": f"{_SCM}/faiom/index.html",

    # ━━━ SCM — Manufacturing ━━━
    "manufacturing": f"{_SCM}/faimf/index.html",
    "work orders": f"{_SCM}/faimf/index.html",
    "work definitions": f"{_SCM}/faimf/index.html",
    "production scheduling": f"{_SCM}/faimf/index.html",
    "discrete manufacturing": f"{_SCM}/faimf/index.html",
    "process manufacturing": f"{_SCM}/faimf/index.html",

    # ━━━ SCM — Quality ━━━
    "quality management": f"{_SCM}/faiqm/index.html",
    "quality inspections": f"{_SCM}/faiqm/index.html",
    "quality plans": f"{_SCM}/faiqm/index.html",
    "nonconformance": f"{_SCM}/faiqm/index.html",

    # ━━━ SCM — Maintenance ━━━
    "maintenance management": f"{_SCM}/faimt/index.html",
    "asset maintenance": f"{_SCM}/faimt/index.html",

    # ━━━ SCM — Logistics ━━━
    "shipping": f"{_SCM}/faish/index.html",
    "receiving": f"{_SCM}/fairc/index.html",
    "transportation": f"{_SCM}/faitr/index.html",
    "warehouse management": f"{_SCM}/faiwm/index.html",
    "logistics": f"{_SCM}/faish/index.html",

    # ━━━ SCM — Overview ━━━
    "supply chain management": f"{_SCM}/index.html",
    "scm": f"{_SCM}/index.html",

    # ━━━ Procurement ━━━
    "procurement": f"{_PR}/index.html",
    "purchasing": f"{_PR}/faipu/index.html",
    "purchase orders": f"{_PR}/faipu/index.html",
    "self service procurement": f"{_PR}/faiss/index.html",
    "sourcing": f"{_PR}/faiso/index.html",
    "procurement contracts": f"{_PR}/faipc/index.html",
    "supplier portal": f"{_PR}/faisp/index.html",

    # ━━━ Projects ━━━
    "project management": f"{_PRJ}/index.html",
    "project financial management": f"{_PRJ}/faipf/index.html",
    "project resource management": f"{_PRJ}/faipr/index.html",
    "project costing": f"{_PRJ}/faipc/index.html",
    "project billing": f"{_PRJ}/faipb/index.html",
    "grants management": f"{_PRJ}/faigm/index.html",
    "project": f"{_PRJ}/index.html",

    # ━━━ CX — Sales ━━━
    "sales": f"{_CX}/sales/index.html",
    "cx sales": f"{_CX}/sales/index.html",
    "opportunities": f"{_CX}/sales/index.html",
    "leads": f"{_CX}/sales/index.html",
    "sales forecasting": f"{_CX}/sales/index.html",
    "territory management": f"{_CX}/sales/index.html",
    "sales quoting": f"{_CX}/sales/index.html",

    # ━━━ CX — Service ━━━
    "service": f"{_CX}/service/index.html",
    "cx service": f"{_CX}/service/index.html",
    "service requests": f"{_CX}/service/index.html",
    "knowledge management": f"{_CX}/service/index.html",
    "field service": f"{_CX}/service/index.html",
    "service entitlements": f"{_CX}/service/index.html",

    # ━━━ Cross-Module — Security & Access ━━━
    "security": f"{_COM}/faasc/index.html",
    "applications security": f"{_COM}/faasc/index.html",
    "function security": f"{_COM}/faasc/index.html",

    # ━━━ Cross-Module — Approvals ━━━
    "approvals": f"{_COM}/faiaw/index.html",
    "approval workflows": f"{_COM}/faiaw/index.html",
    "bpm": f"{_COM}/faiaw/index.html",
    "workflow": f"{_COM}/faiaw/index.html",
    "notifications": f"{_COM}/faiaw/index.html",

    # ━━━ Cross-Module — REST API ━━━
    "rest api": f"{_COM}/farcr/index.html",
    "rest apis": f"{_COM}/farcr/index.html",
    "api": f"{_COM}/farcr/index.html",
    "web services": f"{_COM}/farcr/index.html",

    # ━━━ Cross-Module — Flexfields & Lookups ━━━
    "flexfields": f"{_COM}/faiem/index.html",
    "descriptive flexfields": f"{_COM}/faiem/index.html",
    "key flexfields": f"{_COM}/faiem/index.html",
    "dff": f"{_COM}/faiem/index.html",
    "kff": f"{_COM}/faiem/index.html",
    "lookups": f"{_COM}/faiem/index.html",
    "value sets": f"{_COM}/faiem/index.html",
    "extensibility": f"{_COM}/faiem/index.html",

    # ━━━ Cross-Module — UI Customization ━━━
    "page composer": f"{_COM}/faipg/index.html",
    "sandboxes": f"{_COM}/faisb/index.html",
    "visual builder": f"{_COM}/faivb/index.html",
    "visual builder studio": f"{_COM}/faivb/index.html",
    "personalization": f"{_COM}/faipg/index.html",
    "infolets": f"{_COM}/faiem/index.html",

    # ━━━ Cross-Module — Other ━━━
    "attachments": f"{_COM}/faiem/index.html",
    "file import": f"{_COM}/faiem/index.html",
    "audit": f"{_COM}/faiau/index.html",
    "audit trail": f"{_COM}/faiau/index.html",
    "scheduled processes": f"{_COM}/faisp/index.html",
    "enterprise scheduler": f"{_COM}/faisp/index.html",
    "hcm common": f"{_COM}/index.html",
    "applications common": f"{_COM}/index.html",
}

# Known Oracle Fusion module index pages (fallback for broad queries)
FUSION_MODULE_PAGES: list[tuple[str, str]] = [
    ("HCM — Human Resources", f"{_HCM}/books.html"),
    ("ERP — Financials", f"{_ERP}/books.html"),
    ("EPM — Enterprise Performance Management", f"{_EPM}/index.html"),
    ("SCM — Supply Chain Management", f"{_SCM}/index.html"),
    ("Procurement", f"{_PR}/books.html"),
    ("Projects", f"{_PRJ}/index.html"),
    ("CX — Sales", f"{_CX}/sales/books.html"),
    ("CX — Service", f"{_CX}/service/books.html"),
    ("Applications Common", f"{_COM}/index.html"),
]


# ── Helpers ──────────────────────────────────────────────────

def _search_topic_index(query: str, limit: int = 5) -> list[tuple[str, str, str]]:
    """Search the keyword→URL index for matching topics. Case-insensitive."""
    q = query.lower().strip()
    matches: list[tuple[str, str, str]] = []

    # Exact match
    for keyword, url in TOPIC_INDEX.items():
        if q == keyword:
            matches.append((keyword, url, "exact"))

    # Partial match (query ⊂ keyword OR keyword ⊂ query)
    if not matches:
        for keyword, url in TOPIC_INDEX.items():
            if q in keyword or keyword in q:
                matches.append((keyword, url, "partial"))

    # Deduplicate by URL
    seen: set[str] = set()
    unique: list[tuple[str, str, str]] = []
    for kw, url, mtype in matches:
        if url not in seen:
            seen.add(url)
            unique.append((kw, url, mtype))

    return unique[:limit]


def _strip_jina_header(text: str) -> str:
    """Remove Jina Reader metadata header, returning clean markdown."""
    lines = text.split("\n")
    content_start = 0
    for i, line in enumerate(lines):
        if line.startswith("Markdown Content:"):
            content_start = i + 1
            break
        if line.startswith("#") and not line.startswith("## URL"):
            content_start = i
            break
    return "\n".join(lines[content_start:])


def _collapse_blanks(text: str) -> str:
    """Collapse runs of >2 blank lines to max 2."""
    cleaned: list[str] = []
    blank_count = 0
    for line in text.split("\n"):
        if line.strip() == "":
            blank_count += 1
            if blank_count <= 2:
                cleaned.append(line)
        else:
            blank_count = 0
            cleaned.append(line)
    return "\n".join(cleaned)


# ── Tools ────────────────────────────────────────────────────

@mcp.tool(
    name="search_oracle_docs",
    annotations={
        "title": "Search Oracle Fusion Documentation",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def search_oracle_docs(params: SearchInput) -> str:
    """Search Oracle Fusion Cloud documentation by topic.

    Covers ALL Fusion modules: HCM, ERP/Financials, EPM, SCM,
    Procurement, Projects, CX (Sales/Service), and Applications Common.

    Uses a keyword→URL index (200+ entries) for instant results.
    Use fetch_oracle_page() to read any returned URL in full markdown.

    Args:
        params: SearchInput with query string and max_results (1-10).

    Returns:
        Markdown-formatted list of matching documentation pages,
        module index links, and direct search URLs for Oracle Help Center.
    """
    logger.info("search_oracle_docs: query='%s', max_results=%d", params.query, params.max_results)
    index_matches = _search_topic_index(query=params.query, limit=params.max_results)

    google_url = (
        f"https://www.google.com/search?q=site%3Adocs.oracle.com%2Fen%2Fcloud%2Fsaas%2F"
        f"+{quote(params.query)}"
    )
    oracle_url = f"https://docs.oracle.com/search/?q={quote(params.query)}"

    lines: list[str] = [f"## Search: *{params.query}*\n"]

    if index_matches:
        logger.info("search_oracle_docs: found %d matches in topic index", len(index_matches))
        lines.append("### 📚 Matching Documentation Pages\n")
        for i, (keyword, url, match_type) in enumerate(index_matches, 1):
            tag = "🎯" if match_type == "exact" else "🔍"
            lines.append(f"**{i}. [{keyword.title()}]({url})** {tag}")
        lines.append("")
    else:
        logger.warning("search_oracle_docs: empty results (no matches found) for query '%s'", params.query)
        lines.append("### 🔍 No exact match in the topic index.\n")

    lines.append("### 📂 Oracle Fusion Module Indexes\n")
    for i, (name, url) in enumerate(FUSION_MODULE_PAGES, 1):
        lines.append(f"**{i}. [{name}]({url})**")
    lines.append("")
    lines.append("### 🔗 Search Oracle Directly\n")
    lines.append(f"- [Search Google (site:docs.oracle.com)]({google_url})")
    lines.append(f"- [Search Oracle Help Center]({oracle_url})")
    lines.append("")
    lines.append("> 💡 **Tip**: Use `fetch_oracle_page(url)` to read any page above in clean markdown.")

    return "\n".join(lines)


@mcp.tool(
    name="fetch_oracle_page",
    annotations={
        "title": "Fetch Oracle Documentation Page",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def fetch_oracle_page(params: FetchInput) -> str:
    """Fetch and return clean markdown from an Oracle documentation page.

    Handles Oracle's JavaScript-heavy pages using Jina Reader for
    server-side rendering. Returns clean, readable markdown.

    Args:
        params: FetchInput with the full URL (must be under docs.oracle.com).

    Returns:
        Clean markdown text truncated to ~15,000 characters.
    """
    url = params.url.strip()
    logger.info("fetch_oracle_page: called with URL: %s", url)

    if "docs.oracle.com" not in url:
        logger.warning("fetch_oracle_page: invalid URL domain requested: %s", url)
        return "Error: URL must be under docs.oracle.com. Please specify a valid Oracle documentation URL."
    if not url.startswith("http"):
        url = "https://" + url

    # Cache lookup
    cached_content = _page_cache.get(url)
    if cached_content is not None:
        logger.info("fetch_oracle_page: cache HIT for URL: %s", url)
        _cache_stats()
        return cached_content

    logger.info("fetch_oracle_page: cache MISS for URL: %s", url)

    try:
        resp = await _jina_get(url)
        resp_text = resp.text
    except httpx.TimeoutException as e:
        err_msg = f"Error: Request to Jina Reader timed out after 3 attempts. Try again or check the URL directly: {url}"
        logger.error("fetch_oracle_page: timeout fetching URL %s: %s", url, str(e))
        return err_msg
    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code
        if status_code == 429:
            err_msg = f"Error: Rate limit exceeded (HTTP 429) after 3 attempts. Jina Reader is currently rate-limiting requests. Please wait a minute and try again."
        else:
            err_msg = f"Error: HTTP {status_code} returned. The page may be inaccessible, deleted, or requires login. Verify the URL: {url}"
        logger.error("fetch_oracle_page: HTTP %d fetching URL %s: %s", status_code, url, str(e))
        return err_msg
    except httpx.NetworkError as e:
        err_msg = f"Error: Network connection failed after 3 attempts. Check your internet connection and verify if Jina Reader (https://r.jina.ai/) is reachable."
        logger.error("fetch_oracle_page: Network error fetching URL %s: %s", url, str(e))
        return err_msg
    except Exception as e:
        err_msg = f"Error: Unexpected network failure — {type(e).__name__}: {e}. Please ensure Jina Reader is available and try again."
        logger.error("fetch_oracle_page: unexpected failure fetching URL %s: %s", url, str(e))
        return err_msg

    text = _strip_jina_header(resp_text)
    result = _collapse_blanks(text)

    is_truncated = False
    if len(result) > MAX_PAGE_CHARS:
        result = result[:MAX_PAGE_CHARS] + "\n\n[... truncated — content exceeds 15K chars]"
        is_truncated = True

    if len(result.strip()) < 50:
        logger.warning(
            "fetch_oracle_page: empty or very short content extracted (%d chars) for URL: %s",
            len(result), url
        )
        return (
            f"Warning: Very little content extracted ({len(result)} chars). "
            "The page may be JavaScript-rendered, require login, or be inaccessible. "
            f"Check the URL directly: {url}"
        )

    # Cache successful result
    _page_cache.set(url, result)

    if is_truncated:
        logger.warning("fetch_oracle_page: truncated content fetched for URL %s (%d chars)", url, len(result))
    else:
        logger.info("fetch_oracle_page: successfully fetched URL %s (%d chars)", url, len(result))

    _cache_stats()
    return result


@mcp.tool(
    name="list_modules",
    annotations={
        "title": "List Oracle Fusion Modules",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def list_modules() -> str:
    """List all Oracle Fusion Cloud modules with their documentation home pages.

    Returns a formatted list of all available modules (HCM, ERP, EPM, SCM,
    Procurement, Projects, CX) with links to their books/index pages.

    Use this to discover what modules are available before searching.
    """
    logger.info("list_modules: called")
    lines: list[str] = ["## Oracle Fusion Cloud Modules\n"]
    for i, (name, url) in enumerate(FUSION_MODULE_PAGES, 1):
        lines.append(f"{i}. **[{name}]({url})**")
    lines.append("")
    lines.append(f"> 📚 **Total topic index**: {len(TOPIC_INDEX)} keywords mapped to documentation pages.")
    lines.append("> Use `search_oracle_docs(query)` to find specific topics within these modules.")
    return "\n".join(lines)


# ── Entrypoint ───────────────────────────────────────────────

def main() -> None:
    """Run the Oracle Fusion Docs MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
