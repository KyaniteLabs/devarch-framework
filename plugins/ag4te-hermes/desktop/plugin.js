// AG4TE for Hermes Desktop: dig a git repo and read its history like rock strata.
// Plain ESM, no build step. Chrome uses the app's theme variables (var(--ui-*)); the
// seven work-type colours are a fixed, validated palette with a dark and a light set.
import * as sdk from '@hermes/plugin-sdk'
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

const PATH = '/ag4te'
const KINDS = ['feat', 'fix', 'refactor', 'docs', 'ops', 'test', 'other']
const KIND_LABEL = { feat: 'Features', fix: 'Fixes', refactor: 'Refactors', docs: 'Docs', ops: 'Ops & chores', test: 'Tests', other: 'Other', merge: 'Merge' }
// Colour follows the work type, never its rank. Validated for CVD separation on each surface.
const PALETTE = {
  dark: { feat: '#00a2ce', fix: '#d84497', refactor: '#8b61e3', docs: '#00ad71', ops: '#366bd3', test: '#7ca215', other: '#8a94a8' },
  light: { feat: '#008fb3', fix: '#c61d78', refactor: '#7544cd', docs: '#009962', ops: '#2256bb', test: '#6c8e03', other: '#8a94a8' }
}
const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const SIGNAL_ROWS = ['velocity', 'scope', 'author', 'gap']
const SIGNAL_LABEL = { velocity: 'Pace', scope: 'Scope', author: 'People', gap: 'Quiet' }
const LOAD_LABEL = { TRIVIAL: 'Tiny', ROUTINE: 'Small', MODERATE: 'Medium', HIGH: 'Large', INTENSE: 'Huge' }
const LOAD_RANGE = { TRIVIAL: '≤10 lines', ROUTINE: '≤50', MODERATE: '≤200', HIGH: '≤800', INTENSE: '800+' }
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const PAGE = 60
// The stone renders 'other' as milky chalcedony, the translucent layer between an agate's colours.
const CHALCEDONY = '#c4b5f0'

function h(type, props, ...children) {
  const { key, ...rest } = props || {}
  const kids = children.flat().filter(c => c !== null && c !== undefined && c !== false)
  if (kids.length === 1) rest.children = kids[0]
  else if (kids.length > 1) rest.children = kids
  return (kids.length > 1 ? jsxs : jsx)(type, rest, key)
}

const CSS = `
@font-face{font-family:'AG Chakra';font-weight:600;font-display:swap;src:url(data:font/woff2;base64,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) format('woff2')}
@font-face{font-family:'AG Chakra';font-weight:700;font-display:swap;src:url(data:font/woff2;base64,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) format('woff2')}
.ag{container-type:inline-size;height:100%;overflow:auto;color:var(--ui-text-primary);font-size:13.5px;line-height:1.5;
  --ag-mono:ui-monospace,'SF Mono','JetBrains Mono',Menlo,Consolas,monospace;--ag-r:12px;
  --ag-display:'AG Chakra','Chakra Petch',system-ui,sans-serif}
.ag *{box-sizing:border-box}
.ag-main{max-width:1320px;margin:0 auto;padding:20px 24px 40px;display:flex;flex-direction:column;gap:16px}
.ag-head{display:flex;flex-wrap:wrap;gap:10px 14px;align-items:center}
.ag-brand{display:flex;align-items:center;gap:10px;margin-right:auto}
.ag-brand span{color:var(--ui-text-secondary);font-size:12.5px}
.ag-ctl{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.ag-select{font:inherit;font-size:13px;color:var(--ui-text-primary);background:transparent;color-scheme:inherit;border:1px solid var(--ui-stroke-secondary);border-radius:7px;padding:5px 8px;min-width:0;max-width:280px}
.ag-select option{background:var(--ui-bg-elevated,Canvas);color:var(--ui-text-primary,CanvasText)}
.ag-btn{font:inherit;font-size:12.5px;border:1px solid var(--ui-stroke-secondary);background:transparent;color:var(--ui-text-primary);border-radius:7px;padding:5px 12px;cursor:pointer;white-space:nowrap}
.ag-btn:hover{background:var(--ui-control-hover-background)}
.ag-btn.pri{background:var(--ui-accent);border-color:var(--ui-accent);color:var(--ui-accent-foreground,#fff);font-weight:600}
.ag-btn:disabled{opacity:.5;cursor:default}
.ag-run{display:flex;flex-direction:column;gap:6px;border:1px solid var(--ui-stroke-tertiary);border-radius:var(--ag-r);padding:12px 14px;background:var(--ui-bg-card)}
.ag-run .bar{height:6px;border-radius:3px;background:var(--ui-stroke-tertiary);overflow:hidden}
.ag-run .bar i{display:block;height:100%;background:linear-gradient(90deg,#00a2ce,#8b61e3,#d84497);transition:width .4s ease}
.ag-run small{color:var(--ui-text-secondary)}
.ag-kpis{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));border:1px solid var(--ui-stroke-tertiary);border-radius:var(--ag-r);overflow:hidden;background:var(--ui-bg-card)}
.ag-kpis div{padding:10px 14px;border-right:1px solid var(--ui-stroke-tertiary);min-width:0}
.ag-kpis div:last-child{border-right:0}
.ag-kpis small{display:block;font-size:11px;letter-spacing:.05em;text-transform:uppercase;color:var(--ui-text-secondary);margin-bottom:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ag-kpis span{font:600 19px/1.1 var(--ag-mono);font-variant-numeric:tabular-nums;white-space:nowrap}
.ag-kpis em{font-style:normal;font:500 11.5px var(--ag-mono);color:var(--ui-text-secondary);margin-left:4px}
.ag-card{background:var(--ui-bg-card);border:1px solid var(--ui-stroke-tertiary);border-radius:var(--ag-r);padding:14px 16px;min-width:0}
.ag-card h3{margin:0;font-size:13.5px;font-weight:600}
.ag-chead{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center;justify-content:space-between;margin-bottom:10px}
.ag-sub{color:var(--ui-text-secondary);font-size:12px;margin:2px 0 0}
.ag-tabs{display:inline-flex;border:1px solid var(--ui-stroke-tertiary);border-radius:7px;padding:2px;gap:2px}
.ag-tabs button{font:inherit;font-size:12px;border:0;background:transparent;color:var(--ui-text-secondary);padding:3px 10px;min-height:24px;border-radius:5px;cursor:pointer}
.ag-tabs button[aria-pressed=true]{background:var(--ui-control-active-background);color:var(--ui-text-primary)}
.ag-legend{display:flex;flex-wrap:wrap;gap:4px 6px}
.ag-legend button{font:inherit;font-size:12px;display:inline-flex;align-items:center;gap:6px;border:1px solid transparent;background:transparent;color:var(--ui-text-primary);border-radius:6px;padding:2px 8px;min-height:24px;cursor:pointer}
.ag-legend button:hover{border-color:var(--ui-stroke-tertiary)}
.ag-legend button[aria-pressed=false]{color:var(--ui-text-tertiary)}
.ag-legend button[aria-pressed=false] i{opacity:.25}
.ag-legend i{width:10px;height:10px;border-radius:3px;display:inline-block}
.ag-legend em{font-style:normal;font-family:var(--ag-mono);color:var(--ui-text-secondary);font-size:11.5px}
.ag-chart{position:relative}
.ag-chart svg{display:block;width:100%;height:auto;overflow:visible}
.ag-chart text{font-family:var(--ag-mono);font-size:10.5px;fill:var(--ui-text-secondary)}
.ag-chart .hit{cursor:crosshair}
.ag-tip{position:absolute;pointer-events:none;background:var(--ui-bg-elevated);color:var(--ui-text-primary);border:1px solid var(--ui-stroke-secondary);border-radius:8px;
  padding:7px 10px;font:12px/1.45 var(--ag-mono);box-shadow:0 8px 22px -8px rgba(0,0,0,.45);z-index:3;max-width:320px;white-space:normal}
.ag-tip b{font-weight:600}
.ag-tip .r{display:grid;grid-template-columns:10px minmax(0,1fr) auto;gap:6px;align-items:center}
.ag-tip .r i{width:9px;height:9px;border-radius:2px}
.ag-foot{display:flex;flex-wrap:wrap;justify-content:space-between;gap:6px 14px;margin-top:8px;font-size:11.5px;color:var(--ui-text-secondary)}
.ag-grid2{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(0,1fr);gap:16px}
.ag-stack{display:flex;flex-direction:column;gap:16px;min-width:0}
.ag-grid3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}
.ag-bars{display:flex;flex-direction:column;gap:9px;margin:0;padding:0;list-style:none}
.ag-bars li{display:grid;grid-template-columns:128px minmax(0,1fr) 54px;gap:10px;align-items:center;font-size:12.5px}
.ag-bars li>span:first-child{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ag-bars .t{height:10px;border-radius:0 4px 4px 0;background:transparent;position:relative}
.ag-bars .t i{display:block;height:100%;border-radius:0 4px 4px 0;min-width:2px}
.ag-bars b{font:600 12px var(--ag-mono);text-align:right;font-variant-numeric:tabular-nums}
.ag-sdlc{display:flex;flex-direction:column;margin:0;padding:0;list-style:none}
.ag-sdlc li{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:4px 12px;padding:9px 0;border-top:1px solid var(--ui-stroke-tertiary)}
.ag-sdlc li:first-child{border-top:0;padding-top:0}
.ag-sdlc p{margin:0;grid-column:1/-1;color:var(--ui-text-secondary);font-size:12px}
.ag-st{--tone:var(--ui-text-secondary);display:inline-flex;align-items:center;gap:5px;font:600 11px/1 var(--ag-mono);padding:4px 7px;border-radius:5px;white-space:nowrap;color:color-mix(in oklab,var(--tone) 62%,var(--ui-text-primary));border:1px solid color-mix(in srgb,var(--tone) 50%,transparent);background:color-mix(in srgb,var(--tone) 10%,transparent)}
.ag-st svg{color:var(--tone)}
.ag-st svg{width:11px;height:11px}
.ag-sig{display:flex;flex-direction:column;gap:8px;margin:0;padding:0;list-style:none}
.ag-sig li{display:grid;grid-template-columns:20px 64px minmax(0,1fr);gap:8px;font-size:12.5px;border-radius:6px;padding:2px 4px;margin:0 -4px;outline:none}
.ag-sig li.on,.ag-sig li:focus-visible{background:var(--ui-control-hover-background)}
.ag-sig .no{display:inline-grid;place-items:center;width:18px;height:18px;border-radius:50%;background:var(--ui-text-primary);color:var(--ui-bg-card);font:700 10px/1 var(--ag-mono)}
.ag-sig time{font:12px var(--ag-mono);color:var(--ui-text-secondary)}
.ag-sig small{display:block;color:var(--ui-text-secondary);font-size:11px;text-transform:uppercase;letter-spacing:.05em}
.ag-tools{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.ag-search{font:inherit;font-size:12.5px;color:var(--ui-text-primary);background:transparent;border:1px solid var(--ui-stroke-secondary);border-radius:7px;padding:5px 9px;min-width:0;flex:0 1 260px}
.ag-table{width:100%;border-collapse:collapse;font-size:12.5px;table-layout:fixed}
.ag-table th{text-align:left;font-weight:600;font-size:11px;letter-spacing:.05em;text-transform:uppercase;color:var(--ui-text-secondary);padding:6px 8px;border-bottom:1px solid var(--ui-stroke-tertiary)}
.ag-table td{padding:6px 8px;border-bottom:1px solid var(--ui-stroke-tertiary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;vertical-align:middle}
.ag-table td.m{font-family:var(--ag-mono);font-size:12px;color:var(--ui-text-secondary)}
.ag-table td.n{font-family:var(--ag-mono);font-size:12px;text-align:right;font-variant-numeric:tabular-nums}
.ag-kind{display:inline-flex;align-items:center;gap:6px;font-size:12px}
.ag-kind i{width:8px;height:8px;border-radius:2px;display:inline-block}
.ag-add{color:color-mix(in srgb,var(--ui-green,#2e9e5b) 85%,var(--ui-text-primary))}
.ag-del{color:color-mix(in srgb,var(--ui-red,#d0453f) 85%,var(--ui-text-primary))}
.ag-empty{border:1px dashed var(--ui-stroke-secondary);border-radius:var(--ag-r);padding:26px;color:var(--ui-text-secondary);display:flex;flex-direction:column;gap:8px;align-items:flex-start}
.ag-empty b{color:var(--ui-text-primary);font-size:15px}
.ag-empty code,.ag-muted code{font-family:var(--ag-mono);font-size:12px;padding:1px 5px;border-radius:4px;border:1px solid var(--ui-stroke-tertiary)}
.ag-muted{color:var(--ui-text-secondary);margin:0;font-size:12.5px}
.ag-err{color:color-mix(in srgb,var(--ui-red,#d0453f) 85%,var(--ui-text-primary))}
.ag :is(button,select,input):focus-visible{outline:2px solid var(--ui-accent);outline-offset:2px}
.ag-rise{animation:ag-rise .5s ease both}
@keyframes ag-rise{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
@container (max-width:1000px){.ag-grid3{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}.ag-kpis{grid-template-columns:repeat(3,minmax(0,1fr))}.ag-kpis div:nth-child(3){border-right:0}.ag-kpis div:nth-child(-n+3){border-bottom:1px solid var(--ui-stroke-tertiary)}}
@container (max-width:760px){.ag-grid2,.ag-grid3{grid-template-columns:minmax(0,1fr)}.ag-main{padding:16px}.ag-table .opt{display:none}.ag-cwrap{grid-template-columns:minmax(0,1fr)}.ag-core{display:none}}
@container (max-width:480px){.ag-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.ag-kpis div{border-right:0!important;border-bottom:1px solid var(--ui-stroke-tertiary)}.ag-bars li{grid-template-columns:76px minmax(0,1fr) 44px}}
.ag-lead{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px 28px;align-items:center}
.ag-lead h2{font:600 28px/1.15 var(--ag-display);letter-spacing:.005em;margin:0 0 8px;text-wrap:balance}
.ag-lead .meta{margin:0;color:var(--ui-text-secondary);font-size:12.5px}
.ag-stone{position:relative;width:232px}
.ag-stone svg{display:block;width:100%;height:auto}
.ag-stone figcaption{font-size:11px;color:var(--ui-text-secondary);text-align:center;margin-top:2px}
.ag-stone .band{cursor:pointer;transition:opacity .15s}
.ag-stone.dim .band:not(.on){opacity:.35}
.ag-kpis .lead span{font:600 26px/1 var(--ag-display)}
.ag-kpis .lead svg{display:block;margin-top:6px;width:100%;height:18px;overflow:visible}
.ag-kpis span{font-family:var(--ag-display)}
.ag-brand b{font:700 19px/1 var(--ag-display);letter-spacing:.06em}
.ag-scale{display:inline-flex;align-items:center;gap:3px}
.ag-scale i{width:12px;height:10px;border-radius:2px;display:inline-block}
.ag-scale i.z{background:transparent;border:1px solid var(--ui-stroke-secondary)}
.ag-table tbody tr:not(.grp):hover td{background:var(--ui-control-hover-background)}
.ag-table tr.grp td{position:sticky;top:0;z-index:1;background:linear-gradient(var(--ui-bg-card),var(--ui-bg-card)),var(--background,var(--ui-bg-elevated,#0d1117));font:600 11.5px var(--ag-mono);color:var(--ui-text-primary);padding-top:12px;border-bottom:1px solid var(--ui-stroke-secondary)}
.ag-table tr.grp em{font-style:normal;font-weight:400;color:var(--ui-text-secondary);margin-left:8px}
.ag-tag{display:inline-block;font:600 10px/1.5 var(--ag-mono);font-style:normal;padding:0 5px;margin-left:6px;border-radius:4px;border:1px solid var(--ui-stroke-tertiary);color:var(--ui-text-secondary);vertical-align:1px;white-space:nowrap}
.ag-tag.agent{color:var(--ag-seq);border-color:color-mix(in oklab,var(--ag-seq) 45%,transparent)}
.ag-tag.rv{margin:0 7px 0 0;color:var(--ui-red,#d0453f);border-color:color-mix(in oklab,var(--ui-red,#d0453f) 45%,transparent)}
.ag-pr{color:var(--ui-text-secondary);font:12px var(--ag-mono)}
.ag-table tr.mg td{color:var(--ui-text-secondary)}
.ag-kind i.mg{background:transparent;border:1.5px solid var(--ui-text-secondary);width:6px;height:6px}
.ag-who .t{display:flex}.ag-who .t i{border-radius:0}.ag-who .t i:last-child{border-radius:0 4px 4px 0}
.ag-who .t i.co,.ag-key .sw.co{background:repeating-linear-gradient(135deg,var(--ag-seq) 0 2px,transparent 2px 4px);opacity:.75}
.ag-key{display:flex;align-items:center;gap:6px;margin:10px 0 0;font-size:11.5px}.ag-key .sw{width:12px;height:8px;border-radius:2px;background:var(--ag-seq);display:inline-block}.ag-key .sw.co{margin-left:8px}
.ag-files li>span:first-child small{color:var(--ui-text-secondary);font-size:11px}
.ag-files li{grid-template-columns:minmax(0,1.6fr) minmax(0,1fr) 40px}
.ag-rng{display:block;color:var(--ui-text-secondary);font:10.5px var(--ag-mono)}
.ag-rel{list-style:none;margin:0;padding:0;display:flex;flex-direction:column}
.ag-rel li{display:grid;grid-template-columns:minmax(70px,auto) 84px minmax(0,1fr);gap:10px;align-items:baseline;padding:6px 0;border-top:1px solid var(--ui-stroke-tertiary);font-size:12.5px}
.ag-story{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:2px 20px}
.ag-story li{padding:7px 8px;border-radius:6px;font-size:12.8px;line-height:1.5}
.ag-story li b{display:block;font-size:11px;letter-spacing:.05em;text-transform:uppercase;color:var(--ui-text-secondary);margin-bottom:2px}
.ag-story li[data-era]{cursor:pointer}.ag-story li[data-era]:hover,.ag-story li[data-era]:focus-visible,.ag-story li.on{background:var(--ui-control-active-background);outline:none}
.ag-rel li:first-child{border-top:0}.ag-rel b{font:600 12px var(--ag-mono)}.ag-rel time{font:12px var(--ag-mono);color:var(--ui-text-secondary)}
.ag-rel .ag-muted{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ag-sdlc p.ev{display:flex;align-items:center;gap:8px;font:11.5px var(--ag-mono)}
.ag-meter{flex:0 0 64px;height:6px;border-radius:3px;background:var(--ui-stroke-tertiary);overflow:hidden}.ag-meter i{display:block;height:100%;border-radius:3px}
.ag-span{font-style:normal;color:var(--ui-text-secondary)}
.ag-prov{margin:18px 0 0;font:11.5px/1.6 var(--ag-mono);color:var(--ui-text-secondary);overflow-wrap:anywhere}
.ag-scope{display:inline-block;font:500 11px/1.5 var(--ag-mono);padding:0 6px;margin-right:7px;border-radius:4px;border:1px solid var(--ui-stroke-tertiary);color:var(--ui-text-secondary);vertical-align:1px}
.ag-tools{flex-wrap:nowrap}
.ag-ghost{position:relative;overflow:hidden;border:1px solid var(--ui-stroke-tertiary);border-radius:var(--ag-r);padding:28px;background:var(--ui-bg-card);display:flex;flex-direction:column;gap:8px;align-items:flex-start}
.ag-ghost>svg.bg{position:absolute;inset:auto 0 0 0;width:100%;height:60%;opacity:.16;pointer-events:none}
.ag-ghost b{font:600 20px/1.2 var(--ag-display)}
.ag-ghost span{color:var(--ui-text-secondary);max-width:520px;position:relative}
.ag-run svg{display:block;width:100%;height:auto}
.ag-runhead{display:flex;align-items:center;justify-content:space-between;gap:12px}
.ag-stall{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:8px 16px;border:1px solid color-mix(in srgb,var(--ui-red,#d0453f) 40%,var(--ui-stroke-tertiary));border-radius:var(--ag-r);padding:10px 14px;background:var(--ui-bg-card);font-size:13px}
.ag-sdlc .nm{display:flex;align-items:center;gap:8px;min-width:0}
.ag-sdlc .sev{font:600 10px/1 var(--ag-mono);text-transform:uppercase;letter-spacing:.05em;font-style:normal;padding:3px 5px;border-radius:4px;color:var(--ui-text-secondary);border:1px solid var(--ui-stroke-tertiary)}
.ag-sdlc .sev.s0{color:var(--ui-text-primary);border-color:var(--ui-text-secondary)}
.ag-sdlc li.fine .nm{color:var(--ui-text-secondary);font-size:12px;white-space:normal}
.ag-sdlc p{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.ag-sdlc p.ev{display:flex;white-space:nowrap}
.ag-tools .ag-select{flex:none}
.ag-kpis svg.spark{display:block;margin-top:6px;width:100%;height:14px;overflow:visible}
.ag-chip{font:500 12px var(--ag-mono);border:1px solid var(--ui-stroke-secondary);background:var(--ui-control-active-background);color:var(--ui-text-primary);border-radius:999px;padding:3px 10px;min-height:24px;cursor:pointer;white-space:nowrap}
.ag-cwrap{display:grid;grid-template-columns:auto minmax(0,1fr);gap:14px;align-items:start}
.ag-core{position:sticky;top:8px;display:flex;flex-direction:column;align-items:flex-start;gap:4px;padding-top:4px}
.ag-core small{font:600 10px var(--ag-mono);letter-spacing:.06em;text-transform:uppercase;color:var(--ui-text-secondary)}
.ag-core .layer{cursor:pointer;outline:none;transition:opacity .15s}
.ag-core .layer:focus-visible rect:first-of-type{stroke:var(--ui-accent)}
.ag-tw{min-width:0}
.ag-div{width:46px;height:10px;vertical-align:-1px;margin-right:6px}
.ag-div .add{fill:color-mix(in srgb,var(--ui-green,#2e9e5b) 80%,var(--ui-bg-card))}
.ag-div .del{fill:color-mix(in srgb,var(--ui-red,#d0453f) 75%,var(--ui-bg-card))}
.ag-div line{stroke:var(--ui-stroke-secondary);stroke-width:1}
.ag-run .now{animation:ag-pulse 1.4s ease-in-out infinite}
@keyframes ag-pulse{50%{opacity:.45}}
@container (max-width:760px){.ag-lead{grid-template-columns:minmax(0,1fr)}.ag-stone{width:200px;justify-self:center}.ag-lead h2{font-size:22px}}
@media (prefers-reduced-motion:reduce){.ag *{transition:none!important;animation:none!important}}
`

