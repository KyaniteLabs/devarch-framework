"""Unified design system for all DevArch HTML outputs.

Exports CSS, JS, and HTML constants for 3 selectable themes
(Warm, Clean Editorial, Modern Data). Every generator imports
from this module so all outputs share one visual identity.

Source of truth: shared/design-system-spec.md
"""

from __future__ import annotations

from typing import Any


# ── Google Fonts (all themes share this bundle) ─────────────────────────

GOOGLE_FONTS_LINK = """\
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@300;400;500;600&family=Lora:wght@400;600;700&family=Source+Sans+3:wght@300;400;500;600&family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">"""


# ── Theme CSS (all 3 theme token sets) ──────────────────────────────────

THEME_CSS = """<style>
/* ── DevArch Unified Design System ── */

/* ── Theme: Warm ── */
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

/* ── Theme: Clean Editorial (default) ── */
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

/* ── Theme: Modern Data ── */
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

/* ── Backward-compatible aliases ── */
/* Maps old token names (--bg, --surface, etc.) to new design system tokens
   so existing CSS references continue to work during migration. */
:root, [data-theme="warm"], [data-theme="editorial"], [data-theme="modern"] {
  --bg:            var(--bg-main);
  --surface:       var(--bg-surface);
  --surface2:      var(--bg-card);
  --surface3:      var(--bg-card-alt);
  --border-hover:  var(--accent-mid);
  --text2:         var(--text-2);
  --text3:         var(--text-muted);
}

/* ── Shared spacing & layout tokens ── */
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

/* ── Base reset ── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html { scroll-behavior: smooth; -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; }
body {
  background: var(--bg-main);
  color: var(--text);
  font-family: var(--font-body);
  line-height: 1.65;
  overflow-x: hidden;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
</style>"""


# ── Theme Switcher HTML ──────────────────────────────────────────────────

THEME_SWITCHER_HTML = """\
<div class="theme-switcher" role="radiogroup" aria-label="Color theme">
  <button data-theme="warm" aria-label="Warm theme" title="Warm">W</button>
  <button data-theme="editorial" aria-label="Editorial theme" title="Editorial">E</button>
  <button data-theme="modern" aria-label="Modern theme" title="Modern">M</button>
</div>"""

THEME_SWITCHER_CSS = """\
<style>
.theme-switcher {
  display: inline-flex;
  gap: 2px;
  background: var(--bg-card-alt);
  border-radius: var(--radius-sm);
  padding: 2px;
  border: 1px solid var(--border-subtle);
}
.theme-switcher button {
  background: transparent;
  border: none;
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 4px;
  cursor: pointer;
  transition: background var(--transition), color var(--transition);
}
.theme-switcher button:hover {
  background: var(--bg-hover);
  color: var(--text);
}
.theme-switcher button.active {
  background: var(--accent-dim);
  color: var(--accent);
}
</style>"""

THEME_SWITCHER_JS = """\
<script>
(function() {
  var saved = localStorage.getItem('devarch-theme') || 'editorial';
  document.documentElement.setAttribute('data-theme', saved);
  function updateActive() {
    var current = document.documentElement.getAttribute('data-theme') || 'editorial';
    document.querySelectorAll('.theme-switcher button[data-theme]').forEach(function(btn) {
      btn.classList.toggle('active', btn.getAttribute('data-theme') === current);
    });
  }
  updateActive();
  document.querySelectorAll('.theme-switcher button[data-theme]').forEach(function(btn) {
    btn.addEventListener('click', function() {
      var theme = btn.getAttribute('data-theme');
      document.documentElement.setAttribute('data-theme', theme);
      localStorage.setItem('devarch-theme', theme);
      updateActive();
      if (typeof window._rebuildCharts === 'function') window._rebuildCharts();
    });
  });
})();
</script>"""


# ── Chart Theme Integration ──────────────────────────────────────────────

CHART_THEME_JS = """\
<script>
function getThemeColors() {
  var s = getComputedStyle(document.documentElement);
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
</script>"""


# ── Accessibility CSS ────────────────────────────────────────────────────

