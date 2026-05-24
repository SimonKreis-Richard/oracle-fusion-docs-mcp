#!/usr/bin/env python3
"""
Oracle Fusion Docs MCP Server
─────────────────────────────
Universal access to Oracle Fusion Cloud documentation (HCM, ERP, EPM, SCM, CX).
No API keys required. No maintenance. Always up-to-date.
"""

from mcp.server.fastmcp import FastMCP
import requests
import re
from urllib.parse import quote

# ── Config ───────────────────────────────────────────────────
mcp = FastMCP("oracle-fusion-docs")

MAX_PAGE_CHARS = 15_000
JINA_READER_URL = "https://r.jina.ai/"

# ── Keyword → URL Index ──────────────────────────────────────
# Maps common Oracle Fusion topics to documentation URLs.
# Covers 40+ high-traffic topics across HCM, ERP, EPM.
# Jina Reader fetches the live page, so content is always current.

TOPIC_INDEX = {
    # HCM - Core
    "implementing global hr": "https://docs.oracle.com/en/cloud/saas/human-resources/faigh/index.html",
    "global hr implementation": "https://docs.oracle.com/en/cloud/saas/human-resources/faigh/index.html",
    "implementing absence management": "https://docs.oracle.com/en/cloud/saas/human-resources/faiaa/index.html",
    "absence management": "https://docs.oracle.com/en/cloud/saas/human-resources/faiaa/index.html",
    "implementing payroll": "https://docs.oracle.com/en/cloud/saas/human-resources/faipy/index.html",
    "payroll implementation": "https://docs.oracle.com/en/cloud/saas/human-resources/faipy/index.html",
    "fast formula": "https://docs.oracle.com/en/cloud/saas/human-resources/faihf/index.html",
    "fast formulas": "https://docs.oracle.com/en/cloud/saas/human-resources/faihf/index.html",
    "compensation": "https://docs.oracle.com/en/cloud/saas/human-resources/faicw/index.html",
    "compensation management": "https://docs.oracle.com/en/cloud/saas/human-resources/faicw/index.html",
    "benefits": "https://docs.oracle.com/en/cloud/saas/human-resources/faibn/index.html",
    "benefits implementation": "https://docs.oracle.com/en/cloud/saas/human-resources/faibn/index.html",
    "talent management": "https://docs.oracle.com/en/cloud/saas/human-resources/faits/index.html",
    "talent review": "https://docs.oracle.com/en/cloud/saas/human-resources/faits/index.html",
    "recruiting": "https://docs.oracle.com/en/cloud/saas/human-resources/fairs/index.html",
    "recruiting implementation": "https://docs.oracle.com/en/cloud/saas/human-resources/fairs/index.html",
    "learning": "https://docs.oracle.com/en/cloud/saas/human-resources/failm/index.html",
    "learning management": "https://docs.oracle.com/en/cloud/saas/human-resources/failm/index.html",
    "workforce management": "https://docs.oracle.com/en/cloud/saas/human-resources/faiwm/index.html",
    "time and labor": "https://docs.oracle.com/en/cloud/saas/human-resources/faitl/index.html",

    # HCM - Analytics & OTBI
    "administering analytics": "https://docs.oracle.com/en/cloud/saas/human-resources/fahca/index.html",
    "otbi hcm": "https://docs.oracle.com/en/cloud/saas/human-resources/fahca/index.html",
    "otbi subject areas": "https://docs.oracle.com/en/cloud/saas/human-resources/fahca/index.html",
    "bi publisher hcm": "https://docs.oracle.com/en/cloud/saas/human-resources/fahca/index.html",
    "hcm analytics": "https://docs.oracle.com/en/cloud/saas/human-resources/fahca/index.html",
    "transactional business intelligence hcm": "https://docs.oracle.com/en/cloud/saas/human-resources/fahca/index.html",

    # ERP - Financials
    "implementing general ledger": "https://docs.oracle.com/en/cloud/saas/financials/faigl/index.html",
    "general ledger": "https://docs.oracle.com/en/cloud/saas/financials/faigl/index.html",
    "implementing payables": "https://docs.oracle.com/en/cloud/saas/financials/faiap/index.html",
    "payables": "https://docs.oracle.com/en/cloud/saas/financials/faiap/index.html",
    "implementing receivables": "https://docs.oracle.com/en/cloud/saas/financials/faiar/index.html",
    "receivables": "https://docs.oracle.com/en/cloud/saas/financials/faiar/index.html",
    "fixed assets": "https://docs.oracle.com/en/cloud/saas/financials/faifa/index.html",
    "cash management": "https://docs.oracle.com/en/cloud/saas/financials/faicm/index.html",
    "expenses": "https://docs.oracle.com/en/cloud/saas/financials/faiex/index.html",
    "financial reporting": "https://docs.oracle.com/en/cloud/saas/financials/fcucs/index.html",

    # EPM
    "enterprise performance management": "https://docs.oracle.com/en/cloud/saas/enterprise-performance-management-common/index.html",
    "epm overview": "https://docs.oracle.com/en/cloud/saas/enterprise-performance-management-common/index.html",
    "financial consolidation": "https://docs.oracle.com/en/cloud/saas/enterprise-performance-management-common/index.html",
    "planning epm": "https://docs.oracle.com/en/cloud/saas/enterprise-performance-management-common/index.html",
    "epm implementation": "https://docs.oracle.com/en/cloud/saas/enterprise-performance-management-common/index.html",

    # SCM
    "supply chain management": "https://docs.oracle.com/en/cloud/saas/supply-chain-management/index.html",
    "inventory management": "https://docs.oracle.com/en/cloud/saas/supply-chain-management/faimm/index.html",
    "procurement": "https://docs.oracle.com/en/cloud/saas/procurement/index.html",
    "purchasing": "https://docs.oracle.com/en/cloud/saas/procurement/faipu/index.html",
    "order management": "https://docs.oracle.com/en/cloud/saas/supply-chain-management/faiom/index.html",

    # Cross-module
    "security": "https://docs.oracle.com/en/cloud/saas/applications-common/faasc/index.html",
    "approvals": "https://docs.oracle.com/en/cloud/saas/applications-common/faiaw/index.html",
    "hcm data loader": "https://docs.oracle.com/en/cloud/saas/human-resources/faihd/index.html",
    "hcm extract": "https://docs.oracle.com/en/cloud/saas/human-resources/faiex/index.html",
    "rest api": "https://docs.oracle.com/en/cloud/saas/applications-common/farcr/index.html",
}