// ---------------------------------------------------------------------------- helpers

const num = n => Number(n || 0).toLocaleString()
const pctf = (n, t) => { const v = (n / (t || 1)) * 100; return n && v < 1 ? '<1%' : `${Math.round(v)}%` }
const short = n => (n >= 10000 ? `${Math.round(n / 1000)}k` : n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n))
const parseDay = s => { const [y, m, d] = String(s).split('-').map(Number); return new Date(Date.UTC(y, m - 1, d)) }
const fmtDay = s => { const d = parseDay(s); return `${MONTHS[d.getUTCMonth()]} ${d.getUTCDate()}` }
const fmtDayY = s => { const d = parseDay(s); return `${MONTHS[d.getUTCMonth()]} ${d.getUTCDate()}, ${d.getUTCFullYear()}` }
const fmtRange = (a, b, multiYear) => (a === b ? (multiYear ? fmtDayY(a) : fmtDay(a)) : `${multiYear ? fmtDayY(a) : fmtDay(a)} – ${multiYear ? fmtDayY(b) : fmtDay(b)}`)
const dayIndex = (first, s) => Math.round((parseDay(s) - parseDay(first)) / 864e5)
const argmax = a => a.reduce((bi, v, i) => (v > a[bi] ? i : bi), 0)
let uidN = 0
const useUid = p => useMemo(() => `${p}${++uidN}`, [])
const ERA_MIN = 10 // eras with at least this many commits get a number and a colour
const eraMin = d => (d && d.thresholds && d.thresholds.era_min_commits) || ERA_MIN

function useWidth(ref) {
  const [w, setW] = useState(0)
  useLayoutEffect(() => {
    if (!ref.current) return undefined
    setW(Math.round(ref.current.getBoundingClientRect().width))
    if (typeof ResizeObserver === 'undefined') return undefined
    const ro = new ResizeObserver(([e]) => setW(Math.round(e.contentRect.width)))
    ro.observe(ref.current)
    return () => ro.disconnect()
  }, [ref])
  return w
}

// Dark or light: read the luminance of the app's text colour, and re-check when the theme changes.
function useMode(ref) {
  const [mode, setMode] = useState('dark')
  useEffect(() => {
    const read = () => {
      if (!ref.current) return
      const m = getComputedStyle(ref.current).color.match(/[\d.]+/g)
      if (!m) return
      const [r, g, b] = m.map(Number)
      setMode(0.2126 * r + 0.7152 * g + 0.0722 * b > 128 ? 'dark' : 'light')
    }
    read()
    if (typeof MutationObserver === 'undefined') return undefined
    const mo = new MutationObserver(read)
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ['class', 'style', 'data-theme'] })
    if (document.body) mo.observe(document.body, { attributes: true, attributeFilter: ['class', 'style', 'data-theme'] })
    return () => mo.disconnect()
  }, [ref])
  return mode
}

// Monotone cubic through points (Fritsch–Carlson): smooth, never overshoots below zero.
function monotone(pts) {
  const n = pts.length
  if (n < 2) return pts.length ? `L${pts[0][0]},${pts[0][1]}` : ''
  const dx = [], s = [], m = new Array(n)
  for (let i = 0; i < n - 1; i++) { dx[i] = pts[i + 1][0] - pts[i][0]; s[i] = dx[i] ? (pts[i + 1][1] - pts[i][1]) / dx[i] : 0 }
  m[0] = s[0]; m[n - 1] = s[n - 2]
  for (let i = 1; i < n - 1; i++) m[i] = s[i - 1] * s[i] <= 0 ? 0 : (s[i - 1] + s[i]) / 2
  for (let i = 0; i < n - 1; i++) {
    if (s[i] === 0) { m[i] = 0; m[i + 1] = 0; continue }
    const a = m[i] / s[i], b = m[i + 1] / s[i], t = a * a + b * b
    if (t > 9) { const k = 3 / Math.sqrt(t); m[i] = k * a * s[i]; m[i + 1] = k * b * s[i] }
  }
  let d = ''
  for (let i = 0; i < n - 1; i++) {
    const h3 = dx[i] / 3
    d += `C${pts[i][0] + h3},${pts[i][1] + m[i] * h3} ${pts[i + 1][0] - h3},${pts[i + 1][1] - m[i + 1] * h3} ${pts[i + 1][0]},${pts[i + 1][1]}`
  }
  return d
}

// Calendar bins: days, ISO weeks (Mon–Sun) or calendar months. Each bin is placed at the
// commit-weighted centre of its days, so a curve never draws work inside a quiet stretch.
function binKey(s, unit) {
  if (unit === 'day') return s
  if (unit === 'month') return s.slice(0, 7)
  const d = parseDay(s), wd = (d.getUTCDay() + 6) % 7
  return new Date(d - wd * 864e5).toISOString().slice(0, 10)
}
function binDays(days, unit) {
  const out = []
  let cur = null
  days.forEach((d, i) => {
    const key = binKey(d.d, unit)
    if (!cur || cur.key !== key) { cur = { key, i, from: d.d, to: d.d, k: KINDS.map(() => 0), n: 0, ins: 0, del: 0, len: 0, w: 0, act: 0 }; out.push(cur) }
    cur.to = d.d; cur.len++
    let n = 0
    KINDS.forEach((_, j) => { const v = (d.k && d.k[j]) || 0; cur.k[j] += v; n += v })
    cur.n += n; cur.act += n ? 1 : 0; cur.w += i * n; cur.ins += d.ins || 0; cur.del += d.del || 0
  })
  out.forEach(b => {
    const [y, m] = b.key.split('-').map(Number)
    b.full = unit === 'day' ? 1 : unit === 'week' ? 7 : new Date(Date.UTC(y, m, 0)).getUTCDate()
    b.c = b.n ? b.w / b.n : b.i + (b.len - 1) / 2
  })
  if (out.length > 1) { const last = out[out.length - 1]; last.partial = last.len < last.full }
  return out
}

function Glyph({ size = 26 }) {
  const id = useUid('ag-iris-')
  return h('svg', { width: size, height: size, viewBox: '0 0 32 32', 'aria-hidden': true },
    h('defs', null, h('linearGradient', { id, x1: 0, y1: 0, x2: 1, y2: 1 },
      h('stop', { offset: '0', stopColor: '#00a2ce' }), h('stop', { offset: '.5', stopColor: '#8b61e3' }), h('stop', { offset: '1', stopColor: '#d84497' }))),
    h('rect', { width: 32, height: 32, rx: 7, fill: `url(#${id})` }),
    h('path', { d: 'M10.5 8v16M21.8 9.6C21.8 17 18 19.8 10.5 19.8', fill: 'none', stroke: '#0b0f16', strokeWidth: 2.9, strokeLinecap: 'round' }),
    h('circle', { cx: 10.5, cy: 8, r: 3.5, fill: '#0b0f16' }), h('circle', { cx: 10.5, cy: 24, r: 3.5, fill: '#0b0f16' }), h('circle', { cx: 21.8, cy: 9.6, r: 3.5, fill: '#0b0f16' }))
}