ACCESSIBILITY_CSS = """\
<style>
/* Skip to content */
.skip-link {
  position: absolute;
  top: -40px;
  left: 0;
  background: var(--accent);
  color: var(--bg-main);
  padding: 8px 16px;
  z-index: 200;
  font-weight: 600;
  font-size: 14px;
  border-radius: 0 0 var(--radius-sm) 0;
  transition: top var(--transition);
}
.skip-link:focus {
  top: 0;
  text-decoration: none;
}

/* Focus visible */
:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

/* Reduced motion */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}

/* High contrast */
@media (prefers-contrast: more) {
  :root, [data-theme="editorial"] {
    --bg-main: #ffffff;
    --bg-surface: #ffffff;
    --text: #000000;
    --text-2: #1a1a1a;
    --text-muted: #333333;
    --border: #000000;
  }
  [data-theme="warm"], [data-theme="modern"] {
    --bg-main: #000000;
    --bg-surface: #0a0a0a;
    --text: #ffffff;
    --text-2: #e0e0e0;
    --text-muted: #cccccc;
    --border: #ffffff;
  }
}
</style>"""


# ── SEO Meta Tags ────────────────────────────────────────────────────────

def seo_meta(
    title: str,
    description: str,
    url: str = "",
    og_type: str = "website",
    json_ld: dict[str, Any] | None = None,
    image: str = "",
) -> str:
    """Generate meta description, OG, Twitter Card, robots, and JSON-LD tags.

    Args:
        title: Page title.
        description: Page description.
        url: Canonical URL (optional, for deployed sites).
        og_type: Open Graph type (website, article).
        json_ld: Optional Schema.org structured data dict.
        image: OG/Twitter image URL (optional, for social sharing previews).

    Returns:
        HTML string with meta tags.
    """
    import json

    tags = f"""\
<meta name="description" content="{description}">
<meta name="robots" content="index, follow">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:type" content="{og_type}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{description}">"""
    if url:
        tags += f'\n<link rel="canonical" href="{url}">\n<meta property="og:url" content="{url}">'
    if image:
        tags += f'\n<meta property="og:image" content="{image}">\n<meta name="twitter:image" content="{image}">'
    if json_ld:
        tags += f'\n<script type="application/ld+json">{json.dumps(json_ld, indent=2)}</script>'
    return tags


def seo_software_application(name: str, description: str, version: str = "", url: str = "", image: str = "") -> str:
    """Shorthand for SoftwareApplication JSON-LD (common in DevArch outputs)."""
    return seo_meta(
        title=f"{name} — DevArch Analysis",
        description=description,
        url=url,
        image=image,
        json_ld={
            "@context": "https://schema.org",
            "@type": "SoftwareApplication",
            "name": name,
            "applicationCategory": "DeveloperApplication",
            "description": description,
            **({"version": version} if version else {}),
            **({"url": url} if url else {}),
        },
    )


# ── Favicon ──────────────────────────────────────────────────────────────

FAVICON = """\
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>&#x26CF;</text></svg>">"""


# ── Convenience: full head bundle ────────────────────────────────────────

def head_bundle(
    title: str,
    description: str,
    include_charts: bool = False,
    include_d3: bool = False,
    url: str = "",
    json_ld: dict[str, Any] | None = None,
) -> str:
    """Generate the complete <head> content for a DevArch HTML page.

    Args:
        title: Page title.
        description: Page description (for meta + OG).
        include_charts: Include Chart.js CDN and theme integration.
        include_d3: Include D3.js CDN.
        url: Canonical URL (optional).
        json_ld: Schema.org structured data (optional).

    Returns:
        HTML string for everything that goes inside <head>.
    """
    parts = [
        '<meta charset="UTF-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
        f"<title>{title}</title>",
        FAVICON,
        GOOGLE_FONTS_LINK,
        seo_meta(title, description, url=url, json_ld=json_ld),
        THEME_CSS,
        THEME_SWITCHER_CSS,
        ACCESSIBILITY_CSS,
    ]
    if include_d3:
        parts.append('<script src="https://d3js.org/d3.v7.min.js"></script>')
    if include_charts:
        parts.append('<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>')
        parts.append(CHART_THEME_JS)
    return "\n".join(parts)


# ── Convenience: body-end bundle ─────────────────────────────────────────

def body_end_bundle() -> str:
    """Generate the theme switcher JS that goes at the end of <body>."""
    return THEME_SWITCHER_JS
