# Project Context — Oracle Fusion Docs MCP

> **Type:** MCP server — documentation Oracle Fusion Cloud
> **Repo:** `/mnt/c/Users/SimonJonasKreis-Rich/repositories/oracle-fusion-docs-mcp/`
> **Skill:** `mcp-integration`
> **Status:** Actif

---

## Overview

Serveur MCP (Model Context Protocol) qui expose la documentation Oracle Fusion Cloud
comme outils pour les agents IA. Permet de chercher et lire la doc Oracle directement
depuis Hermes via les outils MCP.

## Stack technique

- **Language:** TypeScript (migration depuis Python)
- **Runtime:** Node.js
- **Build:** `npm run build` → `dist/`
- **Package:** npm/npx
- **MCP SDK:** @modelcontextprotocol/sdk

## Architecture

```
src/            → Source TypeScript
dist/           → Build output
node_modules/   → Dépendances
package.json    → Config npm
tsconfig.json   → Config TypeScript
```

## Outils exposés

- `search_oracle_docs` — Recherche dans la doc Oracle Fusion
- `fetch_oracle_page` — Lecture d'une page spécifique
- `list_modules` — Liste des modules Oracle disponibles

---

## Session State

<!-- Mettre à jour après des changements significatifs -->

### Dernière activité
- 2026-05-31 : Context créé

### Status
- MCP server opérationnel, migration TypeScript terminée

### Issues connus
- (aucun pour l'instant)