const TIP_W = 330 // matches .ag-tip max-width plus a margin
function Tip({ tip }) {
  if (!tip) return null
  const top = Math.max(0, tip.y - 12)
  if (tip.flip) return h('div', { className: 'ag-tip', style: { right: `calc(100% - ${tip.x - 14}px)`, top, width: 'max-content', maxWidth: TIP_W } }, tip.body)
  const left = Math.max(8, Math.min(tip.x + 14, (tip.w || 9999) - TIP_W))
  return h('div', { className: 'ag-tip', style: { left, top } }, tip.body)
}

function kindRows(k, pal, on) {
  const tot = k.reduce((a, b) => a + b, 0) || 1
  return KINDS.map((kk, j) => [kk, k[j], j]).filter(([, n, j]) => n && (!on || on[j])).sort((a, b) => b[1] - a[1])
    .map(([kk, n]) => h('div', { key: kk, className: 'r' }, h('i', { style: { background: pal[kk] } }), KIND_LABEL[kk], h('span', null, `${n} · ${pctf(n, tot)}`)))
}

// Tooltip handlers for mouse, pen and touch: a tap shows the tip, moving away hides it.
function tipOn(fn, leave) { return { onPointerMove: fn, onPointerDown: fn, onPointerLeave: leave } }

// The turning points worth naming: strong signals, newest first, at most ten. The strata
// rail numbers these same ten and the Turning points card lists them with those numbers.
const TOP_SIGNALS = 10
function topSignals(d) {
  const all = (d.signals || []).map((s, idx) => ({ ...s, idx }))
  const strong = all.filter(s => s.strength === 'strong')
  return (strong.length ? strong : all).slice(-TOP_SIGNALS).reverse().map((s, i) => ({ ...s, no: i + 1 }))
}

// A folded signal has an onset, a peak and an end; say all three when they differ.
function sigSpan(s, multiYear) {
  const f = multiYear ? fmtDayY : fmtDay
  const span = s.end && s.end !== s.d ? `${f(s.d)} – ${f(s.end)}` : f(s.d)
  return [s.strength, s.n > 1 ? `${s.n} readings, ${span}` : span, s.peak && s.peak !== s.d ? `peak ${f(s.peak)}` : ''].filter(Boolean).join(' · ')
}

function eraBody(c, no, pal, multiYear) {
  return [h('b', { key: 'h' }, no ? `Era ${no}${c.scope ? ` · ${c.scope}` : ''}` : 'Short burst'),
    h('div', { key: 'd' }, fmtRange(c.start, c.end, multiYear)),
    h('div', { key: 'n', style: { marginBottom: 4 } }, `${num(c.commits)} commit${c.commits === 1 ? '' : 's'} · ${c.active_days} active day${c.active_days === 1 ? '' : 's'}`),
    ...(c.k ? kindRows(c.k, pal).slice(0, 3) : []),
    c.author ? h('div', { key: 'a', className: 'ag-muted' }, c.author) : null]
}

// ---------------------------------------------------------------------------- agate (signature)

