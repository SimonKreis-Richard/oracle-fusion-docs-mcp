#!/usr/bin/env node
/**
 * Oracle Fusion Docs MCP Server (TypeScript)
 * ──────────────────────────────────────────
 * Universal access to Oracle Fusion Cloud documentation (HCM, ERP, EPM, SCM, CX, Projects).
 * No API keys required. No maintenance. Always up-to-date.
 *
 * Uses Jina Reader (https://r.jina.ai/) for server-side rendering of Oracle's
 * JavaScript-heavy documentation pages into clean markdown.
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { CallToolRequestSchema, ListToolsRequestSchema } from "@modelcontextprotocol/sdk/types.js";
import { z } from "zod";
import * as fs from "fs";
import * as path from "path";
import * as os from "os";
import * as crypto from "crypto";

// ── Config ───────────────────────────────────────────────────

const MAX_PAGE_CHARS = 15000;
const JINA_READER_URL = "https://r.jina.ai/";
const REQUEST_TIMEOUT = 25000; // 25.0 seconds
const USER_AGENT = "OracleDocsMCP/3.0";

// ── Topic Index Mappings ─────────────────────────────────────

const _HCM = "https://docs.oracle.com/en/cloud/saas/human-resources";
const _ERP = "https://docs.oracle.com/en/cloud/saas/financials";
const _EPM = "https://docs.oracle.com/en/cloud/saas/enterprise-performance-management-common";
const _SCM = "https://docs.oracle.com/en/cloud/saas/supply-chain-management";
const _PR  = "https://docs.oracle.com/en/cloud/saas/procurement";
const _PRJ = "https://docs.oracle.com/en/cloud/saas/projects";
const _CX  = "https://docs.oracle.com/en/cloud/saas";
const _COM = "https://docs.oracle.com/en/cloud/saas/applications-common";

const TOPIC_INDEX: Record<string, string> = {
  // ━━━ HCM — Core HR & Workforce ━━━
  "implementing global hr": `${_HCM}/faigh/index.html`,
  "global hr implementation": `${_HCM}/faigh/index.html`,
  "workforce structures": `${_HCM}/faigh/index.html`,
  "person management": `${_HCM}/faigh/index.html`,
  "employment information": `${_HCM}/faigh/index.html`,
  "document records": `${_HCM}/faigh/index.html`,
  "checklists": `${_HCM}/faigh/index.html`,
  "workforce lifecycle": `${_HCM}/faigh/index.html`,
  "work directory": `${_HCM}/faigh/index.html`,
  "line manager": `${_HCM}/faigh/index.html`,

  // ━━━ HCM — Recruiting ━━━
  "recruiting": `${_HCM}/fairs/index.html`,
  "recruiting implementation": `${_HCM}/fairs/index.html`,
  "implementing recruiting": `${_HCM}/fairs/index.html`,
  "candidate experience": `${_HCM}/fairs/index.html`,
  "career sites": `${_HCM}/fairs/index.html`,
  "career site": `${_HCM}/fairs/index.html`,
  "job requisitions": `${_HCM}/fairs/index.html`,
  "offer management": `${_HCM}/fairs/index.html`,
  "recruiting agency": `${_HCM}/fairs/index.html`,
  "recruiting analytics": `${_HCM}/fairs/index.html`,

  // ━━━ HCM — Talent ━━━
  "talent management": `${_HCM}/faits/index.html`,
  "talent review": `${_HCM}/faits/index.html`,
  "succession planning": `${_HCM}/faits/index.html`,
  "talent profiles": `${_HCM}/faits/index.html`,
  "talent pools": `${_HCM}/faits/index.html`,
  "career development": `${_HCM}/faits/index.html`,
  "performance management": `${_HCM}/faits/index.html`,
  "goal management": `${_HCM}/faits/index.html`,
  "goals": `${_HCM}/faits/index.html`,

  // ━━━ HCM — Payroll ━━━
  "implementing payroll": `${_HCM}/faipy/index.html`,
  "payroll implementation": `${_HCM}/faipy/index.html`,
  "payroll": `${_HCM}/faipy/index.html`,
  "element entries": `${_HCM}/faipy/index.html`,
  "balance definitions": `${_HCM}/faipy/index.html`,
  "payroll flow": `${_HCM}/faipy/index.html`,
  "payroll costing": `${_HCM}/faipy/index.html`,
  "payroll batch loader": `${_HCM}/faipy/index.html`,

  // ━━━ HCM — Fast Formulas ━━━
  "fast formula": `${_HCM}/faihf/index.html`,
  "fast formulas": `${_HCM}/faihf/index.html`,
  "administering fast formulas": `${_HCM}/oapff/index.html`,

  // ━━━ HCM — Compensation ━━━
  "compensation": `${_HCM}/faicw/index.html`,
  "compensation management": `${_HCM}/faicw/index.html`,
  "salary basis": `${_HCM}/faicw/index.html`,
  "grade rates": `${_HCM}/faicw/index.html`,
  "variable allocation": `${_HCM}/faicw/index.html`,
  "total compensation": `${_HCM}/faicw/index.html`,
  "implementing compensation": `${_HCM}/faicw/index.html`,

  // ━━━ HCM — Benefits ━━━
  "benefits": `${_HCM}/faibn/index.html`,
  "benefits implementation": `${_HCM}/faibn/index.html`,
  "implementing benefits": `${_HCM}/faibn/index.html`,
  "benefit programs": `${_HCM}/faibn/index.html`,
  "life events": `${_HCM}/faibn/index.html`,
  "open enrollment": `${_HCM}/faibn/index.html`,

  // ━━━ HCM — Absence Management ━━━
  "implementing absence management": `${_HCM}/faiaa/index.html`,
  "absence management": `${_HCM}/faiaa/index.html`,
  "absence types": `${_HCM}/faiaa/index.html`,
  "absence plans": `${_HCM}/faiaa/index.html`,
  "accrual": `${_HCM}/faiaa/index.html`,
  "accrual plans": `${_HCM}/faiaa/index.html`,

  // ━━━ HCM — Time & Labor ━━━
  "implementing time and labor": `${_HCM}/faitl/index.html`,
  "time and labor": `${_HCM}/faitl/index.html`,
  "time cards": `${_HCM}/faitl/index.html`,
  "time categories": `${_HCM}/faitl/index.html`,
  "time entry": `${_HCM}/faitl/index.html`,

  // ━━━ HCM — Learning ━━━
  "implementing learning": `${_HCM}/failm/index.html`,
  "learning management": `${_HCM}/failm/index.html`,
  "learning": `${_HCM}/failm/index.html`,
  "learning catalog": `${_HCM}/failm/index.html`,
  "required learning": `${_HCM}/failm/index.html`,
  "certifications": `${_HCM}/failm/index.html`,

  // ━━━ HCM — Workforce Management ━━━
  "workforce management": `${_HCM}/faiwm/index.html`,
  "workforce scheduling": `${_HCM}/faiws/index.html`,
  "implementing workforce scheduling": `${_HCM}/faiws/index.html`,

  // ━━━ HCM — Journeys ━━━
  "journeys": `${_HCM}/faijh/index.html`,
  "implementing journeys": `${_HCM}/faijh/index.html`,
  "journey tasks": `${_HCM}/faijh/index.html`,

  // ━━━ HCM — Help Desk ━━━
  "help desk": `${_HCM}/faihd/index.html`,
  "implementing help desk": `${_HCM}/faihd/index.html`,

  // ━━━ HCM — Health & Safety ━━━
  "workforce health and safety": `${_HCM}/faiwh/index.html`,
  "incidents": `${_HCM}/faiwh/index.html`,
  "safety incidents": `${_HCM}/faiwh/index.html`,

  // ━━━ HCM — Analytics & OTBI ━━━
  "administering analytics": `${_HCM}/fahca/index.html`,
  "otbi": `${_HCM}/fahca/index.html`,
  "otbi hcm": `${_HCM}/fahca/index.html`,
  "otbi subject areas": `${_HCM}/faohb/index.html`,
  "subject areas for otbi": `${_HCM}/faohb/index.html`,
  "bi publisher": `${_HCM}/fahca/index.html`,
  "bi publisher hcm": `${_HCM}/fahca/index.html`,
  "hcm analytics": `${_HCM}/fahca/index.html`,
  "transactional business intelligence": `${_HCM}/fahca/index.html`,
  "workforce analytics": `${_HCM}/fahca/index.html`,

  // ━━━ HCM — Security ━━━
  "securing hcm": `${_HCM}/ochus/index.html`,
  "hcm security": `${_HCM}/ochus/index.html`,
  "data roles": `${_HCM}/oawpm/index.html`,
  "job roles": `${_HCM}/oawpm/index.html`,
  "duty roles": `${_HCM}/oawpm/index.html`,
  "security profiles": `${_HCM}/oawpm/index.html`,
  "security reference hcm": `${_HCM}/oawpm/index.html`,

  // ━━━ HCM — Data Loading ━━━
  "hcm data loader": `${_HCM}/fahdl/index.html`,
  "hcm spreadsheet data loader": `${_HCM}/fahdl/index.html`,
  "hcm extract": `${_HCM}/fahex/index.html`,
  "hcm extracts": `${_HCM}/fahex/index.html`,

  // ━━━ HCM — Autocomplete Rules ━━━
  "autocomplete rules": `${_HCM}/faiau/index.html`,
  "configuring hcm": `${_HCM}/faiau/index.html`,

  // ━━━ HCM — AI Agent Studio ━━━
  "ai agent studio": `${_HCM}/fairs/index.html`,
  "ai agent": `${_HCM}/fairs/index.html`,
  "career coach": `${_HCM}/fairs/index.html`,
  "agent team": `${_HCM}/fairs/index.html`,
  "agent configuration": `${_HCM}/fairs/index.html`,
  "intelligent advisor": `${_HCM}/fairs/index.html`,

  // ━━━ HCM — Digital Assistant ━━━
  "digital assistant": `${_HCM}/faoda/index.html`,
  "oracle digital assistant": `${_HCM}/faoda/index.html`,
  "chatbot": `${_HCM}/faoda/index.html`,

  // ━━━ HCM — Common Features ━━━
  "using common features hcm": `${_HCM}/faucf/index.html`,
  "using global hr": `${_HCM}/fawhr/index.html`,

  // ━━━ HCM — Payroll by Country ━━━
  "payroll canada": `${_HCM}/fapcd/index.html`,
  "payroll usa": `${_HCM}/fapus/index.html`,
  "payroll uk": `${_HCM}/fapuk/index.html`,
  "canadian payroll": `${_HCM}/fapcd/index.html`,
  "us payroll": `${_HCM}/fapus/index.html`,

  // ━━━ ERP — General Ledger ━━━
  "implementing general ledger": `${_ERP}/faigl/index.html`,
  "general ledger": `${_ERP}/faigl/index.html`,
  "gl": `${_ERP}/faigl/index.html`,
  "journal entries": `${_ERP}/faigl/index.html`,
  "chart of accounts": `${_ERP}/faigl/index.html`,
  "allocations": `${_ERP}/faigl/index.html`,
  "period close gl": `${_ERP}/faigl/index.html`,
  "financial reporting": `${_ERP}/fcucs/index.html`,
  "smartview": `${_ERP}/fcucs/index.html`,

  // ━━━ ERP — Payables ━━━
  "implementing payables": `${_ERP}/faiap/index.html`,
  "payables": `${_ERP}/faiap/index.html`,
  "ap": `${_ERP}/faiap/index.html`,
  "invoices": `${_ERP}/faiap/index.html`,
  "invoice approval": `${_ERP}/faiap/index.html`,
  "payments": `${_ERP}/faiap/index.html`,
  "suppliers": `${_ERP}/faiap/index.html`,

  // ━━━ ERP — Receivables ━━━
  "implementing receivables": `${_ERP}/faiar/index.html`,
  "receivables": `${_ERP}/faiar/index.html`,
  "ar": `${_ERP}/faiar/index.html`,
  "customer invoices": `${_ERP}/faiar/index.html`,
  "receipts": `${_ERP}/faiar/index.html`,
  "collections": `${_ERP}/faiar/index.html`,
  "revenue recognition": `${_ERP}/faiar/index.html`,

  // ━━━ ERP — Assets ━━━
  "implementing assets": `${_ERP}/faifa/index.html`,
  "fixed assets": `${_ERP}/faifa/index.html`,
  "fa": `${_ERP}/faifa/index.html`,
  "asset additions": `${_ERP}/faifa/index.html`,
  "depreciation": `${_ERP}/faifa/index.html`,
  "asset retirement": `${_ERP}/faifa/index.html`,
  "group assets": `${_ERP}/faifa/index.html`,

  // ━━━ ERP — Cash Management ━━━
  "cash management": `${_ERP}/faicm/index.html`,
  "bank statements": `${_ERP}/faicm/index.html`,
  "bank reconciliation": `${_ERP}/faicm/index.html`,
  "cash positioning": `${_ERP}/faicm/index.html`,
  "cash forecasting": `${_ERP}/faicm/index.html`,

  // ━━━ ERP — Expenses ━━━
  "expenses": `${_ERP}/faiex/index.html`,
  "expense reports": `${_ERP}/faiex/index.html`,
  "expense policies": `${_ERP}/faiex/index.html`,
  "per diem": `${_ERP}/faiex/index.html`,
  "travel": `${_ERP}/faiex/index.html`,

  // ━━━ ERP — Tax ━━━
  "implementing tax": `${_ERP}/faitx/index.html`,
  "tax": `${_ERP}/faitx/index.html`,
  "tax rules": `${_ERP}/faitx/index.html`,
  "tax regimes": `${_ERP}/faitx/index.html`,
  "withholding tax": `${_ERP}/faitx/index.html`,
  "tax reporting": `${_ERP}/faitx/index.html`,

  // ━━━ ERP — Subledger Accounting ━━━
  "implementing subledger accounting": `${_ERP}/faisl/index.html`,
  "subledger accounting": `${_ERP}/faisl/index.html`,
  "accounting methods": `${_ERP}/faisl/index.html`,
  "accounting rules": `${_ERP}/faisl/index.html`,
  "sla": `${_ERP}/faisl/index.html`,

  // ━━━ ERP — Intercompany ━━━
  "intercompany": `${_ERP}/faiic/index.html`,
  "intercompany transactions": `${_ERP}/faiic/index.html`,
  "intercompany balancing": `${_ERP}/faiic/index.html`,

  // ━━━ ERP — Lease Accounting ━━━
  "lease accounting": `${_ERP}/faila/index.html`,
  "leases": `${_ERP}/faila/index.html`,
  "ifrs 16": `${_ERP}/faila/index.html`,
  "asc 842": `${_ERP}/faila/index.html`,

  // ━━━ ERP — Joint Venture ━━━
  "joint venture": `${_ERP}/faijv/index.html`,
  "joint venture management": `${_ERP}/faijv/index.html`,

  // ━━━ ERP — Common ━━━
  "implementing common features financials": `${_ERP}/faicf/index.html`,
  "financials common": `${_ERP}/faicf/index.html`,

  // ━━━ EPM — Planning ━━━
  "planning": `${_EPM}/index.html`,
  "enterprise planning": `${_EPM}/index.html`,
  "financial planning": `${_EPM}/index.html`,
  "workforce planning": `${_EPM}/index.html`,
  "capital planning": `${_EPM}/index.html`,
  "epm": `${_EPM}/index.html`,
  "enterprise performance management": `${_EPM}/index.html`,
  "epm overview": `${_EPM}/index.html`,

  // ━━━ EPM — Consolidation ━━━
  "financial consolidation": `${_EPM}/index.html`,
  "consolidation": `${_EPM}/index.html`,
  "eliminations": `${_EPM}/index.html`,

  // ━━━ EPM — Close ━━━
  "close manager": `${_EPM}/index.html`,
  "period close epm": `${_EPM}/index.html`,
  "close scheduling": `${_EPM}/index.html`,

  // ━━━ EPM — Account Reconciliation ━━━
  "account reconciliation": `${_EPM}/index.html`,
  "reconciliation compliance": `${_EPM}/index.html`,
  "transaction matching": `${_EPM}/index.html`,

  // ━━━ EPM — Profitability ━━━
  "profitability and cost management": `${_EPM}/index.html`,
  "cost allocation": `${_EPM}/index.html`,
  "profitability analysis": `${_EPM}/index.html`,

  // ━━━ EPM — Data Integration ━━━
  "data integration epm": `${_EPM}/index.html`,
  "data management epm": `${_EPM}/index.html`,
  "epm integration": `${_EPM}/index.html`,

  // ━━━ SCM — Inventory ━━━
  "inventory management": `${_SCM}/faimm/index.html`,
  "inventory": `${_SCM}/faimm/index.html`,
  "item organizations": `${_SCM}/faimm/index.html`,
  "on-hand quantities": `${_SCM}/faimm/index.html`,
  "inventory transactions": `${_SCM}/faimm/index.html`,
  "consignment": `${_SCM}/faimm/index.html`,

  // ━━━ SCM — Order Management ━━━
  "order management": `${_SCM}/faiom/index.html`,
  "sales orders": `${_SCM}/faiom/index.html`,
  "order fulfillment": `${_SCM}/faiom/index.html`,
  "pricing": `${_SCM}/faiom/index.html`,
  "returns": `${_SCM}/faiom/index.html`,
  "drop ship": `${_SCM}/faiom/index.html`,

  // ━━━ SCM — Manufacturing ━━━
  "manufacturing": `${_SCM}/faimf/index.html`,
  "work orders": `${_SCM}/faimf/index.html`,
  "work definitions": `${_SCM}/faimf/index.html`,
  "production scheduling": `${_SCM}/faimf/index.html`,
  "discrete manufacturing": `${_SCM}/faimf/index.html`,
  "process manufacturing": `${_SCM}/faimf/index.html`,

  // ━━━ SCM — Quality ━━━
  "quality management": `${_SCM}/faiqm/index.html`,
  "quality inspections": `${_SCM}/faiqm/index.html`,
  "quality plans": `${_SCM}/faiqm/index.html`,
  "nonconformance": `${_SCM}/faiqm/index.html`,

  // ━━━ SCM — Maintenance ━━━
  "maintenance management": `${_SCM}/faimt/index.html`,
  "asset maintenance": `${_SCM}/faimt/index.html`,

  // ━━━ SCM — Logistics ━━━
  "shipping": `${_SCM}/faish/index.html`,
  "receiving": `${_SCM}/fairc/index.html`,
  "transportation": `${_SCM}/faitr/index.html`,
  "warehouse management": `${_SCM}/faiwm/index.html`,
  "logistics": `${_SCM}/faish/index.html`,

  // ━━━ SCM — Overview ━━━
  "supply chain management": `${_SCM}/index.html`,
  "scm": `${_SCM}/index.html`,

  // ━━━ Procurement ━━━
  "procurement": `${_PR}/index.html`,
  "purchasing": `${_PR}/faipu/index.html`,
  "purchase orders": `${_PR}/faipu/index.html`,
  "self service procurement": `${_PR}/faiss/index.html`,
  "sourcing": `${_PR}/faiso/index.html`,
  "procurement contracts": `${_PR}/faipc/index.html`,
  "supplier portal": `${_PR}/faisp/index.html`,

  // ━━━ Projects ━━━
  "project management": `${_PRJ}/index.html`,
  "project financial management": `${_PRJ}/faipf/index.html`,
  "project resource management": `${_PRJ}/faipr/index.html`,
  "project costing": `${_PRJ}/faipc/index.html`,
  "project billing": `${_PRJ}/faipb/index.html`,
  "grants management": `${_PRJ}/faigm/index.html`,
  "project": `${_PRJ}/index.html`,

  // ━━━ CX — Sales ━━━
  "sales": `${_CX}/sales/index.html`,
  "cx sales": `${_CX}/sales/index.html`,
  "opportunities": `${_CX}/sales/index.html`,
  "leads": `${_CX}/sales/index.html`,
  "sales forecasting": `${_CX}/sales/index.html`,
  "territory management": `${_CX}/sales/index.html`,
  "sales quoting": `${_CX}/sales/index.html`,

  // ━━━ CX — Service ━━━
  "service": `${_CX}/service/index.html`,
  "cx service": `${_CX}/service/index.html`,
  "service requests": `${_CX}/service/index.html`,
  "knowledge management": `${_CX}/service/index.html`,
  "field service": `${_CX}/service/index.html`,
  "service entitlements": `${_CX}/service/index.html`,

  // ━━━ Cross-Module — Security & Access ━━━
  "security": `${_COM}/faasc/index.html`,
  "applications security": `${_COM}/faasc/index.html`,
  "function security": `${_COM}/faasc/index.html`,

  // ━━━ Cross-Module — Approvals ━━━
  "approvals": `${_COM}/faiaw/index.html`,
  "approval workflows": `${_COM}/faiaw/index.html`,
  "bpm": `${_COM}/faiaw/index.html`,
  "workflow": `${_COM}/faiaw/index.html`,
  "notifications": `${_COM}/faiaw/index.html`,

  // ━━━ Cross-Module — REST API ━━━
  "rest api": `${_COM}/farcr/index.html`,
  "rest apis": `${_COM}/farcr/index.html`,
  "api": `${_COM}/farcr/index.html`,
  "web services": `${_COM}/farcr/index.html`,

  // ━━━ Cross-Module — Flexfields & Lookups ━━━
  "flexfields": `${_COM}/faiem/index.html`,
  "descriptive flexfields": `${_COM}/faiem/index.html`,
  "key flexfields": `${_COM}/faiem/index.html`,
  "dff": `${_COM}/faiem/index.html`,
  "kff": `${_COM}/faiem/index.html`,
  "lookups": `${_COM}/faiem/index.html`,
  "value sets": `${_COM}/faiem/index.html`,
  "extensibility": `${_COM}/faiem/index.html`,

  // ━━━ Cross-Module — UI Customization ━━━
  "page composer": `${_COM}/faipg/index.html`,
  "sandboxes": `${_COM}/faisb/index.html`,
  "visual builder": `${_COM}/faivb/index.html`,
  "visual builder studio": `${_COM}/faivb/index.html`,
  "personalization": `${_COM}/faipg/index.html`,
  "infolets": `${_COM}/faiem/index.html`,

  // ━━━ Cross-Module — Other ━━━
  "attachments": `${_COM}/faiem/index.html`,
  "file import": `${_COM}/faiem/index.html`,
  "audit": `${_COM}/faiau/index.html`,
  "audit trail": `${_COM}/faiau/index.html`,
  "scheduled processes": `${_COM}/faisp/index.html`,
  "enterprise scheduler": `${_COM}/faisp/index.html`,
  "hcm common": `${_COM}/index.html`,
  "applications common": `${_COM}/index.html`,
};

// Known Oracle Fusion module index pages (fallback for broad queries)
const FUSION_MODULE_PAGES: [string, string][] = [
  ["HCM — Human Resources", `${_HCM}/books.html`],
  ["ERP — Financials", `${_ERP}/books.html`],
  ["EPM — Enterprise Performance Management", `${_EPM}/index.html`],
  ["SCM — Supply Chain Management", `${_SCM}/index.html`],
  ["Procurement", `${_PR}/books.html`],
  ["Projects", `${_PRJ}/index.html`],
  ["CX — Sales", `${_CX}/sales/books.html`],
  ["CX — Service", `${_CX}/service/books.html`],
  ["Applications Common", `${_COM}/index.html`],
];

// ── Caching ──────────────────────────────────────────────────

interface CacheEntry {
  content: string;
  expiresAt: number;
}

class ResponseCache {
  private maxSize: number;
  private ttlMs: number;
  private diskTtlMs: number;
  private maxDiskEntries: number;
  private cache: Map<string, CacheEntry>;
  private hits: number = 0;
  private misses: number = 0;
  private cacheDir: string | null = null;
  public diskEnabled: boolean = false;

  constructor(maxSize = 50, ttlSeconds = 3600, diskTtlSeconds = 86400, maxDiskEntries = 200) {
    this.maxSize = maxSize;
    this.ttlMs = ttlSeconds * 1000;
    this.diskTtlMs = diskTtlSeconds * 1000;
    this.maxDiskEntries = maxDiskEntries;
    this.cache = new Map();

    try {
      this.cacheDir = path.join(os.homedir(), ".cache", "oracle-fusion-docs");
      if (!fs.existsSync(this.cacheDir)) {
        fs.mkdirSync(this.cacheDir, { recursive: true });
      }
      this.diskEnabled = true;
    } catch (err) {
      console.error(
        `Failed to initialize persistent disk cache directory: ${err}. ` +
        "Falling back to in-memory caching only."
      );
      this.diskEnabled = false;
    }

    if (this.diskEnabled) {
      this.warmCacheFromDisk().catch((err) => {
        console.error(`Error during warming cache from disk: ${err}`);
      });
    }
  }

  private async warmCacheFromDisk(): Promise<void> {
    if (!this.cacheDir) return;
    try {
      const now = Date.now();
      let expiredEntries = 0;
      let corruptEntries = 0;

      const files = fs.readdirSync(this.cacheDir).filter(f => f.endsWith(".json"));
      const validFiles: { filepath: string; mtime: number }[] = [];

      for (const filename of files) {
        const filepath = path.join(this.cacheDir, filename);
        try {
          const stat = fs.statSync(filepath);
          const contentStr = fs.readFileSync(filepath, "utf-8");
          const data = JSON.parse(contentStr);

          const timestamp = data.timestamp;
          // Handle both seconds (Python) and milliseconds (JS) timestamps
          let tsMs = timestamp;
          if (timestamp < 100000000000) {
            tsMs = timestamp * 1000;
          }

          const ttlMs = (data.ttl || 86400) * 1000;

          if (now >= tsMs + ttlMs) {
            expiredEntries++;
            try { fs.unlinkSync(filepath); } catch {}
          } else {
            validFiles.push({ filepath, mtime: stat.mtimeMs });
          }
        } catch {
          corruptEntries++;
          try { fs.unlinkSync(filepath); } catch {}
        }
      }

      // Sort files by modification time descending (newest first)
      validFiles.sort((a, b) => b.mtime - a.mtime);

      // Load up to maxSize newest entries
      const toLoad = validFiles.slice(0, this.maxSize);

      // Load in reverse order (oldest first, newest last) to maintain LRU order
      let loadedEntries = 0;
      for (let i = toLoad.length - 1; i >= 0; i--) {
        const item = toLoad[i];
        try {
          const contentStr = fs.readFileSync(item.filepath, "utf-8");
          const data = JSON.parse(contentStr);
          const url = data.url;
          const content = data.content;
          const timestamp = data.timestamp;
          let tsMs = timestamp;
          if (timestamp < 100000000000) {
            tsMs = timestamp * 1000;
          }
          const ttlMs = (data.ttl || 86400) * 1000;

          const remainingDiskTtl = (tsMs + ttlMs) - now;
          if (remainingDiskTtl > 0) {
            const inMemoryTtl = Math.min(this.ttlMs, remainingDiskTtl);
            const expiresAt = now + inMemoryTtl;
            this.setMemory(url, content, expiresAt);
            loadedEntries++;
          }
        } catch {}
      }

      if (loadedEntries > 0 || expiredEntries > 0 || corruptEntries > 0) {
        console.error(
          `Warmed cache from disk: loaded ${loadedEntries} valid entries. ` +
          `Cleaned ${expiredEntries} expired and ${corruptEntries} corrupt entries on disk.`
        );
      }
    } catch (err) {
      console.error(`Error during warming cache from disk: ${err}`);
    }
  }

  private setMemory(url: string, content: string, expiresAt: number): void {
    if (this.cache.has(url)) {
      this.cache.delete(url);
    }
    if (this.cache.size >= this.maxSize) {
      const oldestKey = this.cache.keys().next().value;
      if (oldestKey !== undefined) {
        this.cache.delete(oldestKey);
      }
    }
    this.cache.set(url, { content, expiresAt });
  }

  private saveToDisk(url: string, content: string): void {
    if (!this.diskEnabled || !this.cacheDir) return;
    try {
      const md5 = crypto.createHash("md5").update(url).digest("hex");
      const filename = `${md5}.json`;
      const filepath = path.join(this.cacheDir, filename);

      // Enforce max disk entries limit (200)
      if (!fs.existsSync(filepath)) {
        const files = fs.readdirSync(this.cacheDir).filter(f => f.endsWith(".json"));
        if (files.length >= this.maxDiskEntries) {
          const filesWithStats = files.map(f => {
            const p = path.join(this.cacheDir!, f);
            try {
              return { path: p, mtime: fs.statSync(p).mtimeMs, name: f };
            } catch {
              return null;
            }
          }).filter((x): x is { path: string; mtime: number; name: string } => x !== null);

          if (filesWithStats.length > 0) {
            filesWithStats.sort((a, b) => a.mtime - b.mtime);
            const oldest = filesWithStats[0];
            try {
              fs.unlinkSync(oldest.path);
              console.error(`Evicted oldest disk cache entry: ${oldest.name}`);
            } catch (err) {
              console.error(`Failed to evict oldest disk cache entry ${oldest.name}: ${err}`);
            }
          }
        }
      }

      const data = {
        url,
        content,
        timestamp: Date.now() / 1000, // stored in seconds for Python compatibility
        ttl: this.diskTtlMs / 1000
      };

      fs.writeFileSync(filepath, JSON.stringify(data, null, 2), "utf-8");
    } catch (err) {
      console.error(`Failed to save entry to disk cache for URL ${url}: ${err}`);
    }
  }

  public get(url: string): string | null {
    const now = Date.now();

    // 1. Check memory cache
    const memEntry = this.cache.get(url);
    if (memEntry) {
      if (now < memEntry.expiresAt) {
        this.hits++;
        // Maintain LRU order by deleting and re-setting
        this.cache.delete(url);
        this.cache.set(url, memEntry);
        return memEntry.content;
      } else {
        this.cache.delete(url);
      }
    }

    // 2. Check disk cache
    if (this.diskEnabled && this.cacheDir) {
      const md5 = crypto.createHash("md5").update(url).digest("hex");
      const filename = `${md5}.json`;
      const filepath = path.join(this.cacheDir, filename);

      if (fs.existsSync(filepath)) {
        try {
          const contentStr = fs.readFileSync(filepath, "utf-8");
          const data = JSON.parse(contentStr);
          const timestamp = data.timestamp;
          let tsMs = timestamp;
          if (timestamp < 100000000000) {
            tsMs = timestamp * 1000;
          }
          const ttlMs = (data.ttl || 86400) * 1000;

          if (now < tsMs + ttlMs) {
            const remainingDiskTtl = (tsMs + ttlMs) - now;
            const inMemoryTtl = Math.min(this.ttlMs, remainingDiskTtl);
            const expiresAt = now + inMemoryTtl;
            this.setMemory(url, data.content, expiresAt);

            this.hits++;
            console.error(`fetch_oracle_page: disk cache HIT for URL: ${url}`);
            return data.content;
          } else {
            try { fs.unlinkSync(filepath); } catch {}
          }
        } catch (err) {
          console.error(`Failed to read disk cache file ${filename}: ${err}`);
        }
      }
    }

    this.misses++;
    return null;
  }

  public set(url: string, content: string): void {
    const expiresAt = Date.now() + this.ttlMs;
    this.setMemory(url, content, expiresAt);
    this.saveToDisk(url, content);
  }

  public getDiskStats(): { count: number; sizeKb: number } {
    if (!this.diskEnabled || !this.cacheDir) return { count: 0, sizeKb: 0.0 };
    try {
      let count = 0;
      let totalBytes = 0;
      const files = fs.readdirSync(this.cacheDir).filter(f => f.endsWith(".json"));
      for (const filename of files) {
        try {
          const stat = fs.statSync(path.join(this.cacheDir, filename));
          count++;
          totalBytes += stat.size;
        } catch {}
      }
      return { count, sizeKb: totalBytes / 1024.0 };
    } catch {
      return { count: 0, sizeKb: 0.0 };
    }
  }

  public getStats() {
    const total = this.hits + this.misses;
    const ratio = total > 0 ? this.hits / total : 0.0;
    const { count: diskCount, sizeKb: diskSizeKb } = this.getDiskStats();
    return {
      hits: this.hits,
      misses: this.misses,
      totalRequests: total,
      hitRatio: ratio,
      size: this.cache.size,
      diskCount,
      diskSizeKb
    };
  }

  // Helper for tests
  public clearMemory(): void {
    this.cache.clear();
  }
}

const pageCache = new ResponseCache(50, 3600);

function logCacheStats(): void {
  const stats = pageCache.getStats();
  console.error(
    `Cache Statistics: Hits: ${stats.hits}, Misses: ${stats.misses}, ` +
    `Hit Ratio: ${(stats.hitRatio * 100).toFixed(2)}%, ` +
    `Active Entries: ${stats.size}/50 (Disk: ${stats.diskCount} entries, ${stats.diskSizeKb.toFixed(2)} KB)`
  );
}

// ── Search Logic ─────────────────────────────────────────────

interface IndexMatch {
  keyword: string;
  url: string;
  matchType: "exact" | "partial";
}

function searchTopicIndex(query: string, limit = 5): IndexMatch[] {
  const q = query.toLowerCase().trim();
  const matches: IndexMatch[] = [];

  // Exact matches
  for (const [keyword, url] of Object.entries(TOPIC_INDEX)) {
    if (q === keyword) {
      matches.push({ keyword, url, matchType: "exact" });
    }
  }

  // Partial matches (query inside keyword, or keyword inside query)
  if (matches.length === 0) {
    for (const [keyword, url] of Object.entries(TOPIC_INDEX)) {
      if (keyword.includes(q) || q.includes(keyword)) {
        matches.push({ keyword, url, matchType: "partial" });
      }
    }
  }

  // Deduplicate by URL
  const seen = new Set<string>();
  const unique: IndexMatch[] = [];
  for (const match of matches) {
    if (!seen.has(match.url)) {
      seen.add(match.url);
      unique.push(match);
    }
  }

  return unique.slice(0, limit);
}

// ── Helper Processing Functions ──────────────────────────────

function stripJinaHeader(text: string): string {
  const lines = text.split("\n");
  let contentStart = 0;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (line.startsWith("Markdown Content:")) {
      contentStart = i + 1;
      break;
    }
    if (line.startsWith("#") && !line.startsWith("## URL")) {
      contentStart = i;
      break;
    }
  }
  return lines.slice(contentStart).join("\n");
}

function collapseBlanks(text: string): string {
  const lines = text.split("\n");
  const cleaned: string[] = [];
  let blankCount = 0;
  for (const line of lines) {
    if (line.trim() === "") {
      blankCount++;
      if (blankCount <= 2) {
        cleaned.push(line);
      }
    } else {
      blankCount = 0;
      cleaned.push(line);
    }
  }
  return cleaned.join("\n");
}

// ── HTTP Request & Retry Logic ───────────────────────────────

const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

async function jinaGet(url: string): Promise<string> {
  const targetUrl = `${JINA_READER_URL}${url}`;

  for (let attempt = 1; attempt <= 3; attempt++) {
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), REQUEST_TIMEOUT);

    try {
      const response = await fetch(targetUrl, {
        headers: {
          "Accept": "text/markdown",
          "User-Agent": USER_AGENT
        },
        signal: controller.signal
      });

      clearTimeout(id);

      if (!response.ok) {
        if (response.status === 429) {
          throw new Error("HTTP 429 Rate Limit");
        }
        throw new Error(`HTTP ${response.status}`);
      }

      return await response.text();
    } catch (err: any) {
      clearTimeout(id);
      
      const isTimeout = err.name === "AbortError";
      const is429 = err.message && err.message.includes("429");
      const isNetworkError = err instanceof TypeError || (err.message && (err.message.includes("network") || err.message.includes("fetch")));
      const shouldRetry = isTimeout || isNetworkError || is429;

      if (attempt === 3 || !shouldRetry) {
        throw err;
      }

      const delayMs = attempt === 1 ? 2000 : 4000;
      console.error(
        `Retry attempt ${attempt} failed for URL ${url}: ${err.name || "Error"}: ${err.message || err}. ` +
        `waiting ${(delayMs / 1000).toFixed(1)}s before next attempt.`
      );
      await sleep(delayMs);
    }
  }
  throw new Error("Unexpected end of retry loop");
}

// ── Tool Implementation Functions ────────────────────────────

function searchOracleDocsTool(query: string, maxResults = 10): string {
  console.error(`search_oracle_docs: query='${query}', max_results=${maxResults}`);
  const indexMatches = searchTopicIndex(query, maxResults);

  const googleUrl = `https://www.google.com/search?q=site%3Adocs.oracle.com%2Fen%2Fcloud%2Fsaas%2F+${encodeURIComponent(query)}`;
  const oracleUrl = `https://docs.oracle.com/search/?q=${encodeURIComponent(query)}`;

  const lines: string[] = [`## Search: *${query}*\n`];

  if (indexMatches.length > 0) {
    console.error(`search_oracle_docs: found ${indexMatches.length} matches in topic index`);
    lines.push("### 📚 Matching Documentation Pages\n");
    indexMatches.forEach((match, index) => {
      const tag = match.matchType === "exact" ? "🎯" : "🔍";
      const title = match.keyword.split(" ").map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
      lines.push(`**${index + 1}. [${title}](${match.url})** ${tag}`);
    });
    lines.push("");
  } else {
    console.error(`search_oracle_docs: empty results (no matches found) for query '${query}'`);
    lines.push("### 🔍 No exact match in the topic index.\n");
  }

  lines.push("### 📂 Oracle Fusion Module Indexes\n");
  FUSION_MODULE_PAGES.forEach((mod, index) => {
    lines.push(`**${index + 1}. [${mod[0]}](${mod[1]})**`);
  });
  lines.push("");

  lines.push("### 🔗 Search Oracle Directly\n");
  lines.push(`- [Search Google (site:docs.oracle.com)](${googleUrl})`);
  lines.push(`- [Search Oracle Help Center](${oracleUrl})`);
  lines.push("");

  lines.push("> 💡 **Tip**: Use `fetch_oracle_page(url)` to read any page above in clean markdown.");

  return lines.join("\n");
}

async function fetchOraclePageTool(url: string): Promise<string> {
  let cleanUrl = url.trim();
  console.error(`fetch_oracle_page: called with URL: ${cleanUrl}`);

  if (!cleanUrl.includes("docs.oracle.com")) {
    console.error(`fetch_oracle_page: invalid URL domain requested: ${cleanUrl}`);
    return "Error: URL must be under docs.oracle.com. Please specify a valid Oracle documentation URL.";
  }

  if (!cleanUrl.startsWith("http")) {
    cleanUrl = `https://${cleanUrl}`;
  }

  // Cache check
  const cachedContent = pageCache.get(cleanUrl);
  if (cachedContent !== null) {
    console.error(`fetch_oracle_page: cache HIT for URL: ${cleanUrl}`);
    logCacheStats();
    return cachedContent;
  }

  console.error(`fetch_oracle_page: cache MISS for URL: ${cleanUrl}`);

  let respText = "";
  try {
    respText = await jinaGet(cleanUrl);
  } catch (err: any) {
    const isTimeout = err.name === "AbortError";
    const is429 = err.message && err.message.includes("429");
    const isNetworkError = err instanceof TypeError || (err.message && (err.message.includes("network") || err.message.includes("fetch")));

    if (isTimeout) {
      const errMsg = `Error: Request to Jina Reader timed out after 3 attempts. Try again or check the URL directly: ${cleanUrl}`;
      console.error(`fetch_oracle_page: timeout fetching URL ${cleanUrl}: ${err}`);
      return errMsg;
    } else if (is429) {
      const errMsg = "Error: Rate limit exceeded (HTTP 429) after 3 attempts. Jina Reader is currently rate-limiting requests. Please wait a minute and try again.";
      console.error(`fetch_oracle_page: HTTP 429 fetching URL ${cleanUrl}: ${err}`);
      return errMsg;
    } else if (isNetworkError) {
      const errMsg = "Error: Network connection failed after 3 attempts. Check your internet connection and verify if Jina Reader (https://r.jina.ai/) is reachable.";
      console.error(`fetch_oracle_page: Network error fetching URL ${cleanUrl}: ${err}`);
      return errMsg;
    } else {
      const httpMatch = err.message && err.message.match(/HTTP (\d+)/);
      if (httpMatch) {
        const statusCode = httpMatch[1];
        const errMsg = `Error: HTTP ${statusCode} returned. The page may be inaccessible, deleted, or requires login. Verify the URL: ${cleanUrl}`;
        console.error(`fetch_oracle_page: HTTP ${statusCode} fetching URL ${cleanUrl}: ${err}`);
        return errMsg;
      }
      const errMsg = `Error: Unexpected network failure — ${err.name || "Error"}: ${err.message || err}. Please ensure Jina Reader is available and try again.`;
      console.error(`fetch_oracle_page: unexpected failure fetching URL ${cleanUrl}: ${err}`);
      return errMsg;
    }
  }

  let text = stripJinaHeader(respText);
  let result = collapseBlanks(text);
  let isTruncated = false;

  if (result.length > MAX_PAGE_CHARS) {
    result = result.slice(0, MAX_PAGE_CHARS) + "\n\n[... truncated — content exceeds 15K chars]";
    isTruncated = true;
  }

  if (result.trim().length < 50) {
    console.error(`fetch_oracle_page: empty or very short content extracted (${result.length} chars) for URL: ${cleanUrl}`);
    return (
      `Warning: Very little content extracted (${result.length} chars). ` +
      `The page may be JavaScript-rendered, require login, or be inaccessible. ` +
      `Check the URL directly: ${cleanUrl}`
    );
  }

  pageCache.set(cleanUrl, result);

  if (isTruncated) {
    console.error(`fetch_oracle_page: truncated content fetched for URL ${cleanUrl} (${result.length} chars)`);
  } else {
    console.error(`fetch_oracle_page: successfully fetched URL ${cleanUrl} (${result.length} chars)`);
  }

  logCacheStats();
  return result;
}

function listModulesTool(): string {
  console.error("list_modules: called");
  const lines: string[] = ["## Oracle Fusion Cloud Modules\n"];
  FUSION_MODULE_PAGES.forEach((mod, index) => {
    lines.push(`${index + 1}. **[${mod[0]}](${mod[1]})**`);
  });
  lines.push("");
  lines.push(`> 📚 **Total topic index**: ${Object.keys(TOPIC_INDEX).length} keywords mapped to documentation pages.`);
  lines.push("> Use `search_oracle_docs(query)` to find specific topics within these modules.");
  return lines.join("\n");
}

// ── MCP Server Setup ─────────────────────────────────────────

const server = new Server(
  {
    name: "oracle-fusion-docs",
    version: "3.0.0",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// Register Tool Listing
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: "search_oracle_docs",
        description: "Search Oracle Fusion Cloud documentation by topic. Covers HCM, ERP, EPM, SCM, Procurement, Projects, CX (Sales/Service), and Applications Common.",
        inputSchema: {
          type: "object",
          properties: {
            query: {
              type: "string",
              description: "Natural language search query (e.g. 'payroll fast formula', 'absence management implementation', 'otbi subject areas')",
              minLength: 2,
              maxLength: 500,
            },
            max_results: {
              type: "integer",
              description: "Maximum number of results to return (1-10)",
              minimum: 1,
              maximum: 10,
              default: 10,
            },
          },
          required: ["query"],
        },
      },
      {
        name: "fetch_oracle_page",
        description: "Fetch and return clean markdown from an Oracle documentation page. Handles Jina Reader rendering and caches results.",
        inputSchema: {
          type: "object",
          properties: {
            url: {
              type: "string",
              description: "Full URL of an Oracle documentation page under docs.oracle.com",
              minLength: 20,
              maxLength: 1000,
            },
          },
          required: ["url"],
        },
      },
      {
        name: "list_modules",
        description: "List all Oracle Fusion Cloud modules with their documentation home pages.",
        inputSchema: {
          type: "object",
          properties: {},
        },
      },
    ],
  };
});

// Register Tool Call Handling
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    if (name === "search_oracle_docs") {
      const parsed = z.object({
        query: z.string().min(2).max(500),
        max_results: z.number().int().min(1).max(10).default(10),
      }).parse(args);

      const result = searchOracleDocsTool(parsed.query, parsed.max_results);
      return {
        content: [{ type: "text", text: result }],
      };
    } else if (name === "fetch_oracle_page") {
      const parsed = z.object({
        url: z.string().min(20).max(1000),
      }).parse(args);

      const result = await fetchOraclePageTool(parsed.url);
      return {
        content: [{ type: "text", text: result }],
      };
    } else if (name === "list_modules") {
      const result = listModulesTool();
      return {
        content: [{ type: "text", text: result }],
      };
    } else {
      throw new Error(`Tool not found: ${name}`);
    }
  } catch (err: any) {
    console.error(`Error executing tool ${name}: ${err}`);
    return {
      content: [{ type: "text", text: `Error: ${err.message || err}` }],
      isError: true,
    };
  }
});

// ── Server Execution ─────────────────────────────────────────

async function run() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Oracle Fusion Docs MCP Server (TypeScript) running on stdio");
}

// Graceful shutdown handling
process.on("SIGINT", async () => {
  console.error("Shutting down gracefully (SIGINT)...");
  await server.close();
  process.exit(0);
});

process.on("SIGTERM", async () => {
  console.error("Shutting down gracefully (SIGTERM)...");
  await server.close();
  process.exit(0);
});

run().catch((err) => {
  console.error("Fatal error running server:", err);
  process.exit(1);
});
