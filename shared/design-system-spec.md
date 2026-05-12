# DevArch Unified Design System

## Design Philosophy

Every HTML output from DevArch shares ONE design system. The user selects a theme (Warm, Clean Editorial, or Modern Data) and every page respects that choice. Differentiation comes from content and layout — never from different fonts, colors, or component styles.

## Theme Switcher

Every HTML file includes a theme toggle in its header. Selection persists via `localStorage` key `devarch-theme`. Default theme: `editorial`.

```html
<div class="theme-switcher" role="radiogroup" aria-label="Color theme">
  <button data-theme="warm" aria-label="Warm theme" title="Warm">W</button>
  <button data-theme="editorial" aria-label="Editorial theme" title="Editorial">E</button>
  <button data-theme="modern" aria-label="Modern theme" title="Modern">M</button>
</div>
```

```js
const saved = localStorage.getItem('devarch-theme') || 'modern';
document.documentElement.setAttribute('data-theme', saved);
document.querySelectorAll('[data-theme]').forEach(btn => {
  btn.addEventListener('click', () => {
    const theme = btn.getAttribute('data-theme');
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('devarch-theme', theme);
  });
});
```

## CSS Custom Properties (Design Tokens)

All three themes define the SAME token names. Components reference `var(--accent)` — never a raw hex value.

### Theme: Warm (`[data-theme="warm"]`)

```css
:root, [data-theme="warm"] {
  --bg-main:     #1f1a14;
  --bg-surface:  #2b241b;
  --bg-card:     #383020;
  --bg-card-alt: #453a28;
  --bg-hover:    #504230;

  --accent:      #d4a017;
  --accent-dim:  rgba(212, 160, 23, 0.12);
  --accent-mid:  rgba(212, 160, 23, 0.25);
  --secondary:   #b87333;
  --secondary-dim: rgba(184, 115, 51, 0.12);
  --success:     #4caf70;
  --success-dim: rgba(76, 175, 112, 0.12);
  --warning:     #e8a830;
  --warning-dim: rgba(232, 168, 48, 0.12);
  --danger:      #c0392b;
  --danger-dim:  rgba(192, 57, 43, 0.12);

  --text:        #f5e8c8;
  --text-2:      #c8b898;
  --text-muted:  #9d8f78;
  --text-faint:  #6b5f4e;

  --border:      rgba(212, 160, 23, 0.15);
  --border-subtle: rgba(255, 255, 255, 0.05);

  --font-display: 'DM Serif Display', Georgia, serif;
  --font-body:    'DM Sans', system-ui, sans-serif;
  --font-mono:    'JetBrains Mono', 'Courier New', monospace;
}
```

### Theme: Clean Editorial (`[data-theme="editorial"]`)

```css
[data-theme="editorial"] {
  --bg-main:     #faf9f7;
  --bg-surface:  #ffffff;
  --bg-card:     #ffffff;
  --bg-card-alt: #f5f4f2;
  --bg-hover:    #efeeec;

  --accent:      #1a5c3a;
  --accent-dim:  rgba(26, 92, 58, 0.08);
  --accent-mid:  rgba(26, 92, 58, 0.18);
  --secondary:   #2c5aa0;
  --secondary-dim: rgba(44, 90, 160, 0.08);
  --success:     #1a5c3a;
  --success-dim: rgba(26, 92, 58, 0.08);
  --warning:     #8a6d2b;
  --warning-dim: rgba(138, 109, 43, 0.08);
  --danger:      #a8282d;
  --danger-dim:  rgba(168, 40, 45, 0.08);

  --text:        #1a1a1a;
  --text-2:      #3d3d3d;
  --text-muted:  #6b6b6b;
  --text-faint:  #9d9d9d;

  --border:      rgba(0, 0, 0, 0.10);
  --border-subtle: rgba(0, 0, 0, 0.05);

  --font-display: 'Lora', Georgia, serif;
  --font-body:    'Source Sans 3', system-ui, sans-serif;
  --font-mono:    'IBM Plex Mono', 'Courier New', monospace;
}
```

### Theme: Modern Data (`[data-theme="modern"]`)