// The repo as a cut agate: one band per era, oldest at the rim and newest at the core,
// the way real agates fill from the outside in. Band width is √commits; each band is
// split around the stone by kind of work; quiet gaps of a week or more are dark seams.
function hashStr(s) { let x = 2166136261; for (const ch of String(s)) { x ^= ch.charCodeAt(0); x = Math.imul(x, 16777619) } return x >>> 0 }
function rng(seed) { let a = seed || 1; return () => { a = (a + 0x6d2b79f5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296 } }

// stone-layout:start (pure; tests/test_stone_layout.py evaluates this block in node)
// Lays each era's commits out as bands, rim (f=1) to core (f=core), oldest first.
// - Era thickness: a 3px floor, then a sqrt(commits) share of the rest, so small eras stay visible.
// - Inside an era every commit gets an equal slice of thickness, so each kind's band
//   thickness is its exact share of the era's commits.
// - Resolution follows pixels: one time-ordered chunk per ~3px of era thickness, never
//   finer than one commit. Inside a chunk the kind that continues from the previous chunk
//   goes first, then larger kinds, so runs merge into broad bands.
// - per: one striation per commit when a commit is >= 1.5px thick, else one solid band.
function stoneLayout(d, rad, core) {
  const eras = d.clusters || []
  const other = KINDS.length - 1
  const kindIdx = k => { const j = KINDS.indexOf(k); return j < 0 ? other : j }
  const expand = counts => { const seq = []; counts.map((n, j) => [n || 0, j]).filter(([n]) => n > 0).sort((x, y) => y[0] - x[0]).forEach(([n, j]) => { for (let q = 0; q < n; q++) seq.push(j) }); return seq }
  const byDay = {}
  ;[...(d.commits || [])].filter(x => x.kind !== 'merge').sort((x, y) => Date.parse(x.t) - Date.parse(y.t))
    .forEach(x => { (byDay[x.day] = byDay[x.day] || []).push(kindIdx(x.kind)) })
  const dayOrder = {}
  ;(d.days || []).forEach(day => {
    const tot = (day.k || []).reduce((a, b) => a + (b || 0), 0)
    dayOrder[day.d] = byDay[day.d] && byDay[day.d].length === tot ? byDay[day.d] : expand(day.k || [])
  })
  const weights = eras.map(c => Math.sqrt(Math.max(1, c.commits || 0)))
  const wsum = weights.reduce((a, b) => a + b, 0) || 1
  // Thin-era floor: every era starts with 3px (or an equal share when the stone cannot
  // fit 3px per era), then the rest is split by sqrt(commits). A 2-commit era beside a
  // 4,000-commit one stays a readable band instead of a sub-pixel line.
  const total = 1 - core
  const floor = eras.length ? Math.min(3 / rad, total / eras.length) : 0
  const spare = total - floor * eras.length
  let f = 1
  return eras.map((c, i) => {
    const f0 = f, f1 = f - floor - (weights[i] / wsum) * spare
    f = f1
    const kc = KINDS.map((_, j) => (c.k && c.k.some(Boolean) ? c.k[j] || 0 : j === other ? 1 : 0))
    let seq = []
    ;(d.days || []).filter(day => day.d >= c.start && day.d <= c.end).forEach(day => { seq = seq.concat(dayOrder[day.d] || []) })
    const sc = KINDS.map(() => 0)
    seq.forEach(j => { sc[j]++ })
    if (sc.some((v, j) => v !== kc[j])) seq = expand(kc) // day series disagrees with the era: trust the era's counts
    const n = seq.length || 1, span = f0 - f1
    const chunks = Math.max(1, Math.min(n, Math.floor((span * rad) / 3)))
    const ordered = []
    for (let q = 0; q < chunks; q++) {
      const part = seq.slice(Math.round((q * n) / chunks), Math.round(((q + 1) * n) / chunks))
      const cnt = {}
      part.forEach(j => { cnt[j] = (cnt[j] || 0) + 1 })
      const prev = ordered[ordered.length - 1]
      Object.keys(cnt).map(Number).sort((x, y) => (x === prev ? -1 : y === prev ? 1 : cnt[y] - cnt[x] || x - y)).forEach(j => { for (let r = 0; r < cnt[j]; r++) ordered.push(j) })
    }
    const runs = []
    ordered.forEach(j => { const last = runs[runs.length - 1]; if (last && last.j === j) last.n++; else runs.push({ j, n: 1 }) })
    const striate = (span / n) * rad >= 1.5
    let g = f0
    runs.forEach(run => { run.g0 = g; run.g1 = g - (run.n / n) * span; run.per = run.n > 1 && striate ? run.n : 1; g = run.g1 })
    return { f0, f1, chunks, n: seq.length, runs }
  })
}
// stone-layout:end

function Agate({ d, pal, eraNo, hl, setHl, multiYear }) {
  const [tip, setTip] = useState(null)
  const box = useRef(null)
  const gid = useUid('ag-stone-')
  const S = 232, C = S / 2, RAD = 104, CORE = 0.17, N = 160
  const eras = d.clusters || []
  const shape = useMemo(() => {
    const r = rng(hashStr(d.project))
    const waves = [2, 3, 4, 5, 7].map((f, i) => ({ f, a: [0.07, 0.05, 0.03, 0.02, 0.012][i] * (0.6 + r() * 0.8), p: r() * Math.PI * 2, q: r() * Math.PI * 2 }))
    return (t, f) => 1 + waves.reduce((acc, w, i) => acc + w.a * Math.sin(w.f * t + (i % 2 ? w.q * (1 - f) + w.p * f : w.p)), 0) * Math.pow(f, 0.6)
  }, [d.project])
  const pt = (t, f) => { const rr = RAD * f * shape(t, f); return [C + rr * Math.cos(t), C + rr * Math.sin(t)] }
  const ring = (f0, f1, a0, a1) => {
    const steps = Math.max(2, Math.ceil(((a1 - a0) / (Math.PI * 2)) * N))
    const outer = [], inner = []
    for (let s = 0; s <= steps; s++) { const t = a0 + ((a1 - a0) * s) / steps; outer.push(pt(t, f0)); inner.push(pt(t, f1)) }
    inner.reverse()
    return `M${outer.map(p => p.map(v => v.toFixed(1)).join(',')).join('L')}L${inner.map(p => p.map(v => v.toFixed(1)).join(',')).join('L')}Z`
  }
  const loop = f => { const p = []; for (let s = 0; s < N; s++) p.push(pt((s / N) * Math.PI * 2, f)); return `M${p.map(q => q.map(v => v.toFixed(1)).join(',')).join('L')}Z` }

  const layout = useMemo(() => stoneLayout(d, RAD, CORE), [d])
  const bands = [], seams = []
  layout.forEach(({ f0, f1, runs }, i) => {
    const c = eras[i]
    const pale = !eraNo[i]
    const on = hl === i
    const tip = e => { setHl(i); const bb = box.current.getBoundingClientRect(); setTip({ x: e.clientX - bb.left, y: e.clientY - bb.top, flip: true, body: eraBody(c, eraNo[i], pal, multiYear) }) }
    runs.forEach((run, s0) => {
      const kind = KINDS[run.j], milky = kind === 'other'
      const op = (milky ? 0.6 : 1) * (pale ? 0.72 : 1)
      for (let q = 0; q < run.per; q++) {
        const a0 = run.g0 - ((run.g0 - run.g1) * q) / run.per, a1 = run.g0 - ((run.g0 - run.g1) * (q + 1)) / run.per
        bands.push(h('path', { key: `b${i}-${s0}-${q}`, d: ring(a0, a1, 0, Math.PI * 2), fill: milky ? CHALCEDONY : pal[kind], fillOpacity: op * (q % 2 ? 0.8 : 1), className: `band${on ? ' on' : ''}`,
          onPointerMove: tip, onPointerLeave: () => { setHl(null); setTip(null) }, onClick: () => setHl(i) }))
      }
    })
    if (i > 0) seams.push(h('path', { key: `e${i}`, d: loop(f0), fill: 'none', stroke: '#fff', strokeOpacity: 0.6, strokeWidth: 0.7, pointerEvents: 'none' }))
    const next = eras[i + 1]
    if (next && dayIndex(c.end, next.start) - 1 >= 7) seams.push(h('path', { key: `s${i}`, d: loop(f1), fill: 'none', stroke: '#0b0f16', strokeOpacity: 0.7, strokeWidth: 1.1, pointerEvents: 'none' }))
  })
  const big = eras.filter(c => c.commits >= eraMin(d)).length
  return h('figure', { className: `ag-stone${hl != null ? ' dim' : ''}`, ref: box, style: { margin: 0 } },
    h('svg', { viewBox: `0 0 ${S} ${S}`, role: 'img', 'aria-label': `Agate cross-section: ${eras.length} eras as bands, oldest at the rim.` },
      h('defs', null,
        h('radialGradient', { id: `${gid}-core`, cx: '45%', cy: '40%', r: '70%' }, h('stop', { offset: 0, stopColor: '#2a2440' }), h('stop', { offset: 1, stopColor: '#07090e' })),
        h('radialGradient', { id: `${gid}-sheen`, cx: '30%', cy: '25%', r: '75%' }, h('stop', { offset: 0, stopColor: '#fff', stopOpacity: 0.22 }), h('stop', { offset: 0.55, stopColor: '#fff', stopOpacity: 0 })),
        h('filter', { id: `${gid}-grain`, x: 0, y: 0, width: '100%', height: '100%' },
          h('feTurbulence', { type: 'fractalNoise', baseFrequency: 0.85, numOctaves: 2, seed: hashStr(d.project) % 97, stitchTiles: 'stitch' }),
          h('feColorMatrix', { type: 'saturate', values: 0 }), h('feComposite', { operator: 'in', in2: 'SourceGraphic' }))),
      h('path', { d: loop(1.035), fill: '#0b0f16', opacity: 0.9 }),
      h('path', { d: loop(1), fill: CHALCEDONY }),
      h('g', null, bands),
      h('path', { d: loop(CORE), fill: `url(#${gid}-core)` }),
      h('g', null, seams),
      h('path', { d: loop(1.012), fill: 'none', stroke: '#7fd6f0', strokeOpacity: 0.55, strokeWidth: 1.4, pointerEvents: 'none' }),
      h('path', { d: loop(1), fill: `url(#${gid}-sheen)`, pointerEvents: 'none' }),
      h('path', { d: loop(1), fill: '#fff', filter: `url(#${gid}-grain)`, opacity: 0.07, pointerEvents: 'none', style: { mixBlendMode: 'overlay' } })),
    h('figcaption', null, `Eras as bands, oldest at the rim`),
    h(Tip, { tip }))
}

// ---------------------------------------------------------------------------- strata (hero)

function Strata({ d, pal, eraNo, hl, setHl, multiYear, sig, setSig }) {
  const box = useRef(null)
  const uid = useUid('ag-s')
  const width = useWidth(box)
  // A short history reads better by day; a long one by month. Weeks for everything between.
  const [bin, setBin] = useState(() => {
    const span = (Date.parse(d.last) - Date.parse(d.first)) / 864e5
    return !(span >= 0) ? 'week' : span < 35 ? 'day' : span > 730 ? 'month' : 'week'
  })
  const [off, setOff] = useState({})
  const [tip, setTip] = useState(null)
  const [cur, setCur] = useState(null)
  const bins = useMemo(() => binDays(d.days || [], bin), [d, bin])
  const on = KINDS.map(k => !off[k])
  const W = Math.max(320, width || 960)
  const narrow = W < 620
  const first = d.first
  const known = new Set(SIGNAL_ROWS)
  const rowsUsed = [...SIGNAL_ROWS.filter(r => (d.signals || []).some(s => s.type === r)), ...((d.signals || []).some(s => !known.has(s.type)) ? ['other'] : [])]
  const L = 40, R = 14, T = 34, eraH = 12, B = 26
  const sigH = narrow || !rowsUsed.length ? 0 : rowsUsed.length * 16 + 12
  const ih = narrow ? 220 : 300
  const H = T + ih + B + sigH
  const iw = W - L - R
  const nDays = Math.max(1, (d.days || []).length)
  const xDay = i => L + (i / Math.max(1, nDays - 1)) * iw
  const xBin = b => xDay(b.c)
  const stacks = bins.map(b => { let acc = 0; return KINDS.map((_, j) => { const lo = acc; acc += on[j] ? b.k[j] : 0; return [lo, acc] }) })
  const ymax = Math.max(1, ...stacks.map(s => s[s.length - 1][1]))
  const y = v => T + ih - (v / ymax) * ih

  const grid = []
  const ystep = [1, 2, 5, 10, 20, 25, 50, 100, 200, 500, 1000].find(st => ymax / st <= 4) || Math.ceil(ymax / 4)
  for (let v = 0; v <= ymax; v += ystep) {
    grid.push(h('line', { key: 'gy' + v, x1: L, x2: W - R, y1: y(v), y2: y(v), stroke: 'var(--ui-stroke-tertiary)', strokeWidth: v ? 0.6 : 1, strokeDasharray: v ? '2 4' : undefined }))
    grid.push(h('text', { key: 'ty' + v, x: L - 7, y: y(v) + 3.5, textAnchor: 'end' }, String(v)))
  }
  const f0 = parseDay(first)
  let lastX = -99
  for (let mth = 0; mth < 400; mth++) {
    const md = new Date(Date.UTC(f0.getUTCFullYear(), f0.getUTCMonth() + mth, 1))
    const idx = Math.round((md - f0) / 864e5)
    if (idx > nDays - 1) break
    if (idx < 0) continue
    const xx = xDay(idx)
    if (xx - lastX < 46) continue
    lastX = xx
    grid.push(h('line', { key: 'mx' + mth, x1: xx, x2: xx, y1: T, y2: T + ih, stroke: 'var(--ui-stroke-tertiary)', strokeWidth: 0.6 }))
    grid.push(h('text', { key: 'mt' + mth, x: xx + 3, y: T + ih + 16 }, md.getUTCMonth() === 0 ? String(md.getUTCFullYear()) : MONTHS[md.getUTCMonth()]))
  }

  const gapIdx = (d.gaps || []).map(g => [dayIndex(first, g.start), dayIndex(first, g.end)])
  const gaps = gapIdx.map(([a, b], i) => h('rect', { key: 'gap' + i, x: xDay(a), y: T, width: Math.max(2, xDay(b) - xDay(a)), height: ih, fill: `url(#${uid}-hatch)`, opacity: 0.9 }))

  // Points: one per bin, plus zero anchors at both edges of every quiet gap, so the
  // smoothing can't carry work into a stretch where nothing happened.
  const zero = KINDS.map(() => [0, 0])
  const pts = bins.map((b, i) => ({ x: xBin(b), s: stacks[i] }))
  if (bin !== 'day') gapIdx.forEach(([a, b]) => { pts.push({ x: xDay(a), s: zero }); pts.push({ x: xDay(b), s: zero }) })
  pts.sort((a, b) => a.x - b.x)

  const layers = [], edges = [], clips = []
  if (pts.length > 1) {
    KINDS.forEach((k, j) => {
      if (!on[j]) return
      const top = pts.map(p => [p.x, y(p.s[j][1])])
      const bot = pts.map(p => [p.x, y(p.s[j][0])]).reverse()
      const dd = `M${top[0][0]},${top[0][1]}${monotone(top)}L${bot[0][0]},${bot[0][1]}${monotone(bot)}Z`
      layers.push(h('path', { key: k, d: dd, fill: `url(#${uid}-g-${k})`, stroke: 'var(--ui-bg-card)', strokeWidth: 0.6, strokeLinejoin: 'round' }))
      edges.push(h('path', { key: 'e' + k, d: `M${top[0][0]},${top[0][1]}${monotone(top)}`, fill: 'none', stroke: `color-mix(in oklab, ${pal[k]} 62%, white)`, strokeWidth: 0.8, strokeOpacity: 0.9, pointerEvents: 'none' }))
      clips.push(h('path', { key: 'c' + k, d: dd }))
    })
  }

  // Partial last bin: the period isn't over, so a drop there is not a decline.
  const lastBin = bins[bins.length - 1]
  const partial = lastBin && lastBin.partial && bin !== 'day'
    ? h('g', { pointerEvents: 'none' },
      h('rect', { x: xDay(lastBin.i), y: T, width: Math.max(2, W - R - xDay(lastBin.i)), height: ih, fill: 'var(--ui-bg-card)', opacity: 0.55 }),
      h('line', { x1: xDay(lastBin.i), x2: xDay(lastBin.i), y1: T, y2: T + ih, stroke: 'var(--ui-text-secondary)', strokeDasharray: '3 3', strokeWidth: 1 }),
      h('text', { x: xDay(lastBin.i) - 5, y: T + 12, textAnchor: 'end', style: { fontSize: '9.5px' } }, `${bin === 'week' ? 'week' : 'month'} so far`))
    : null

  const show = (e, body) => { const bb = box.current.getBoundingClientRect(); setTip({ x: e.clientX - bb.left, y: e.clientY - bb.top, w: bb.width, body }) }

  // Eras rail: numbered and tinted by their main kind of work when big enough; short bursts are ticks.
  const eraY = T - eraH - 8
  const eras = (d.clusters || []).map((c, i) => {
    const a = xDay(dayIndex(first, c.start)), b = xDay(dayIndex(first, c.end)), w = Math.max(3, b - a)
    const no = eraNo[i], k = KINDS[argmax(c.k || [0])], isOn = hl === i
    const handlers = { className: 'hit', ...tipOn(e => { setHl(i); show(e, eraBody(c, no, pal, multiYear)) }, () => { setHl(null); setTip(null) }) }
    // 24px-tall invisible target so thin ticks and short eras are easy to hit.
    const target = h('rect', { x: a - Math.max(0, (12 - w) / 2), y: eraY - 6, width: Math.max(12, w), height: 24, fill: 'transparent' })
    if (!no) return h('g', { key: 'era' + i, ...handlers }, target,
      h('rect', { x: a, y: eraY + eraH - 4, width: w, height: 4, rx: 1.5, fill: 'var(--ui-text-primary)', fillOpacity: isOn ? 0.7 : 0.3 }))
    return h('g', { key: 'era' + i, ...handlers }, target,
      h('rect', { x: a, y: eraY, width: w, height: eraH, rx: 3, fill: pal[k], fillOpacity: hl == null || isOn ? 0.92 : 0.4, stroke: isOn ? 'var(--ui-text-primary)' : 'none', strokeWidth: 1.2 }),
      w >= 14 ? h('text', { x: a + w / 2, y: eraY + eraH - 2.5, textAnchor: 'middle', style: { fontSize: '9px', fontWeight: 700, fill: '#fff', pointerEvents: 'none' } }, String(no)) : null)
  })
  const hlc = hl != null && (d.clusters || [])[hl]
  const hlBand = hlc ? h('rect', { x: xDay(dayIndex(first, hlc.start)) - 2, y: T, width: Math.max(4, xDay(dayIndex(first, hlc.end)) - xDay(dayIndex(first, hlc.start)) + 4), height: ih, fill: 'var(--ui-text-primary)', opacity: 0.07, pointerEvents: 'none' }) : null

  // Signals rail: one row per kind of signal present. The top ten (strong, newest first)
  // are numbered like the Turning points card; the rest are small and dimmed.
  const sigY = T + ih + B + 8
  const top = topSignals(d), rank = new Map(top.map(s => [s.idx, s.no]))
  const sigTip = (s, no) => e => { setSig(s.idx); show(e, [h('b', { key: 'h' }, `${no ? `#${no} · ` : ''}${SIGNAL_LABEL[s.type] || 'Other'} · ${multiYear ? fmtDayY(s.d) : fmtDay(s.d)}`), h('div', { key: 'd' }, s.detail), h('div', { key: 's', className: 'ag-muted' }, sigSpan(s, multiYear))]) }
  // Numbered badges sit 15px apart at least: close ones are pushed right (then pulled back
  // inside the plot) with a short leader to their true date.
  const spread = new Map()
  {
    const byRow = new Map()
    top.forEach(s => {
      const r = rowsUsed.indexOf(known.has(s.type) ? s.type : 'other')
      if (r < 0) return
      if (!byRow.has(r)) byRow.set(r, [])
      byRow.get(r).push({ idx: s.idx, x: xDay(Math.max(0, Math.min(nDays - 1, dayIndex(first, s.d)))) })
    })
    for (const row of byRow.values()) {
      row.sort((a, b) => a.x - b.x)
      const xs = row.map(m => m.x)
      for (let k = 1; k < xs.length; k++) xs[k] = Math.max(xs[k], xs[k - 1] + 15)
      const over = xs.length ? xs[xs.length - 1] - (W - R - 7) : 0
      if (over > 0) for (let k = xs.length - 1; k >= 0; k--) xs[k] = Math.min(xs[k] - over, k < xs.length - 1 ? xs[k + 1] - 15 : Infinity)
      row.forEach((m, k) => spread.set(m.idx, xs[k]))
    }
  }
  const relTip = r => e => show(e, [h('b', { key: 'h' }, `Release ${r.name}`), h('div', { key: 'd' }, multiYear ? fmtDayY(r.d) : fmtDay(r.d)),
    h('div', { key: 's', className: 'ag-muted' }, r.on_history ? r.sha : `${r.sha} · on another branch`)])
  const rels = (d.releases || []).filter(r => r.d >= d.first && r.d <= d.last).map((r, i) => {
    const xx = xDay(dayIndex(first, r.d))
    return h('g', { key: 'rl' + i, className: 'hit', ...tipOn(relTip(r), () => setTip(null)) },
      h('rect', { x: xx - 6, y: T + ih, width: 12, height: 10, fill: 'transparent' }),
      h('path', { d: `M${xx},${T + ih + 1.5}L${xx + 3},${T + ih + 6.5}L${xx - 3},${T + ih + 6.5}Z`, fill: 'var(--ui-text-primary)', opacity: r.on_history ? 0.75 : 0.35 }))
  })
  const sigMarks = (d.signals || []).map((s, i) => {
    const ri = rowsUsed.indexOf(known.has(s.type) ? s.type : 'other')
    if (ri < 0) return null
    const x0 = xDay(Math.max(0, Math.min(nDays - 1, dayIndex(first, s.d)))), yy = sigY + ri * 16, no = rank.get(i), isOn = sig === i
    const xx = no ? (spread.get(i) ?? x0) : x0
    return { i, no, el: h('g', { key: 'sg' + i, className: 'hit', ...tipOn(sigTip({ ...s, idx: i }, no), () => { setSig(null); setTip(null) }) },
      h('circle', { cx: xx, cy: yy, r: 12, fill: 'transparent' }),
      no && xx !== x0 ? h('line', { x1: x0, x2: xx, y1: yy + 5, y2: yy + 2, stroke: 'var(--ui-text-secondary)', strokeWidth: 0.8 }) : null,
      no ? [h('circle', { key: 'c', cx: xx, cy: yy, r: isOn ? 8 : 6.5, fill: 'var(--ui-text-primary)', stroke: 'var(--ui-bg-card)', strokeWidth: 1.5 }),
        h('text', { key: 't', x: xx, y: yy + 3, textAnchor: 'middle', style: { fontSize: no > 9 ? '7px' : '8.5px', letterSpacing: no > 9 ? '-0.04em' : undefined, fontWeight: 700, fill: 'var(--ui-bg-card)', pointerEvents: 'none' } }, String(no))]
        : h('path', { d: `M${xx},${yy - 2.6}L${xx + 2.6},${yy}L${xx},${yy + 2.6}L${xx - 2.6},${yy}Z`, fill: 'var(--ui-text-secondary)', opacity: isOn ? 0.9 : 0.4 })) }
  }).filter(Boolean)
  const signals = !sigH ? [] : [
    ...rowsUsed.map((r, ri) => h('text', { key: 'sl' + r, x: L - 7, y: sigY + ri * 16 + 3.5, textAnchor: 'end', style: { fontSize: '10px' } }, SIGNAL_LABEL[r] || 'Other')),
    ...rowsUsed.map((r, ri) => h('line', { key: 'sr' + r, x1: L, x2: W - R, y1: sigY + ri * 16, y2: sigY + ri * 16, stroke: 'var(--ui-stroke-tertiary)', strokeWidth: 0.6 })),
    // numbered markers last so they sit on top of the dimmed ones
    ...sigMarks.filter(m => !m.no).map(m => m.el), ...sigMarks.filter(m => m.no).sort((a, b) => b.no - a.no).map(m => m.el)
  ]

  const tipAt = (bi, px, py, bw) => {
    const b = bins[bi]
    const rows = kindRows(b.k, pal, on)
    setCur(bi)
    setTip({
      x: px, y: py, w: bw, cx: xBin(b),
      body: [h('b', { key: 'h' }, bin === 'day' ? fmtDayY(b.from) : `${fmtRange(b.from, b.to, multiYear)}${b.partial ? ' (so far)' : ''}`),
        h('div', { key: 'n', style: { marginBottom: 4 } }, `${num(b.n)} commit${b.n === 1 ? '' : 's'} · `, h('span', { className: 'ag-add' }, `+${short(b.ins)}`), ' ', h('span', { className: 'ag-del' }, `−${short(b.del)}`)),
        ...rows, rows.length ? null : h('div', { key: 'q', className: 'ag-muted' }, 'Quiet')]
    })
  }
  const hover = e => {
    if (!bins.length) return
    const svg = e.currentTarget.ownerSVGElement.getBoundingClientRect()
    const sx = ((e.clientX - svg.left) / svg.width) * W
    let best = 0, bd = Infinity
    bins.forEach((b, i) => { const dd = Math.abs(xBin(b) - sx); if (dd < bd) { bd = dd; best = i } })
    const bb = box.current.getBoundingClientRect()
    tipAt(best, e.clientX - bb.left, e.clientY - bb.top, bb.width)
  }
  const key = e => {
    if (!bins.length) return
    const step = { ArrowRight: 1, ArrowLeft: -1, End: bins.length, Home: -bins.length }[e.key]
    if (step == null) return
    e.preventDefault()
    const bi = Math.max(0, Math.min(bins.length - 1, (cur == null ? (step > 0 ? -1 : bins.length) : cur) + step))
    const bb = box.current.getBoundingClientRect(), sx = (xBin(bins[bi]) / W) * bb.width
    tipAt(bi, sx, (T / H) * bb.height * 3, bb.width)
  }

  const totals = d.kind_totals || [], tsum = totals.reduce((a, b) => a + b, 0)
  return h('section', { className: 'ag-card ag-rise' },
    h('div', { className: 'ag-chead' },
      h('div', null, h('h3', null, 'The strata'), h('p', { className: 'ag-sub' }, 'Every commit, stacked by the kind of work it was. Hatched stretches went quiet.')),
      h('div', { className: 'ag-tabs', role: 'group', 'aria-label': 'Bin size' },
        [['day', 'Days'], ['week', 'Weeks'], ['month', 'Months']].map(([v, l]) =>
          h('button', { key: v, type: 'button', 'aria-pressed': bin === v, onClick: () => { setBin(v); setCur(null); setTip(null) } }, l)))),
    h('div', { className: 'ag-legend', role: 'group', 'aria-label': 'Work types shown' },
      KINDS.map((k, j) => h('button', { key: k, type: 'button', 'aria-pressed': on[j], onClick: () => setOff(o => ({ ...o, [k]: !o[k] })) },
        h('i', { style: { background: pal[k] } }), KIND_LABEL[k], h('em', null, `${num(totals[j])} · ${pctf(totals[j] || 0, tsum)}`)))),
    h('div', { className: 'ag-chart', ref: box, style: { marginTop: 8 } },
      h('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': `Commits over time by work type, ${d.first} to ${d.last}. ${num(d.commit_count)} commits in ${(d.clusters || []).length} eras. Focus the chart and use the arrow keys to step through ${bin}s.` },
        h('defs', null,
          h('pattern', { id: `${uid}-hatch`, width: 6, height: 6, patternUnits: 'userSpaceOnUse', patternTransform: 'rotate(45)' },
            h('line', { x1: 0, y1: 0, x2: 0, y2: 6, stroke: 'var(--ui-stroke-secondary)', strokeWidth: 1.4 })),
          KINDS.map(k => h('linearGradient', { key: k, id: `${uid}-g-${k}`, x1: 0, y1: 0, x2: 0, y2: 1 },
            h('stop', { offset: 0, stopColor: pal[k], stopOpacity: 0.97 }), h('stop', { offset: 1, stopColor: pal[k], stopOpacity: 0.74 }))),
          h('clipPath', { id: `${uid}-clip` }, clips),
          h('filter', { id: `${uid}-grain`, x: 0, y: 0, width: '100%', height: '100%' },
            h('feTurbulence', { type: 'fractalNoise', baseFrequency: 0.9, numOctaves: 2, stitchTiles: 'stitch' }), h('feColorMatrix', { type: 'saturate', values: 0 }), h('feComposite', { operator: 'in', in2: 'SourceGraphic' }))),
        h('text', { x: L, y: eraY - 5, style: { fontSize: '9.5px' } }, 'ERAS'),
        h('g', null, gaps), h('g', null, grid), hlBand, h('g', null, layers),
        h('rect', { x: L, y: T, width: iw, height: ih, fill: '#fff', filter: `url(#${uid}-grain)`, clipPath: `url(#${uid}-clip)`, opacity: 0.06, pointerEvents: 'none', style: { mixBlendMode: 'overlay' } }),
        h('g', null, edges), partial, h('g', null, eras), h('g', null, signals), h('g', null, rels),
        tip && tip.cx != null ? h('line', { x1: tip.cx, x2: tip.cx, y1: T, y2: T + ih, stroke: 'var(--ui-text-primary)', strokeWidth: 1, strokeDasharray: '3 3', pointerEvents: 'none' }) : null,
        h('rect', { className: 'hit', x: L, y: T, width: iw, height: ih, fill: 'transparent', tabIndex: 0, 'aria-label': 'Strata chart, use arrow keys',
          onPointerMove: hover, onPointerDown: hover, onPointerLeave: () => setTip(null), onKeyDown: key, onBlur: () => { setTip(null); setCur(null) } })),
      h(Tip, { tip })),
    h('div', { className: 'ag-foot' },
      h('span', null, `Top band: ${(d.clusters || []).length} eras, ${eraNo.filter(Boolean).length} with ${eraMin(d)}+ commits numbered and coloured by their main kind.${(d.releases || []).length ? ` Ticks under the axis: ${d.releases.length} releases.` : ''}`, sigH ? ` Bottom rail: ${(d.signals || []).length} signals; the ${top.length} numbered ones are the Turning points.` : ''),
      h('span', null, `${fmtDayY(d.first)} – ${fmtDayY(d.last)}`)))
}

// ---------------------------------------------------------------------------- rhythm heatmap

const STEPS = [20, 38, 56, 76, 96] // % of the sequential hue for the five count steps

function Rhythm({ d }) {
  const box = useRef(null)
  const width = useWidth(box)
  const [tip, setTip] = useState(null)
  const R = d.rhythm || []
  const max = Math.max(1, ...R.flat())
  // Marginal bars: weekday totals on the right, hour totals along the bottom.
  const W = Math.max(300, width || 640), L = 34, T = 4, MR = 52, MB = 26, B = 20
  const cw = (W - L - MR - 2) / 24, ch = Math.min(26, Math.max(16, cw * 0.9)), gy = T + ch * 7, H = gy + MB + B
  const dayTot = DAYS.map((_, di) => (R[di] || []).reduce((a, b) => a + b, 0))
  const hourTot = Array.from({ length: 24 }, (_, hr) => R.reduce((a, row) => a + (row[hr] || 0), 0))
  const dMax = Math.max(1, ...dayTot), hMax = Math.max(1, ...hourTot)
  const step = n => (n ? Math.min(5, Math.max(1, Math.ceil(5 * Math.pow(n / max, 0.6)))) : 0)
  const bounds = [1, 2, 3, 4, 5].map(s => Math.max(1, Math.ceil(max * Math.pow((s - 1) / 5, 1 / 0.6) + 1e-9)))
  let peak = [0, 0, 0]
  R.forEach((row, di) => row.forEach((n, hr) => { if (n > peak[0]) peak = [n, di, hr] }))
  const at = (e, body) => { const bb = box.current.getBoundingClientRect(); setTip({ x: e.clientX - bb.left, y: e.clientY - bb.top, w: bb.width, body }) }
  const leave = () => setTip(null)
  const cells = []
  R.forEach((row, di) => row.forEach((n, hr) => {
    const s = step(n), isPeak = n && n === peak[0] && di === peak[1] && hr === peak[2]
    cells.push(h('rect', {
      key: `${di}-${hr}`, x: L + hr * cw + 1.5, y: T + di * ch + 1.5, width: cw - 3, height: ch - 3, rx: 3, className: 'hit',
      fill: s ? `color-mix(in oklab, var(--ag-seq) ${STEPS[s - 1]}%, var(--ui-bg-card))` : 'transparent',
      stroke: isPeak ? 'var(--ui-text-primary)' : s ? 'none' : 'var(--ui-stroke-tertiary)', strokeWidth: isPeak ? 1.6 : 0.8,
      ...tipOn(e => at(e, [h('b', { key: 'h' }, `${DAYS[di]} ${String(hr).padStart(2, '0')}:00`), h('div', { key: 'n' }, `${n} commit${n === 1 ? '' : 's'}`)]), leave)
    }))
  }))
  const bar = 'color-mix(in oklab, var(--ag-seq) 55%, var(--ui-bg-card))'
  const margins = [
    ...dayTot.map((n, di) => h('g', { key: 'md' + di, className: 'hit', ...tipOn(e => at(e, [h('b', { key: 'h' }, `Every ${DAYS[di]}`), h('div', { key: 'n' }, `${num(n)} commits · ${pctf(n, dayTot.reduce((a, b) => a + b, 0))}`)]), leave) },
      h('rect', { x: W - MR + 4, y: T + di * ch, width: MR - 4, height: ch, fill: 'transparent' }),
      h('rect', { x: W - MR + 6, y: T + di * ch + ch * 0.25, width: Math.max(n ? 1.5 : 0, (n / dMax) * (MR - 12)), height: ch * 0.5, rx: 2, fill: bar }))),
    ...hourTot.map((n, hr) => h('g', { key: 'mh' + hr, className: 'hit', ...tipOn(e => at(e, [h('b', { key: 'h' }, `${String(hr).padStart(2, '0')}:00 – ${String(hr).padStart(2, '0')}:59`), h('div', { key: 'n' }, `${num(n)} commits across all days`)]), leave) },
      h('rect', { x: L + hr * cw, y: gy + 2, width: cw, height: MB - 2, fill: 'transparent' }),
      h('rect', { x: L + hr * cw + cw * 0.22, y: gy + MB - 2 - (n / hMax) * (MB - 6), width: cw * 0.56, height: Math.max(n ? 1.5 : 0, (n / hMax) * (MB - 6)), rx: 1.5, fill: bar })))
  ]
  const labels = [
    ...DAYS.map((dn, i) => h('text', { key: 'd' + i, x: L - 6, y: T + i * ch + ch / 2 + 3.5, textAnchor: 'end' }, dn)),
    ...[0, 6, 12, 18, 23].map(hr => h('text', { key: 'h' + hr, x: L + hr * cw + cw / 2, y: H - 5, textAnchor: 'middle' }, String(hr).padStart(2, '0'))),
    h('text', { key: 'tw', x: W - MR + 6, y: gy + 13, style: { fontSize: '9px' } }, 'per day'),
    h('text', { key: 'th', x: L - 6, y: gy + MB - 3, textAnchor: 'end', style: { fontSize: '9px' } }, 'hour')
  ]
  return h('section', { className: 'ag-card ag-rise' },
    h('div', { className: 'ag-chead' }, h('div', null, h('h3', null, 'When the work happens'),
      h('p', { className: 'ag-sub' }, peak[0] ? `Busiest slot: ${DAYS[peak[1]]} around ${String(peak[2]).padStart(2, '0')}:00 (outlined), commit-local time. Bars show totals per weekday and per hour.` : 'No commits yet.'))),
    h('div', { className: 'ag-chart', ref: box },
      h('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': `Commits by weekday and hour. Busiest weekday ${DAYS[argmax(dayTot)]}, busiest hour ${String(argmax(hourTot)).padStart(2, '0')}:00.` }, h('g', null, cells), h('g', null, margins), h('g', null, labels)),
      h(Tip, { tip })),
    h('div', { className: 'ag-foot' },
      h('span', { className: 'ag-scale' }, h('i', { className: 'z', title: 'No commits' }), ' 0 ', ...STEPS.map((p, i) => h('i', { key: i, title: `${bounds[i]}+ commits`, style: { background: `color-mix(in oklab, var(--ag-seq) ${p}%, var(--ui-bg-card))` } })), ` ${max}`),
      h('span', null, `Peak ${max} commits in one hour slot`)))
}

// ---------------------------------------------------------------------------- churn (lines added / removed)

function Churn({ d }) {
  const box = useRef(null)
  const width = useWidth(box)
  const [tip, setTip] = useState(null)
  const bins = useMemo(() => binDays(d.days || [], 'week'), [d])
  if (!d.has_line_stats) return h('section', { className: 'ag-card ag-rise' }, h('h3', null, 'Lines added and removed'),
    h('p', { className: 'ag-muted', style: { marginTop: 8 } }, 'This dig has no line counts. Re-dig with DevArch stats to see churn.'))
  const W = Math.max(300, width || 560), L = 40, R = 8, T = 8, B = 28, ih = 196, H = T + ih + B, mid = T + ih / 2
  const max = Math.max(1, ...bins.map(b => Math.max(b.ins, b.del)))
  const sc = v => (Math.sqrt(v) / Math.sqrt(max)) * (ih / 2 - 2)
  const bw = Math.max(1.5, (W - L - R) / Math.max(1, bins.length) - 1.5)
  const x = i => L + (i * (W - L - R)) / Math.max(1, bins.length)
  const biggest = bins.reduce((a, b) => (b.ins + b.del > a.ins + a.del ? b : a), bins[0] || { ins: 0, del: 0 })
  const ticks = [max, Math.round(max / 4)].filter((v, i, a) => v > 0 && a.indexOf(v) === i)
  return h('section', { className: 'ag-card ag-rise' },
    h('div', { className: 'ag-chead' }, h('div', null, h('h3', null, 'Lines added and removed'),
      h('p', { className: 'ag-sub' }, `Per week, square-root scale. Biggest week: ${biggest.from ? fmtDay(biggest.from) : '—'}, `, h('span', { className: 'ag-add' }, `+${short(biggest.ins)}`), ' ', h('span', { className: 'ag-del' }, `−${short(biggest.del)}`), '.'))),
    h('div', { className: 'ag-chart', ref: box },
      h('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': `Lines added and removed per week. ${num(d.insertions)} added, ${num(d.deletions)} removed.` },
        ...ticks.flatMap(v => [
          h('line', { key: 'u' + v, x1: L, x2: W - R, y1: mid - sc(v), y2: mid - sc(v), stroke: 'var(--ui-stroke-tertiary)', strokeWidth: 0.6, strokeDasharray: '2 4' }),
          h('line', { key: 'l' + v, x1: L, x2: W - R, y1: mid + sc(v), y2: mid + sc(v), stroke: 'var(--ui-stroke-tertiary)', strokeWidth: 0.6, strokeDasharray: '2 4' }),
          h('text', { key: 'tu' + v, x: L - 6, y: mid - sc(v) + 3.5, textAnchor: 'end' }, short(v)),
          h('text', { key: 'tl' + v, x: L - 6, y: mid + sc(v) + 3.5, textAnchor: 'end' }, short(v))]),
        ...bins.map((b, i) => h('g', { key: i, className: 'hit',
          onPointerDown: e => e.currentTarget.dispatchEvent(new PointerEvent('pointermove', e)),
          onPointerMove: e => { const bb = box.current.getBoundingClientRect(); setTip({ x: e.clientX - bb.left, y: e.clientY - bb.top, w: bb.width, body: [h('b', { key: 'h' }, `Week of ${fmtDay(b.from)}${b.partial ? ' (so far)' : ''}`), h('div', { key: 'a', className: 'ag-add' }, `+${num(b.ins)} added`), h('div', { key: 'r', className: 'ag-del' }, `−${num(b.del)} removed`), h('div', { key: 'n', className: 'ag-muted' }, `${num(b.n)} commit${b.n === 1 ? '' : 's'}`)] }) },
          onPointerLeave: () => setTip(null) },
          h('rect', { x: x(i), y: T, width: bw + 1.5, height: ih, fill: 'transparent' }),
          b.ins ? h('rect', { x: x(i), y: mid - sc(b.ins), width: bw, height: Math.max(1, sc(b.ins)), rx: Math.min(2, bw / 2), fill: 'color-mix(in srgb, var(--ui-green,#2e9e5b) 80%, var(--ui-bg-card))' }) : null,
          b.del ? h('rect', { x: x(i), y: mid, width: bw, height: Math.max(1, sc(b.del)), rx: Math.min(2, bw / 2), fill: 'color-mix(in srgb, var(--ui-red,#d0453f) 75%, var(--ui-bg-card))' }) : null)),
        h('line', { x1: L, x2: W - R, y1: mid, y2: mid, stroke: 'var(--ui-text-secondary)', strokeWidth: 0.8 }),
        h('text', { x: L, y: H - 5 }, fmtDay(d.first)), h('text', { x: W - R, y: H - 5, textAnchor: 'end' }, fmtDay(d.last))),
      h(Tip, { tip })),
    h('div', { className: 'ag-foot' }, h('span', null, h('span', { className: 'ag-add' }, `+${num(d.insertions)}`), ' added above the line, ', h('span', { className: 'ag-del' }, `−${num(d.deletions)}`), ' removed below'), h('span', null, `${bins.length} weeks`)))
}

// ---------------------------------------------------------------------------- side cards

function Load({ d }) {
  const rows = d.load || []
  if (!rows.length) return h('section', { className: 'ag-card ag-rise' }, h('h3', null, 'Change size'),
    h('p', { className: 'ag-muted', style: { marginTop: 8 } }, 'Dig again to measure lines per commit.'))
  const max = Math.max(1, ...rows.map(r => r.n)), total = rows.reduce((a, r) => a + r.n, 0) || 1
  return h('section', { className: 'ag-card ag-rise' },
    h('div', { className: 'ag-chead' }, h('div', null, h('h3', null, 'Change size'), h('p', { className: 'ag-sub' }, 'Lines touched per commit, lockfiles and build output left out.'))),
    h('ul', { className: 'ag-bars' }, rows.map((r, i) => h('li', { key: r.level, title: `${r.n} commits, ${LOAD_RANGE[r.level] || ''}` },
      h('span', null, LOAD_LABEL[r.level] || r.level, h('small', { className: 'ag-rng' }, LOAD_RANGE[r.level] || '')),
      h('span', { className: 't' }, h('i', { style: { width: `${(r.n / max) * 100}%`, background: `color-mix(in oklab, var(--ag-seq) ${30 + i * 17}%, var(--ui-bg-card))` } })),
      h('b', null, pctf(r.n, total))))))
}

const WHO_KIND = { human: 'person', agent: 'agent', bot: 'bot' }
function People({ d }) {
  const all = d.authors || [], bots = all.filter(x => x.kind === 'bot')
  const a = (d.people ? all.filter(x => x.kind !== 'bot') : all).slice(0, 6), max = Math.max(1, ...a.map(x => (x.n || 0) + (x.co || 0)))
  const pp = d.people || {}
  const sub = d.people
    ? `${num(pp.human)} ${pp.human === 1 ? 'person' : 'people'}, ${num(pp.agent)} agent${pp.agent === 1 ? '' : 's'}, ${num(pp.bot)} bot${pp.bot === 1 ? '' : 's'}. ${pctf(d.agent_assisted || 0, Math.max(1, d.commit_count - (d.bot_commits || 0)))} of non-bot commits had an agent co-author.`
    : `${d.author_count} author name${d.author_count === 1 ? '' : 's'} in the history.`
  return h('section', { className: 'ag-card ag-rise' },
    h('div', { className: 'ag-chead' }, h('div', null, h('h3', null, 'Who dug'), h('p', { className: 'ag-sub' }, sub))),
    h('ul', { className: 'ag-bars ag-who' }, a.map(x => h('li', { key: x.name, title: `${x.name}: ${num(x.n)} commits${x.co ? `, co-author on ${num(x.co)}` : ''}${x.spellings > 1 ? `; ${x.spellings} spellings merged` : ''}` },
      h('span', null, x.name, x.kind && x.kind !== 'human' ? h('em', { className: `ag-tag ${x.kind}` }, WHO_KIND[x.kind]) : null),
      h('span', { className: 't' },
        h('i', { style: { width: `${((x.n || 0) / max) * 100}%`, background: 'var(--ag-seq)', display: 'inline-block' } }),
        x.co ? h('i', { className: 'co', style: { width: `${(x.co / max) * 100}%`, display: 'inline-block' } }) : null),
      h('b', null, num((x.n || 0) + (x.co || 0)))))),
    d.people && bots.length ? h('p', { className: 'ag-muted', title: bots.map(x => `${x.name} (${num(x.n || 0)})`).join(', ') }, `Plus ${num(d.bot_commits ?? bots.reduce((t, x) => t + (x.n || 0), 0))} commits from ${num(pp.bot ?? bots.length)} bot${(pp.bot ?? bots.length) === 1 ? '' : 's'}; hover for the busiest.`) : null,
    a.some(x => x.co) ? h('p', { className: 'ag-muted ag-key' }, h('i', { className: 'sw' }), 'authored', h('i', { className: 'sw co' }), 'co-authored') : null)
}

function Files({ d }) {
  const rows = d.paths || []
  if (!rows.length) return null
  const max = Math.max(1, ...rows.map(r => r.commits || 0))
  return h('section', { className: 'ag-card ag-rise' },
    h('div', { className: 'ag-chead' }, h('div', null, h('h3', null, 'Hotspots'), h('p', { className: 'ag-sub' }, 'Files changed in the most commits. Lockfiles and build output left out.'))),
    h('ul', { className: 'ag-bars ag-files' }, rows.slice(0, 10).map(r => {
      const parts = r.path.split('/'), base = parts.pop()
      return h('li', { key: r.path, title: `${r.path}: ${num(r.commits)} commits, +${num(r.ins)} −${num(r.del)}` },
        h('span', null, parts.length ? h('small', null, parts.join('/') + '/') : null, base),
        h('span', { className: 't' }, h('i', { style: { width: `${(r.commits / max) * 100}%`, background: 'var(--ag-seq)' } })),
        h('b', null, num(r.commits)))
    })))
}

function Releases({ d, multiYear }) {
  const rows = (d.releases || []).slice().reverse()
  if (!rows.length) return null
  const ds = (d.commits || []).map(c => c.day)
  return h('section', { className: 'ag-card ag-rise' },
    h('div', { className: 'ag-chead' }, h('div', null, h('h3', null, 'Releases'), h('p', { className: 'ag-sub' }, `${rows.length} tag${rows.length === 1 ? '' : 's'}, newest first. Ticks under the strata mark each one.`))),
    h('ol', { className: 'ag-rel' }, rows.slice(0, 10).map((r, i) => {
      const prev = rows[i + 1]
      const n = prev ? ds.filter(x => x > prev.d && x <= r.d).length : null
      return h('li', { key: r.name + r.sha },
        h('b', null, r.name), h('time', null, multiYear ? fmtDayY(r.d) : fmtDay(r.d)),
        h('span', { className: 'ag-muted' }, !r.on_history ? 'on another branch' : n == null ? 'first tag' : `${num(n)} commit${n === 1 ? '' : 's'} since ${prev.name}`))
    })),
    rows.length > 10 ? h('p', { className: 'ag-muted' }, `and ${rows.length - 10} older`) : null)
}

const STATUS = {
  PRESENT: { tone: 'var(--ui-green,#2e9e5b)', label: 'In place', icon: 'M4 12.5 9.5 18 20 6.5' },
  EMERGING: { tone: 'var(--ui-yellow,#c9a227)', label: 'Growing', icon: 'M12 5v10M12 19.5v.5' },
  ABSENT: { tone: 'var(--ui-red,#d0453f)', label: 'Missing', icon: 'M6 6l12 12M18 6 6 18' }
}

const SEV = { HIGH: 0, MEDIUM: 1, LOW: 2 }
const STATUS_ORDER = { ABSENT: 0, MISSING: 0, EMERGING: 1, PRESENT: 2 }
function Practices({ d }) {
  const rows = (d.sdlc || []).slice().sort((a, b) => ((STATUS_ORDER[a.status] ?? 1) - (STATUS_ORDER[b.status] ?? 1)) || ((SEV[a.severity] ?? 3) - (SEV[b.severity] ?? 3)))
  const open = rows.filter(r => r.status !== 'PRESENT'), fine = rows.filter(r => r.status === 'PRESENT')
  const badge = st => h('span', { className: 'ag-st', style: { '--tone': st.tone } },
    h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 3, strokeLinecap: 'round', 'aria-hidden': true }, h('path', { d: st.icon })), st.label)
  return h('section', { className: 'ag-card ag-rise' },
    h('div', { className: 'ag-chead' }, h('div', null, h('h3', null, 'Practice health'), h('p', { className: 'ag-sub' }, rows.length ? `${open.length} to work on, most severe first. Measured on commits by people and agents (bots left out), from subjects and file paths.` : 'Measured from commit subjects and file paths.'))),
    rows.length ? h('ul', { className: 'ag-sdlc' },
      open.map(r => {
        const st = STATUS[r.status] || STATUS[r.status === 'MISSING' ? 'ABSENT' : 'EMERGING']
        return h('li', { key: r.practice, title: r.recommendation || undefined },
          h('span', { className: 'nm' }, r.severity ? h('em', { className: `sev s${SEV[r.severity] ?? 2}` }, r.severity.toLowerCase()) : null, r.practice),
          badge(st),
          r.of ? h('p', { className: 'ev' }, h('span', { className: 'ag-meter', 'aria-hidden': true }, h('i', { style: { width: `${Math.min(100, (r.share / Math.max(r.target, 1e-9)) * 100)}%`, background: st.tone } })),
            `${num(r.n)} of ${num(r.of)} · ${pctf(r.n, r.of)} · target ${Math.round(r.target * 100)}%`) : null,
          (r.advice || r.recommendation) ? h('p', null, r.advice || r.recommendation) : null)
      }),
      fine.length ? h('li', { key: 'fine', className: 'fine' }, h('span', { className: 'nm' }, fine.map(r => r.practice).join(' · ')), badge(STATUS.PRESENT)) : null)
      : h('p', { className: 'ag-muted' }, 'Dig again to check practices.'))
}