# Known Oracle Fusion module index pages (fallback for broad queries)
FUSION_MODULE_PAGES = [
    ("HCM Documentation Home", "https://docs.oracle.com/en/cloud/saas/human-resources/index.html"),
    ("ERP / Financials Documentation Home", "https://docs.oracle.com/en/cloud/saas/financials/26a/books.html"),
    ("EPM Documentation Home", "https://docs.oracle.com/en/cloud/saas/enterprise-performance-management-common/index.html"),
    ("SCM Documentation Home", "https://docs.oracle.com/en/cloud/saas/supply-chain-management/index.html"),
    ("Procurement Documentation Home", "https://docs.oracle.com/en/cloud/saas/procurement/index.html"),
    ("HCM Implementation Guides", "https://docs.oracle.com/en/cloud/saas/human-resources/books.html"),
    ("ERP Implementation Guides", "https://docs.oracle.com/en/cloud/saas/financials/26a/books.html"),
]


def search_topic_index(query: str) -> list:
    """Search the keyword→URL index for matching topics. Case-insensitive."""
    query_lower = query.lower().strip()
    matches = []
    
    # Direct match
    for keyword, url in TOPIC_INDEX.items():
        if query_lower == keyword:
            matches.append((keyword, url, "exact"))
    
    # Contains match
    if not matches:
        for keyword, url in TOPIC_INDEX.items():
            if query_lower in keyword or keyword in query_lower:
                matches.append((keyword, url, "partial"))
    
    # Deduplicate URLs
    seen_urls = set()
    unique = []
    for kw, url, match_type in matches:
        if url not in seen_urls:
            seen_urls.add(url)
            unique.append((kw, url, match_type))
    
    return unique[:5]


# ── Tools ────────────────────────────────────────────────────