```css
[data-theme="modern"] {
  --bg-main:     #09090b;
  --bg-surface:  #0f0f12;
  --bg-card:     #16161a;
  --bg-card-alt: #1c1c21;
  --bg-hover:    #222228;

  --accent:      #3b82f6;
  --accent-dim:  rgba(59, 130, 246, 0.10);
  --accent-mid:  rgba(59, 130, 246, 0.22);
  --secondary:   #8b5cf6;
  --secondary-dim: rgba(139, 92, 246, 0.10);
  --success:     #10b981;
  --success-dim: rgba(16, 185, 129, 0.10);
  --warning:     #f59e0b;
  --warning-dim: rgba(245, 158, 11, 0.10);
  --danger:      #ef4444;
  --danger-dim:  rgba(239, 68, 68, 0.10);

  --text:        #edf0f7;
  --text-2:      #b4bccf;
  --text-muted:  #6b7a9a;
  --text-faint:  #3d4c6a;

  --border:      rgba(255, 255, 255, 0.08);
  --border-subtle: rgba(255, 255, 255, 0.04);

  --font-display: 'Inter', system-ui, sans-serif;
  --font-body:    'Inter', system-ui, sans-serif;
  --font-mono:    'JetBrains Mono', 'Courier New', monospace;
}
```

## Shared Spacing & Layout Tokens

```css
:root {
  --space-1:  4px;
  --space-2:  8px;
  --space-3:  12px;
  --space-4:  16px;
  --space-5:  20px;
  --space-6:  24px;
  --space-8:  32px;
  --space-10: 40px;
  --space-12: 48px;
  --space-16: 64px;
  --space-20: 80px;

  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-xl: 16px;

  --max-width: 1200px;

  --shadow-sm:  0 1px 2px rgba(0,0,0,0.08);
  --shadow-md:  0 4px 12px rgba(0,0,0,0.10);
  --shadow-lg:  0 8px 24px rgba(0,0,0,0.14);

  --transition: 180ms ease;
}
```

## Font Loading

Every file loads the same Google Fonts bundle. Individual themes select from this pool:

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@300;400;500;600&family=Lora:wght@400;600;700&family=Source+Sans+3:wght@300;400;500;600&family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
```

## Component Patterns

Every component uses ONLY design tokens. No raw colors, no magic numbers.

### Card
```css
.card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--space-6);
  transition: background var(--transition), border-color var(--transition);
}
.card:hover {
  background: var(--bg-hover);
  border-color: var(--accent-mid);
}
```

### Badge
```css
.badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 500;
}
.badge--success { background: var(--success-dim); color: var(--success); }
.badge--warning { background: var(--warning-dim); color: var(--warning); }
.badge--danger  { background: var(--danger-dim);  color: var(--danger);  }
.badge--accent  { background: var(--accent-dim);  color: var(--accent);  }
```

### Section Header
```css
.section-label {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-bottom: var(--space-2);
}
.section-title {
  font-family: var(--font-display);
  font-size: 24px;
  font-weight: 700;
  color: var(--text);
  line-height: 1.3;
}
```

### Table
```css
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}
th {
  font-family: var(--font-mono);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
  padding: var(--space-3) var(--space-4);
  text-align: left;
  border-bottom: 1px solid var(--border);
}
td {
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--border-subtle);
  color: var(--text-2);
}
```

### Chart.js Theme Integration

Charts must respect the active theme. Use CSS variable values in JS:

```js
function getThemeColors() {
  const s = getComputedStyle(document.documentElement);
  return {
    accent:    s.getPropertyValue('--accent').trim(),
    secondary: s.getPropertyValue('--secondary').trim(),
    success:   s.getPropertyValue('--success').trim(),
    warning:   s.getPropertyValue('--warning').trim(),
    danger:    s.getPropertyValue('--danger').trim(),
    text:      s.getPropertyValue('--text').trim(),
    muted:     s.getPropertyValue('--text-muted').trim(),
    border:    s.getPropertyValue('--border').trim(),
    bg:        s.getPropertyValue('--bg-card').trim(),
  };
}
```

Charts must be recreated or updated when theme changes (listen for theme switch clicks).

## Accessibility (Non-negotiable)

Every HTML file MUST include:
1. Skip-to-content link as first focusable element
2. `<main>` landmark wrapping primary content
3. `role="img"` + `aria-label` on every chart canvas
4. `:focus-visible` styles using `var(--accent)`
5. `prefers-reduced-motion` media query disabling animations
6. `lang="en"` on `<html>`
7. `<meta name="viewport">` for responsive behavior

## File Identity

Each page gets a subtle identity marker — a small colored dot or label in the header indicating its pipeline stage — NOT a completely different design language.

Stage colors (shared across all themes):
- Stage 05 (Analyze): `var(--secondary)`
- Stage 06 (Visualize): `var(--accent)`
- Stage 07 (Report): `var(--accent)`
- Stage 08 (Audit): `var(--success)` or `var(--danger)`
- Stage 09 (Strategy): `var(--secondary)`