function Turning({ d, sig, setSig, multiYear }) {
  const list = topSignals(d)
  return h('section', { className: 'ag-card ag-rise' },
    h('div', { className: 'ag-chead' }, h('div', null, h('h3', null, 'Turning points'), h('p', { className: 'ag-sub' }, 'Strongest recent signals, newest first. Runs within a week fold into one. Numbers match the strata rail.'))),
    list.length ? h('ol', { className: 'ag-sig' }, list.map(s => h('li', { key: s.idx, className: sig === s.idx ? 'on' : undefined, tabIndex: 0,
      onPointerEnter: () => setSig(s.idx), onPointerLeave: () => setSig(null), onFocus: () => setSig(s.idx), onBlur: () => setSig(null) },
      h('b', { className: 'no' }, s.no), h('time', null, multiYear ? fmtDayY(s.d) : fmtDay(s.d)), h('span', null, h('small', null, SIGNAL_LABEL[s.type] || s.type), s.detail, s.end && s.end !== s.d ? h('em', { className: 'ag-span' }, ` through ${multiYear ? fmtDayY(s.end) : fmtDay(s.end)}`) : null))))
      : h('p', { className: 'ag-muted' }, 'No turning points found.'))
}

// Core sample: the eras as a drilled core, newest on top. Layer height is log(commits),
// each layer striped by its kind mix, wavy lines mark quiet gaps. Click to filter commits.
function Core({ d, pal, eraNo, era, setEra, hl, setHl }) {
  const cs = d.clusters || []
  const uid = useUid('ag-core')
  if (cs.length < 2) return null
  const W = 74, CW = 40, H = 560, gapH = 10
  const order = cs.map((_, i) => i).reverse()
  const wts = order.map(i => Math.log2(2 + (cs[i].commits || 0)))
  const hiat = order.map((i, j) => j < order.length - 1 && (d.gaps || []).some(g => g.start >= cs[order[j + 1]].end && g.end <= cs[i].start))
  const avail = H - hiat.filter(Boolean).length * gapH, tw = wts.reduce((a, b) => a + b, 0)
  let yy = 0
  const parts = []
  order.forEach((i, j) => {
    const c = cs[i], hh = (avail * wts[j]) / tw, no = eraNo[i], isOn = era === i, lit = isOn || hl === i
    const tot = (c.k || []).reduce((a, b) => a + b, 0) || 1
    let xx = 0
    const stripes = KINDS.map((k, kj) => { const w = (((c.k || [])[kj] || 0) / tot) * CW; const r = w ? h('rect', { key: k, x: xx, y: yy, width: w + 0.3, height: hh, fill: pal[k] }) : null; xx += w; return r })
    const label = `${no ? `Era ${no}` : 'Short burst'}, ${fmtRange(c.start, c.end, true)}, ${c.commits} commits`
    parts.push(h('g', { key: 'l' + i, className: 'layer', role: 'button', tabIndex: 0, 'aria-pressed': isOn, 'aria-label': `${label}. ${isOn ? 'Showing only this era' : 'Show only this era'}`,
      onClick: () => setEra(isOn ? null : i), onKeyDown: e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setEra(isOn ? null : i) } },
      onPointerEnter: () => setHl(i), onPointerLeave: () => setHl(null), opacity: era != null && !isOn ? 0.35 : 1 },
      h('title', null, label),
      h('g', { clipPath: `url(#${uid}-cyl)` }, stripes, h('rect', { x: 0, y: yy, width: CW, height: hh, fill: `url(#${uid}-shade)` }),
        h('line', { x1: 0, x2: CW, y1: yy + hh - 0.4, y2: yy + hh - 0.4, stroke: 'var(--ui-bg-card)', strokeWidth: 0.8 })),
      lit ? h('rect', { x: -1.5, y: yy + 0.5, width: CW + 3, height: Math.max(1, hh - 1), rx: 3, fill: 'none', stroke: 'var(--ui-text-primary)', strokeWidth: 1.4 }) : null,
      h('rect', { x: CW, y: yy, width: W - CW, height: hh, fill: 'transparent' }),
      no && hh >= 11 ? h('text', { x: CW + 7, y: yy + hh / 2 + 3.5, style: { fontSize: '10px', fontWeight: lit ? 700 : 500, fill: lit ? 'var(--ui-text-primary)' : 'var(--ui-text-secondary)' } }, String(no)) : null))
    yy += hh
    if (hiat[j]) {
      let w = `M-2,${yy + gapH / 2}`
      for (let x = 0; x <= CW + 2; x += 4) w += `L${x},${(yy + gapH / 2 + (x % 8 ? 2 : -2)).toFixed(1)}`
      parts.push(h('path', { key: 'h' + i, d: w, fill: 'none', stroke: 'var(--ui-text-secondary)', strokeWidth: 1.1, strokeLinejoin: 'round' }))
      yy += gapH
    }
  })
  return h('div', { className: 'ag-core' },
    h('small', null, 'Core'),
    h('svg', { viewBox: `-3 -2 ${W + 3} ${H + 4}`, width: W, style: { height: 'auto' }, role: 'group', 'aria-label': 'Core sample of eras, newest on top. Choose a layer to filter the commits.' },
      h('defs', null,
        h('clipPath', { id: `${uid}-cyl` }, h('rect', { x: 0, y: 0, width: CW, height: H, rx: 6 })),
        h('linearGradient', { id: `${uid}-shade`, x1: 0, y1: 0, x2: 1, y2: 0 },
          h('stop', { offset: 0, stopColor: '#000', stopOpacity: 0.28 }), h('stop', { offset: 0.35, stopColor: '#fff', stopOpacity: 0.16 }),
          h('stop', { offset: 0.6, stopColor: '#fff', stopOpacity: 0 }), h('stop', { offset: 1, stopColor: '#000', stopOpacity: 0.34 }))),
      parts),
    h('small', null, 'oldest'))
}

