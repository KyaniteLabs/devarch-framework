# analysis-formal-terms-mapper
**Total Findings:** 11
---
## Terminology Mapping
**Description:** "recipe" maps to formal term: "structured data model"
**Confidence:** high
**Evidence:**
- Final polish: regional matcher fix, structured recipe inputs, HTTP tests (#44)
- Add trust checks for constrained recipe handoffs

## Terminology Mapping
**Description:** "ingredient" maps to formal term: "data entity"
**Confidence:** high
**Evidence:**
- feat: add ingredient compound and sensory profile data
- feat: add US regional ingredient availability data
- Rename to Achiote, expand data: 40 families, 82 ingredients, 15 regions (#34)

## Terminology Mapping
**Description:** "dish" maps to formal term: "domain entity"
**Confidence:** high
**Evidence:**
- feat: add dish families with aliases and transliteration mappings
- feat: add SQLite research cache for storing looked-up dish data
- Add ambiguity-aware dish resolution

## Terminology Mapping
**Description:** "substitution" maps to formal term: "algorithmic transformation"
**Confidence:** high
**Evidence:**
- feat: add chemistry-aware substitution engine
- feat: wire ResearchCache, SubstitutionEngine, and data files into MCP tools

## Terminology Mapping
**Description:** "research cache" maps to formal term: "data persistence layer"
**Confidence:** high
**Evidence:**
- feat: add SQLite research cache for storing looked-up dish data

## Terminology Mapping
**Description:** "MCP" maps to formal term: "Model Context Protocol server"
**Confidence:** high
**Evidence:**
- feat: add MCP server with 6 tools
- feat: wire ResearchCache, SubstitutionEngine, and data files into MCP tools
- test: add integration tests for all 6 MCP tools

## Terminology Mapping
**Description:** "fuzzy matching" maps to formal term: "approximate string matching algorithm"
**Confidence:** high
**Evidence:**
- feat: add name resolver with fuzzy matching and transliteration support

## Terminology Mapping
**Description:** "transliteration" maps to formal term: "text normalization"
**Confidence:** high
**Evidence:**
- feat: add dish families with aliases and transliteration mappings
- feat: add name resolver with fuzzy matching and transliteration support

## Terminology Mapping
**Description:** "chemistry-aware" maps to formal term: "domain-specific logic"
**Confidence:** high
**Evidence:**
- feat: add chemistry-aware substitution engine

## Formal Convention
**Description:** Project uses Conventional Commits specification
**Confidence:** high
**Evidence:**
- chore: scaffold member-berries project
- feat: add shared type definitions
- feat: add ingredient compound and sensory profile data

## Formal Convention
**Description:** Project implements MCP (Model Context Protocol) architecture
**Confidence:** high
**Evidence:**
- feat: add MCP server with 6 tools
- feat: wire ResearchCache, SubstitutionEngine, and data files into MCP tools
- test: add integration tests for all 6 MCP tools

