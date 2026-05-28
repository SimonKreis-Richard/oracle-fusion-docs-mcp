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
uvx oracle-fusion-docs-mcp
```

### Configure Your MCP Client

Add to Claude Desktop, Cursor, VS Code, Hermes Agent, or any MCP-compatible client:

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
│  (any MCP client)│◀────│  (3 tools, async)     │◀────│  (free, JS rendering)│
└──────────────────┘     └───────────────────────┘     └──────────────────────┘
```

- **Search** — built-in keyword → URL index (300+ entries), case-insensitive matching
- **Fetch** — Jina Reader (`r.jina.ai`) renders Oracle's JavaScript-heavy pages into clean markdown
- **Modules** — direct links to all product family documentation home pages

---

## 🔧 Development

```bash
git clone https://github.com/SimonKreis-Richard/oracle-fusion-docs-mcp.git
cd oracle-fusion-docs-mcp
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e .
python server.py
```

### Testing with MCP Inspector

```bash
npx @modelcontextprotocol/inspector python server.py
```

---

## 🏗️ Tech Stack

- **Python 3.10+** with `async`/`await`
- **FastMCP** — high-level MCP server framework
- **httpx** — async HTTP client
- **Pydantic** — input validation
- **Jina Reader** — server-side rendering of Oracle docs

---

## 📄 License

MIT © 2026 Simon Kreis-Richard — Montreal, Canada