const CONV_RE = /^([a-z]+)(?:\(([^)]{1,40})\))?!?:\s+/i
const WEEKDAY = s => DAYS[(parseDay(s).getUTCDay() + 6) % 7]

function Commits({ d, pal, eraNo, hl, setHl }) {
  const [q, setQ] = useState('')
  const [kind, setKind] = useState('all')
  const [n, setN] = useState(PAGE)
  const [era, setEraRaw] = useState(null)
  const setEra = v => { setEraRaw(v); setN(PAGE) }
  // One clock: the server already put every commit in the project's zone (d.manifest.time_zone),
  // the same zone it used to cut days, eras and the rhythm. Sort by instant, show that day.
  const all = useMemo(() => (d.commits || []).map(c => {
    const ms = Date.parse(c.t)
    return { ...c, ms: isNaN(ms) ? 0 : ms, day: c.day || String(c.t).slice(0, 10), hm: String(c.t).slice(11, 16) }
  }).sort((x, y) => y.ms - x.ms), [d.commits])
  const ql = q.trim().toLowerCase()
  const ec = era != null ? (d.clusters || [])[era] : null
  const rows = all.filter(c => (kind === 'all' || c.kind === kind) && (!ql || `${c.msg} ${c.author} ${(c.co || []).join(' ')} ${c.sha} ${c.pr ? '#' + c.pr : ''}`.toLowerCase().includes(ql))
    && (!ec || (c.day >= ec.start && c.day <= ec.end)))
  const lmax = useMemo(() => Math.log1p(Math.max(1, ...(d.commits || []).map(c => Math.max(c.ins || 0, c.del || 0)))), [d.commits])
  const lw = v => (v ? Math.max(1, (Math.log1p(v) / lmax) * 22) : 0)
  const shown = rows.slice(0, n)
  const perDay = {}
  rows.forEach(c => { perDay[c.day] = (perDay[c.day] || 0) + 1 })
  const body = []
  let day = ''
  shown.forEach(c => {
    const dk = c.day
    if (dk !== day) {
      day = dk
      body.push(h('tr', { key: 'g' + dk, className: 'grp' }, h('td', { colSpan: 6 }, `${WEEKDAY(dk)} · ${fmtDayY(dk)}`, h('em', null, `${perDay[dk]} row${perDay[dk] === 1 ? '' : 's'}`))))
    }
    const m = c.msg.match(CONV_RE)
    const scope = m && m[2], msg = m ? c.msg.slice(m[0].length) : c.msg
    const merge = c.kind === 'merge'
    body.push(h('tr', { key: c.sha + c.t, className: merge ? 'mg' : undefined },
      h('td', { className: 'm', title: `${c.t}${c.tz ? ` (committed at ${c.tz})` : ''}` }, c.hm),
      h('td', { className: 'm opt', title: c.sha }, c.sha.slice(0, 7)),
      h('td', null, h('span', { className: 'ag-kind' }, h('i', { className: merge ? 'mg' : undefined, style: merge ? undefined : { background: pal[c.kind] || pal.other } }), KIND_LABEL[c.kind] || c.kind)),
      h('td', { title: c.msg }, c.rv ? h('span', { className: 'ag-tag rv', title: `Reverts ${c.rv}` }, 'revert') : null,
        scope ? h('span', { className: 'ag-scope' }, scope) : null, msg,
        c.pr && !msg.includes(`#${c.pr}`) ? h('span', { className: 'ag-pr' }, ` #${c.pr}`) : null),
      h('td', { className: 'opt', title: [c.author, ...(c.co || []).map(x => `with ${x}`)].join(', ') },
        c.author, c.ak === 'b' ? h('em', { className: 'ag-tag bot' }, 'bot') : null,
        (c.co || []).length ? h('em', { className: 'ag-tag agent' }, `+${c.co.length === 1 ? c.co[0] : c.co.length}`) : null),
      h('td', { className: 'n opt' }, c.ins || c.del ? [
        h('svg', { key: 'b', className: 'ag-div', viewBox: '0 0 46 10', 'aria-hidden': true },
          h('rect', { x: 23 - lw(c.del), y: 2, width: lw(c.del), height: 6, rx: 1.5, className: 'del' }),
          h('rect', { x: 23, y: 2, width: lw(c.ins), height: 6, rx: 1.5, className: 'add' }),
          h('line', { x1: 23, x2: 23, y1: 0, y2: 10 })),
        h('span', { key: 'a', className: 'ag-add' }, `+${short(c.ins)}`), ' ', h('span', { key: 'd', className: 'ag-del' }, `−${short(c.del)}`)] : h('span', { className: 'ag-muted' }, '—'))))
  })
  return h('section', { className: 'ag-card ag-rise' },
    h('div', { className: 'ag-chead' },
      h('div', null, h('h3', null, 'Commits'), h('p', { className: 'ag-sub' },
        `Showing ${num(shown.length)} of ${num(rows.length)}${rows.length !== all.length ? ` matching (${num(all.length)} total)` : ''}${d.commits_truncated ? `, latest ${num(all.length)} kept` : ''}. Times in ${(d.manifest && d.manifest.time_zone) || 'the project zone'}${d.merge_count ? `; ${num(d.merge_count)} merges are grey and left out of the counts` : ''}.`)),
      h('div', { className: 'ag-tools' },
        h('input', { className: 'ag-search', type: 'search', placeholder: 'Search messages, authors, SHAs', value: q, 'aria-label': 'Search commits', onChange: e => { setQ(e.target.value); setN(PAGE) } }),
        h('select', { className: 'ag-select', value: kind, 'aria-label': 'Work type', onChange: e => { setKind(e.target.value); setN(PAGE) } },
          h('option', { value: 'all' }, 'Everything'), KINDS.map(k => h('option', { key: k, value: k }, KIND_LABEL[k])),
          d.merge_count ? h('option', { value: 'merge' }, `Merges (${num(d.merge_count)})`) : null),
        ec ? h('button', { type: 'button', className: 'ag-chip', onClick: () => setEra(null), 'aria-label': 'Clear era filter' },
          `${eraNo[era] ? `Era ${eraNo[era]}` : 'Burst'} · ${fmtRange(ec.start, ec.end, true)}`, h('span', { 'aria-hidden': true }, ' ×')) : null)),
    h('div', { className: 'ag-cwrap' },
    h(Core, { d, pal, eraNo, era, setEra, hl, setHl }),
    h('div', { className: 'ag-tw' },
    h('table', { className: 'ag-table' },
      h('colgroup', null, h('col', { style: { width: '62px' } }), h('col', { className: 'opt', style: { width: '78px' } }), h('col', { style: { width: '120px' } }), h('col', null),
        h('col', { className: 'opt', style: { width: '160px' } }), h('col', { className: 'opt', style: { width: '150px' } })),
      h('thead', null, h('tr', null, h('th', null, 'Time'), h('th', { className: 'opt' }, 'SHA'), h('th', null, 'Kind'), h('th', null, 'Message'), h('th', { className: 'opt' }, 'Author'), h('th', { className: 'opt', style: { textAlign: 'right' } }, 'Lines'))),
      h('tbody', null, body)),
    rows.length > n ? h('div', { style: { marginTop: 10 } }, h('button', { type: 'button', className: 'ag-btn', onClick: () => setN(n + PAGE * 2) }, `Show more (${num(rows.length - n)} left)`)) : null,
    !rows.length ? h('p', { className: 'ag-muted', style: { marginTop: 10 } }, 'No commits match.') : null)))
}

