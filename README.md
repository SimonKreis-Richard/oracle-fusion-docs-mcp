# Oracle Fusion Docs MCP

> 🔍 **Instant Oracle Fusion documentation — inside your AI agent or IDE.**
>
> HCM · ERP · EPM · SCM · Procurement · Projects · CX (Sales & Service)
>
> *No API keys. No maintenance. Always up-to-date.*

---

## 🚀 Quick Start

### Install & Run

```bash
npx oracle-fusion-docs-mcp
```

### Configure Your MCP Client

Add to Claude Desktop, Cursor, VS Code, or any MCP-compatible client:

```json
{
  "mcpServers": {
    "oracle-fusion-docs": {
      "command": "npx",
      "args": ["-y", "oracle-fusion-docs-mcp"]
    }
  }
}
```

### Use It

Ask in natural language:

> *"What are the subject areas for Recruiting in OTBI?"*
>
> *"How do I configure a fast formula for Canadian payroll?"*
>
> *"Explain the General Ledger implementation steps."*
>
> *"What's new in AI Agent Studio for career sites?"*

---

## 🛠️ Tools

| Tool | Description |
|---|---|
| `search_oracle_docs(query)` | Search 300+ topics across all Fusion modules. Returns matching doc pages, module indexes, and Oracle Help Center search links. |
| `fetch_oracle_page(url)` | Fetch any `docs.oracle.com` page as clean markdown. Handles JavaScript rendering via Jina Reader. Max ~15K chars. |
| `list_modules()` | List all available Oracle Fusion modules (HCM, ERP, EPM, SCM, Procurement, Projects, CX) with documentation home links. |

---

## 📚 Coverage

**300+ indexed topics** across all major Oracle Fusion Cloud modules:

| Module | Examples |
|---|---|
| **HCM** | Recruiting, Payroll, Absence, Benefits, Compensation, Talent, Learning, Journeys, Time & Labor, OTBI, Security, AI Agent Studio |
| **ERP/Financials** | General Ledger, Payables, Receivables, Assets, Cash Management, Expenses, Tax, Subledger Accounting, Intercompany, Lease Accounting |
| **EPM** | Planning, Consolidation, Close Manager, Account Reconciliation, Profitability, Data Integration |
| **SCM** | Inventory, Order Management, Manufacturing, Quality, Maintenance, Logistics |
| **Procurement** | Purchasing, Sourcing, Supplier Portal, Procurement Contracts |
| **Projects** | Project Management, Project Financials, Resource Management, Grants |
| **CX** | Sales (Opportunities, Leads, Forecasting), Service (Requests, Knowledge, Field Service) |
| **Cross-Module** | Security, Approvals, REST API, Flexfields, Page Composer, Sandboxes, Visual Builder |

---

## 🎯 Why This Exists

Oracle Fusion documentation spans **220+ guides** across a dozen product families. Consultants, developers, and AI agents waste hours digging through PDFs that are outdated the moment they're downloaded.

This MCP server solves that:

- **Live access** — fetches from `docs.oracle.com` via Jina Reader, always current
- **Zero maintenance** — no PDF downloads, no vector databases, no cron jobs
- **Universal** — covers ALL Fusion modules, not just one product area
- **Free** — no API keys required (Jina Reader free tier)

---

## 📦 Architecture

```
┌──────────────────┐     ┌───────────────────────┐     ┌──────────────────────┐
│  AI Agent / IDE  │────▶│  MCP Server           │────▶│  Jina Reader API     │
│  (any MCP client)│◀────│  (3 tools, cached)    │◀────│  (free, retry logic) │
└──────────────────┘     └───────────────────────┘     └──────────────────────┘
```

- **Search** — built-in keyword → URL index (300+ entries), case-insensitive matching.
- **Fetch** — fetches clean markdown via Jina Reader, featuring:
  - **Automatic Retries**: Exponential backoff (2s → 4s, up to 3 attempts) on rate limits (HTTP 429), timeouts, and network issues.
  - **Two-Tier Caching**: In-memory LRU (1-hour TTL, 50 entries) backed by a persistent disk cache under `~/.cache/oracle-fusion-docs` (24-hour TTL, 200 entries) — repeated fetches stay instant across sessions.
  - **Structured Logging**: Diagnostics, tool requests, cache stats, and retries are logged to stderr (captured by the MCP host).
- **Modules** — direct links to all product family documentation home pages.

---

## 🔧 Development

```bash
git clone https://github.com/SimonKreis-Richard/oracle-fusion-docs-mcp.git
cd oracle-fusion-docs-mcp
npm install
npm run build
npm start
```

### Testing with MCP Inspector

```bash
npm run build
npx @modelcontextprotocol/inspector node dist/index.js
```

---

## 🏗️ Tech Stack

- **TypeScript** (ES2022, NodeNext modules)
- **Node.js 18+** with native `fetch`
- **@modelcontextprotocol/sdk** — official MCP server SDK
- **Zod** — input validation
- **Jina Reader** — server-side rendering of Oracle docs

---

## 📄 License

MIT © 2026 Simon Kreis-Richard — Montreal, Canada