@mcp.tool()
def search_oracle_docs(query: str, max_results: int = 10) -> str:
    """
    Search Oracle Fusion Cloud documentation by topic.
    
    Covers ALL Fusion modules: HCM, ERP/Financials, EPM, SCM, 
    Procurement, Projects, Risk Management, and more.
    
    Uses a topic→URL index for instant results, plus live search
    for queries that match known documentation patterns.
    
    Args:
        query: Search query in natural language. Examples:
               "OTBI subject areas", "payroll fast formula",
               "general ledger implementation", "absence management"
        max_results: Number of results (1-10, default 10)
    
    Returns:
        Formatted markdown with matching topics and URLs.
    """
    max_results = min(max(1, max_results), 10)

    # 1. Search the topic index
    index_matches = search_topic_index(query)

    # 2. Generate Oracle site search URL (useful for the LLM client)
    google_search_url = f"https://www.google.com/search?q=site%3Adocs.oracle.com%2Fen%2Fcloud%2Fsaas%2F+{quote(query)}"
    oracle_search_url = f"https://docs.oracle.com/search/?q={quote(query)}"

    lines = [f"## Search: *{query}*\n"]

    if index_matches:
        lines.append("### 📚 Matching Documentation Pages\n")
        for i, (keyword, url, match_type) in enumerate(index_matches, 1):
            tag = "🎯" if match_type == "exact" else "🔍"
            lines.append(f"**{i}. [{keyword.title()}]({url})** {tag}")
        lines.append("")
    else:
        lines.append("### 🔍 No exact match in the topic index.\n")

    # 3. Add module index pages for broad exploration
    lines.append("### 📂 Oracle Fusion Module Indexes\n")
    for i, (name, url) in enumerate(FUSION_MODULE_PAGES[:5], 1):
        lines.append(f"**{i}. [{name}]({url})**")

    lines.append("")
    lines.append("### 🔗 Search Oracle Directly\n")
    lines.append(f"- [Search Google (site:docs.oracle.com)]({google_search_url})")
    lines.append(f"- [Search Oracle Help Center]({oracle_search_url})")
    lines.append("")
    lines.append("> 💡 **Tip**: Use `fetch_oracle_page(url)` to read any page above in clean markdown.")

    return "\n".join(lines)


@mcp.tool()
def fetch_oracle_page(url: str) -> str:
    """
    Fetch and return clean markdown from an Oracle documentation page.
    
    Handles JavaScript-heavy Oracle pages using server-side rendering.
    Use after search_oracle_docs to read a full page.
    
    Args:
        url: Full URL of the Oracle documentation page.
             Must be under docs.oracle.com
    
    Returns:
        Clean markdown text (max ~15,000 chars).
    """
    if "docs.oracle.com" not in url:
        return "Error: URL must be under docs.oracle.com"

    if not url.startswith("http"):
        url = "https://" + url

    try:
        resp = requests.get(
            JINA_READER_URL + url,
            headers={
                "Accept": "text/markdown",
                "User-Agent": "OracleDocsMCP/1.0",
            },
            timeout=25,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        return f"Error fetching page: {e}"

    text = resp.text

    # Strip Jina Reader header
    lines = text.split("\n")
    content_start = 0
    for i, line in enumerate(lines):
        if line.startswith("Markdown Content:"):
            content_start = i + 1
            break
        if line.startswith("#") and not line.startswith("## URL"):
            content_start = i
            break

    content = "\n".join(lines[content_start:])

    # Remove excessive blank lines (>2 consecutive)
    cleaned = []
    blank_count = 0
    for line in content.split("\n"):
        if line.strip() == "":
            blank_count += 1
            if blank_count <= 2:
                cleaned.append(line)
        else:
            blank_count = 0
            cleaned.append(line)

    result = "\n".join(cleaned)

    if len(result) > MAX_PAGE_CHARS:
        result = result[:MAX_PAGE_CHARS] + "\n\n[... truncated]"

    if len(result.strip()) < 50:
        return f"Warning: Very little content extracted ({len(result)} chars). The page may be inaccessible."

    return result


# ── Entrypoint ───────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="stdio")