// ---------------------------------------------------------------------------- dig + page

// Digger: idle → (no repo: hint) | posting → started (hands off to Page) | error.
// "posting" blocks a double click from sending a second POST.
function Digger({ ctx, repos, reposFault, onStarted, onBusyElsewhere, busy }) {
  const [repo, setRepo] = useState('')
  const [err, setErr] = useState('')
  const [posting, setPosting] = useState(false)
  const sel = useRef(null)
  const go = () => {
    if (posting) return
    if (!repo) { setErr('Pick a repo first.'); if (sel.current) sel.current.focus(); return }
    setErr('')
    setPosting(true)
    ctx.rest('/dig', { method: 'POST', body: { repo } })
      .then(r => onStarted(r && r.project))
      .catch(e => {
        const m = String((e && e.message) || e)
        setErr(m)
        // Another tab or the CLI started a dig: resync so its progress shows here.
        if (/already running/i.test(m)) onBusyElsewhere()
      })
      .finally(() => setPosting(false))
  }
  busy = busy || posting
  return h('div', { className: 'ag-ctl' },
    h('select', { ref: sel, className: 'ag-select', value: repo, 'aria-label': 'Repository to dig', onChange: e => { setRepo(e.target.value); setErr('') }, disabled: !repos.length || busy },
      h('option', { value: '' }, repos.length ? 'Dig a repo…' : reposFault ? 'Listing repos… (retrying)' : 'No repos under your roots'),
      repos.map(r => h('option', { key: r.path, value: r.path, title: r.path }, r.name))),
    h('button', { type: 'button', className: 'ag-btn pri', disabled: busy || !repos.length, onClick: go }, busy ? 'Digging…' : 'Dig'),
    err ? h('span', { className: 'ag-muted ag-err', role: 'alert' }, err) : null)
}

// A running dig lays down one deposit band per step; the current band pulses.
// Stop asks the backend to cancel (it kills the command in flight); the run then ends "cancelled".
function Progress({ st, pal, onStop }) {
  const steps = Math.max(1, st.steps || 7), done = Math.min(st.step || 0, steps)
  const bh = 5, gap = 2, H = steps * (bh + gap)
  const [stopping, setStopping] = useState(false)
  const [err, setErr] = useState('')
  const stop = () => { if (stopping) return; setStopping(true); setErr(''); onStop().catch(e => { setStopping(false); setErr(String((e && e.message) || e)) }) }
  const halting = stopping || st.cancelling
  return h('div', { className: 'ag-run', role: 'status' },
    h('div', { className: 'ag-runhead' }, h('div', null, h('b', null, `${st.resumed ? 'Resuming' : 'Digging'} ${st.project || ''}`), ' · ', halting ? 'Stopping…' : st.label || 'Starting'),
      onStop ? h('button', { type: 'button', className: 'ag-btn', disabled: halting, onClick: stop }, halting ? 'Stopping…' : 'Stop') : null),
    h('svg', { viewBox: `0 0 600 ${H}`, preserveAspectRatio: 'none', style: { height: H }, 'aria-hidden': true },
      Array.from({ length: steps }, (_, i) => h('rect', {
        key: i, x: 0, y: H - (i + 1) * (bh + gap) + gap, width: 600, height: bh, rx: 2,
        className: i === done && !halting ? 'now' : undefined,
        fill: i < done || i === done ? pal[KINDS[i % 6]] : 'var(--ui-stroke-tertiary)', fillOpacity: i === done ? 0.7 : i < done ? 0.95 : 0.6
      }))),
    h('small', null, err ? h('span', { className: 'ag-err' }, err) : st.lost ? 'Lost contact with Hermes; still retrying…' : `Step ${Math.min(done + 1, steps)} of ${st.steps || '…'} · big histories take a few minutes; you can leave this page.`))
}

// After a dig stops short (failed, cancelled, or cut off by a Hermes restart) offer to
// pick it up from the step it reached, or to dismiss the note.
function Stalled({ st, onResume, onDismiss }) {
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const what = st.state === 'cancelled' ? `You stopped the dig of ${st.project}.`
    : st.interrupted ? `The dig of ${st.project} was cut off when Hermes restarted.` : `The dig of ${st.project} failed: ${st.error || 'unknown error'}`
  const left = (st.completed || []).length
  const go = () => { if (busy) return; setBusy(true); setErr(''); onResume().catch(e => { setBusy(false); setErr(String((e && e.message) || e)) }) }
  return h('div', { className: 'ag-stall', role: 'alert' },
    h('span', null, what, left ? ` ${left} step${left === 1 ? '' : 's'} already done.` : '', err ? h('span', { className: 'ag-err' }, ` ${err}`) : null),
    h('span', { className: 'ag-tools' },
      h('button', { type: 'button', className: 'ag-btn pri', disabled: busy, onClick: go }, busy ? 'Resuming…' : left ? 'Resume' : 'Try again'),
      h('button', { type: 'button', className: 'ag-btn', onClick: onDismiss, 'aria-label': 'Dismiss' }, 'Dismiss')))
}

function Ghost({ children }) {
  const wave = (y0, a, p) => { let d = `M0,${y0}`; for (let x = 0; x <= 600; x += 20) d += `L${x},${(y0 + a * Math.sin(x / 70 + p)).toFixed(1)}`; return d }
  return h('div', { className: 'ag-ghost' },
    h('svg', { className: 'bg', viewBox: '0 0 600 120', preserveAspectRatio: 'none', 'aria-hidden': true },
      [0, 1, 2, 3, 4, 5].map(i => h('path', { key: i, d: `${wave(20 + i * 17, 6 + i, i * 0.9)}L600,120L0,120Z`, fill: ['#00a2ce', '#8b61e3', '#d84497', '#00ad71', '#366bd3', '#7ca215'][i], fillOpacity: 0.55 }))),
    children)
}

