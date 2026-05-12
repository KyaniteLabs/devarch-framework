# Stage 09-Strategy

Generate go-to-market and business strategy from archaeology outputs.

This is an optional extension stage. Not every archaeology project needs a GTM strategy, but projects heading to market benefit from evidence-based strategic planning grounded in development data.

## Context Loading

| Layer | Load | Skip |
|-------|------|------|
| L3 (reference) | references/strategy-sections.md | shared/concepts.md, shared/sync-rules.md |
| L4 (working) | ../05-analyze/output/analysis-*.json, ../04-detect/output/detected-signals.json, ../07-report/output/ARCHAEOLOGY-REPORT.md | stages/01-03 outputs |

## Inputs

| Source | File/Location | Section/Scope | Why |
|--------|---------------|---------------|-----|
| Previous stage | ../07-report/output/ARCHAEOLOGY-REPORT.md | Full file | Base analysis |
| Previous stage | ../05-analyze/output/analysis-*.json | Full files | Detailed findings |
| Previous stage | ../04-detect/output/detected-signals.json | Full file | Signal data |
| Project config | ../../project.json | Full file | Project identity |
| Reference | references/strategy-sections.md | Full file | Required sections |

## Process

1. Read all archaeology outputs from previous stages
2. Read the project.json for product context
3. Analyze source code structure for feature inventory
4. Research market positioning based on product description
5. Generate pricing analysis from billing code evidence
6. Build launch timeline from development velocity data
7. Identify viral loops and growth mechanisms
8. Assess risks using development pattern evidence
9. Write archaeology-informed strategic insights
10. Produce 90-day action plan
11. Define success metrics with targets
12. Run quality audit on strategy document

## Outputs

| Artifact | Location | Format |
|----------|----------|--------|
| GTM Strategy Report | output/[project-name]-gtm-strategy.html | Self-contained HTML |

## Audit

| Check | Pass Condition |
|-------|---------------|
| All 10 strategy sections present | Executive summary, positioning, pricing, timeline, channels, growth, risks, archaeology insights, action plan, metrics |
| No placeholder data | All numbers sourced from archaeology data |
| No project leakage | Zero references to other DevArch projects |

## Next Stage

This is a terminal stage. Pipeline is complete.
