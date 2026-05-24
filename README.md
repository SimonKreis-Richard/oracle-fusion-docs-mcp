# Oracle Fusion Docs MCP

> 🔍 **Instant Oracle Fusion documentation — inside your IDE.**
>
> HCM · ERP · EPM · SCM · Procurement · Projects · Risk Management
>
> *No API keys. No maintenance. Always up-to-date.*

---

## 🚀 Quick Start

### 1. Install

```bash
uvx oracle-fusion-docs-mcp
```

### 2. Configure your MCP client

Add to Claude Desktop, Continue, VS Code, or any MCP-compatible IDE:

```json
{
  "mcpServers": {
    "oracle-fusion-docs": {
      "command": "uvx",
      "args": ["oracle-fusion-docs-mcp"]
    }
  }
}
```

### 3. Use it

Ask in natural language:

> *"What are the subject areas for Recruiting in OTBI?"*
>
> *"How do I configure a fast formula for Canadian payroll?"*
>
> *"Explain the General Ledger implementation steps."*

---

## 🛠️ Tools

| Tool | Description |
|---|---|
| `search_oracle_docs(query)` | Finds documentation pages via topic index (40+ topics) + module indexes. Returns direct URLs. |
| `fetch_oracle_page(url)` | Fetches any Oracle docs page as clean markdown. Handles JavaScript rendering. |

---

## 🎯 Why This Exists

Oracle Fusion documentation spans 150+ guides across a dozen modules — HCM, ERP, EPM, SCM, and more. Consultants and developers waste time digging through PDFs that are outdated the moment they are downloaded.

This MCP server solves that: live access to the latest documentation, zero setup, always current.

---

## 📦 Architecture

```
┌──────────────┐     ┌───────────────────────┐     ┌──────────────────────┐
│  Your IDE    │────▶│  MCP Server           │────▶│  Jina Reader API     │
│  (any MCP)  │◀────│  (2 tools, 200 lines) │◀────│  (free, JS rendering)│
└──────────────┘     └───────────────────────┘     └──────────────────────┘
```

- **Search** uses a built-in keyword → URL index (40+ common Oracle Fusion topics)
- **Fetch** uses Jina Reader (`r.jina.ai`) — free, no API key, handles Oracle's JavaScript-heavy pages
- No vector database, no PDF scraping, no cron jobs

---

## 🔧 Development

```bash
git clone https://github.com/SimonKreis-Richard/oracle-fusion-docs-mcp.git
cd oracle-fusion-docs-mcp
pip install -e .
python server.py
```

---

## 📄 License

MIT © 2026 Simon Kreis-Richard — Montreal, Canada