function Spark({ d, pick = b => b.n, label }) {
  const bins = useMemo(() => binDays(d.days || [], 'week'), [d])
  if (bins.length < 2) return null
  const vals = bins.map(pick), max = Math.max(1, ...vals)
  const pts = vals.map((v, i) => [(i / (bins.length - 1)) * 100, 17 - (v / max) * 16])
  return h('svg', { className: 'spark', viewBox: '0 0 100 18', preserveAspectRatio: 'none', role: label ? 'img' : undefined, 'aria-label': label, 'aria-hidden': label ? undefined : true },
    h('path', { d: `M0,18L${pts.map(p => p.map(v => v.toFixed(2)).join(',')).join('L')}L100,18Z`, fill: 'var(--ag-seq)', fillOpacity: 0.18 }),
    h('path', { d: `M${pts.map(p => p.map(v => v.toFixed(2)).join(',')).join('L')}`, fill: 'none', stroke: 'var(--ag-seq)', strokeWidth: 1.4, vectorEffect: 'non-scaling-stroke' }))
}

// Where this dig came from, so two readers can tell whether they are looking at the same thing.
function Provenance({ d, when }) {
  const m = d.manifest
  if (!m) return h('p', { className: 'ag-prov' }, 'Older dig without a manifest. Dig again for provenance.')
  const bits = [m.head_sha ? `HEAD ${String(m.head_sha).slice(0, 10)}` : null, m.ref ? `on ${m.ref}` : null,
    m.history === 'all' ? 'all branches' : 'this branch', m.time_zone ? `zone ${m.time_zone}` : null,
    m.mailmap ? '.mailmap applied' : null, `schema ${m.schema_version}`, m.config_hash ? `config ${m.config_hash}` : null,
    m.source === 'git' ? 'read with git' : 'from DevArch files']
  return h('p', { className: 'ag-prov', title: m.devarch_pin ? `DevArch ${m.devarch_pin}` : undefined },
    bits.filter(Boolean).join(' · '), isNaN(when) ? '' : ` · dug ${when.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}`)
}

// Story: the dig told in a few plain chapters (built by rules in __init__.py, no LLM).
// A chapter tied to an era lights that stretch of the strata on hover or focus.
function Story({ d, hl, setHl }) {
  const rows = Array.isArray(d.story) ? d.story : []
  if (!rows.length) return null
  return h('section', { className: 'ag-card ag-rise', 'aria-label': 'Story' },
    h('div', { className: 'ag-chead' }, h('div', null, h('h3', null, 'Story'),
      h('p', { className: 'ag-sub' }, 'The history in plain words, written by rules from the numbers below. Point at a chapter to light its era.'))),
    h('ol', { className: 'ag-story' }, rows.map(c => {
      const tied = c.era != null && (d.clusters || [])[c.era]
      const on = tied ? { 'data-era': c.era, tabIndex: 0, className: hl === c.era ? 'on' : undefined,
        onPointerEnter: () => setHl(c.era), onPointerLeave: () => setHl(null),
        onFocus: () => setHl(c.era), onBlur: () => setHl(null) } : {}
      return h('li', { key: c.id, ...on }, h('b', null, c.title), c.text)
    })))
}

function headline(d) {
  const t = d.kind_totals || [], tot = t.reduce((a, b) => a + b, 0) || 1
  const top = KINDS.map((k, j) => [KIND_LABEL[k].toLowerCase(), t[j] || 0]).sort((a, b) => b[1] - a[1])
  const p = Math.round((top[0][1] / tot) * 100), q = Math.round((top[1][1] / tot) * 100)
  const mix = p >= 50 ? `Mostly ${top[0][0]} (${p}%).` : `${top[0][0][0].toUpperCase()}${top[0][0].slice(1)} lead (${p}%), then ${top[1][0]} (${q}%).`
  return `${num(d.commit_count)} commits over ${num(d.span_days)} days${d.merge_count ? `, plus ${num(d.merge_count)} merges` : ''}. ${mix}`
}

function Page({ ctx }) {
  const root = useRef(null)
  const mode = useMode(root)
  const pal = PALETTE[mode]
  const [projects, setProjects] = useState({ loading: true, list: [] })
  const [repos, setRepos] = useState([])
  const [sel, setSel] = useState(() => { try { return ctx.storage.get('project', '') || '' } catch { return '' } })
  const [dig, setDig] = useState(null)
  const [run, setRun] = useState(null)
  const [hl, setHl] = useState(null)
  const [sig, setSig] = useState(null)
  const [dismissed, setDismissed] = useState('')
  const [reloadKey, setReloadKey] = useState(0)
  const seq = useRef(0)

  const loadProjects = () => ctx.rest('/projects')
    .then(r => setProjects({ loading: false, list: Array.isArray(r && r.projects) ? r.projects : [] }))
    .catch(e => setProjects({ loading: false, list: [], fault: String((e && e.message) || e) }))
  // The repo list can fail on first load (backend still mounting, connection settling).
  // Retry with backoff rather than leave the picker empty until a reload.
  const [reposFault, setReposFault] = useState(false)
  const loadRepos = (attempt = 0) => ctx.rest('/repos')
    .then(r => { setRepos(Array.isArray(r && r.repos) ? r.repos : []); setReposFault(false) })
    .catch(() => {
      setReposFault(true)
      if (attempt < 5) setTimeout(() => loadRepos(attempt + 1), [1000, 2000, 5000, 10000, 20000][attempt])
    })
  useEffect(() => {
    loadProjects()
    loadRepos()
  }, [])

  const withDig = projects.list.filter(p => p.has_dig)
  const current = withDig.find(p => p.project === sel) || withDig[0] || null
  // Run lifecycle (backend owns the truth; see DIG_STATES in __init__.py):
  //   none → running(step) → done | failed (failed+interrupted after a Hermes restart).
  // This page's own run wins; otherwise any running dig from the project list (another
  // tab, the CLI). A finished run's project is skipped until the list reloads, so a
  // stale "running" row cannot restart polling.
  const runningProject = run && run.state === 'running' ? run.project
    : (projects.list.find(p => p.state === 'running' && !(run && p.project === run.project)) || {}).project

  useEffect(() => {
    if (!current) { setDig(null); return }
    const n = ++seq.current
    // Re-reading the same dig keeps it on screen (no flash); a different dig shows loading.
    setDig(prev => (prev && prev.project === current.project && !prev.fault && !prev.loading ? prev : { loading: true }))
    setHl(null)
    ctx.rest(`/dig?project=${encodeURIComponent(current.project)}`)
      .then(r => { if (n === seq.current) setDig(r) })
      .catch(e => { if (n === seq.current) setDig({ fault: String((e && e.message) || e) }) })
  }, [current && current.project, current && current.last, current && current.commit_count, reloadKey])

  // Poll a running dig every 2s; when it finishes, reload projects and the dig, and open it.
  useEffect(() => {
    if (!runningProject) return undefined
    let alive = true, misses = 0
    const tick = () => ctx.rest(`/status?project=${encodeURIComponent(runningProject)}`)
      .then(st => {
        if (!alive) return
        misses = 0
        setRun({ ...st, project: runningProject })
        if (st && st.state !== 'running') { choose(runningProject); loadProjects(); setReloadKey(k => k + 1) }
      })
      .catch(() => {
        // Backend restarting: keep polling, and say so after ~10s of silence.
        if (alive && ++misses >= 5) setRun(r => (r && r.state === 'running' && r.project === runningProject ? { ...r, lost: true } : { state: 'running', project: runningProject, label: 'Waiting for Hermes', lost: true }))
      })
    tick()
    const id = setInterval(() => { if (!document.hidden) tick() }, 2000)
    return () => { alive = false; clearInterval(id) }
  }, [runningProject])

  const choose = v => { setSel(v); try { ctx.storage.set('project', v) } catch { /* storage unavailable */ } }
  const started = (p, resumed) => { if (p) { setDismissed(''); setRun({ state: 'running', project: p, step: 0, label: resumed ? 'Resuming' : 'Starting', resumed }) } }
  const stop = () => ctx.rest('/cancel', { method: 'POST', body: { project: runningProject } })
    .then(() => setRun(r => (r && r.project === runningProject ? { ...r, cancelling: true } : r)))
  // A dig that stopped short: this page's run, else the selected project's row in the list
  // (a cut-off dig still shows after a reload).
  const listStalled = projects.list.find(p => (p.state === 'failed' || p.state === 'cancelled') && (!current || p.project === current.project || !p.has_dig))
  const stalled = !runningProject && (run && (run.state === 'failed' || run.state === 'cancelled') ? run : listStalled ? { ...listStalled, ...(listStalled.status || {}) } : null)
  const resume = () => ctx.rest('/dig', { method: 'POST', body: { project: stalled.project, resume: true } })
    .then(r => { started(r && r.project, true); loadProjects() })

  let body
  if (projects.fault) {
    body = h('div', { className: 'ag-empty' }, h('b', null, 'Could not reach the AG4TE backend.'), h('span', { className: 'ag-err' }, projects.fault),
      h('span', null, 'Enable the plugin in Hermes so its backend loads.'))
  } else if (projects.loading) {
    body = h('p', { className: 'ag-muted' }, 'Loading digs…')
  } else if (!current) {
    body = h(Ghost, null, h(Glyph, { size: 40 }), h('b', null, 'Nothing dug yet.'),
      h('span', null, 'Pick a repo above and press Dig. AG4TE reads its whole history and lays it down here as strata: every commit, by kind of work, era by era.'),
      repos.length || reposFault ? null : h('span', null, 'No git repos were found under your repo roots. Set ', h('code', null, 'plugins.ag4te.repo_roots'), ' in the Hermes config.'))
  } else if (!dig || dig.loading) {
    body = h('p', { className: 'ag-muted' }, 'Reading the dig…')
  } else if (dig.fault) {
    body = h('div', { className: 'ag-empty' }, h('b', null, 'Could not open this dig.'), h('span', { className: 'ag-err' }, dig.fault))
  } else if (dig.empty) {
    body = h('div', { className: 'ag-empty' }, h('b', null, 'That repo has no commits to read.'))
  } else {
    const d = dig
    const pct = Math.round((d.active_days / Math.max(1, d.span_days)) * 100)
    const multiYear = String(d.first).slice(0, 4) !== String(d.last).slice(0, 4)
    let k = 0
    const eraNo = (d.clusters || []).map(c => (c.commits >= eraMin(d) ? ++k : 0))
    const when = new Date(d.generated_at)
    body = [
      h('div', { key: 'lead', className: 'ag-lead ag-rise' },
        h('div', null,
          h('h2', null, headline(d)),
          h('p', { className: 'meta' }, `${d.project}${d.repo ? ` · ${d.repo}` : ''} · ${fmtDayY(d.first)} to ${fmtDayY(d.last)} · dug ${isNaN(when) ? 'recently' : when.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}`)),
        h(Agate, { d, pal, eraNo, hl, setHl, multiYear })),
      h('div', { key: 'kpi', className: 'ag-kpis' },
        h('div', { className: 'lead' }, h('small', null, 'Commits'), h('span', null, num(d.commit_count)), h(Spark, { d, label: 'Commits per week' })),
        h('div', null, h('small', null, 'Active days'), h('span', null, num(d.active_days)), h('em', null, `${pct}%`), h(Spark, { d, pick: b => b.act, label: 'Active days per week' })),
        h('div', null, h('small', null, 'Longest streak'), h('span', null, d.longest_streak), h('em', null, 'days')),
        h('div', null, h('small', null, 'Longest quiet'), h('span', null, d.longest_gap), h('em', null, 'days')),
        h('div', { title: fmtDayY(d.busiest_day.d) }, h('small', null, 'Busiest day'), h('span', null, d.busiest_day.n), h('em', null, fmtDay(d.busiest_day.d))),
        h('div', null, h('small', null, 'Lines'), h('span', { className: 'ag-add' }, `+${short(d.insertions)}`), h('em', { className: 'ag-del' }, `−${short(d.deletions)}`), h(Spark, { d, pick: b => b.ins + b.del, label: 'Lines changed per week' }))),
      h(Story, { key: 'story', d, hl, setHl }),
      h(Strata, { key: 'strata', d, pal, eraNo, hl, setHl, multiYear, sig, setSig }),
      h('div', { key: 'g2', className: 'ag-grid2' }, h(Rhythm, { d }), h(Churn, { d })),
      h('div', { key: 'g3', className: 'ag-grid3' }, h(Practices, { d }), h(Turning, { d, sig, setSig, multiYear }), h('div', { className: 'ag-stack' }, h(People, { d }), h(Load, { d }))),
      (d.paths || []).length || (d.releases || []).length ? h('div', { key: 'g4', className: 'ag-grid2' }, h(Files, { d }), h(Releases, { d, multiYear })) : null,
      h(Commits, { key: 'commits', d, pal, eraNo, hl, setHl }),
      h(Provenance, { key: 'prov', d, when })
    ]
  }

  const style = { '--ag-seq': mode === 'dark' ? '#8b61e3' : '#7544cd' }
  return h('div', { className: 'ag', ref: root, style },
    h('main', { className: 'ag-main' },
      h('div', { className: 'ag-head' },
        h('div', { className: 'ag-brand' }, h(Glyph), h('b', null, 'AG4TE'), h('span', null, 'git archaeology')),
        withDig.length ? h('select', { className: 'ag-select', value: current ? current.project : '', 'aria-label': 'Dig to show', onChange: e => choose(e.target.value) },
          withDig.map(p => h('option', { key: p.project, value: p.project }, `${p.project} · ${num(p.commit_count)} commits`))) : null,
        h(Digger, { ctx, repos, reposFault, onStarted: started, onBusyElsewhere: () => { setRun(null); loadProjects() }, busy: !!runningProject })),
      runningProject ? h(Progress, { st: run && run.project === runningProject ? run : { state: 'running', project: runningProject, label: 'Checking…' }, pal, onStop: stop }) : null,
      stalled && dismissed !== `${stalled.project}:${stalled.state}` ? h(Stalled, { st: stalled, onResume: resume, onDismiss: () => setDismissed(`${stalled.project}:${stalled.state}`) }) : null,
      run && run.state === 'done' && (run.warnings || []).length ? h('p', { className: 'ag-muted' }, `Finished with notes: ${run.warnings.join(' · ')}`) : null,
      body))
}


export default {
  id: 'ag4te',
  name: 'AG4TE',
  register(ctx) {
    const style = document.createElement('style')
    style.dataset.plugin = 'ag4te'
    style.textContent = CSS
    document.head.appendChild(style)
    ctx.onDispose(() => style.remove())
    ctx.registerMany([
      { id: 'page', area: sdk.ROUTES_AREA, data: { path: PATH }, render: () => jsx(Page, { ctx }) },
      { id: 'nav', area: sdk.SIDEBAR_NAV_AREA, data: { path: PATH, label: 'AG4TE', codicon: 'git-commit' } }
    ])
  }
}
