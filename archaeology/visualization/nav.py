"""Shared navigation component for all dev-archaeology HTML deliverables.

Provides a consistent nav bar across all HTML pages with:
- Project name linking to project index
- Tab-style navigation to sibling pages
- "Home" link back to master dashboard
- Mobile hamburger menu
- PostHog analytics integration
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


# ── PostHog snippet ──────────────────────────────────────────────────

POSTHOG_SNIPPET = ""


# ── Shared CSS ───────────────────────────────────────────────────────

NAV_CSS = """<style>
/* ── Site Nav ── */
.site-nav{position:sticky;top:0;z-index:100;background:var(--surface,#0c1018);border-bottom:1px solid var(--border,#1a2232);padding:0 24px;display:flex;align-items:center;gap:12px;height:52px;font-family:var(--font-display,'Space Grotesk',sans-serif);backdrop-filter:blur(12px)}
.site-nav .nav-home{font-weight:700;font-size:14px;letter-spacing:.02em;color:var(--text3,#6a7888);text-decoration:none;white-space:nowrap;padding:4px 10px;border-radius:var(--radius-sm,6px);transition:color .15s,background .15s}
.site-nav .nav-home:hover{color:var(--text,#e8ecf2);background:var(--surface2,#141a24)}
.site-nav .nav-sep{width:1px;height:24px;background:var(--border,#1a2232)}
.site-nav .nav-project{font-weight:600;font-size:15px;color:var(--text,#e8ecf2);letter-spacing:-.01em;white-space:nowrap}
.site-nav .nav-links{display:flex;gap:4px;align-items:center;margin-left:auto}
.site-nav .nav-links a{font-size:13px;font-weight:500;color:var(--text2,#8d99aa);text-decoration:none;padding:6px 12px;border-radius:var(--radius-sm,6px);transition:color .15s,background .15s;white-space:nowrap}
.site-nav .nav-links a:hover{color:var(--text,#e8ecf2);background:var(--surface2,#141a24)}
.site-nav .nav-links a.active{color:var(--text,#e8ecf2);background:var(--surface3,#1c2432)}
.nav-body{margin-top:0}
/* ── Mobile hamburger ── */
.nav-hamburger{display:none;background:none;border:none;color:var(--text2,#8d99aa);font-size:22px;cursor:pointer;padding:4px 8px;margin-left:auto}
@media(max-width:768px){
  .site-nav{padding:0 16px;flex-wrap:wrap;height:auto;min-height:52px}
  .site-nav .nav-links{display:none;flex-direction:column;width:100%;padding:8px 0 12px;gap:2px}
  .site-nav .nav-links.open{display:flex}
  .site-nav .nav-links a{padding:10px 12px;font-size:15px}
  .nav-hamburger{display:block}
}
</style>"""


def _discover_sibling_pages(current_file: Path, project_deliverables_dir: Path) -> list[dict[str, str]]:
    """Find all HTML files in the same visuals/ directory (or deliverables/ for legacy).

    Returns list of {name, href, is_active}.
    """
    visuals_dir = project_deliverables_dir / "visuals"
    if not visuals_dir.exists():
        visuals_dir = project_deliverables_dir

    pages = []
    for html_file in sorted(visuals_dir.glob("*.html")):
        name = html_file.stem
        # Skip index pages
        if name == "index":
            continue
        # Pretty display name
        display = name.replace("-", " ").replace("_", " ").title()
        if display == "Archaeology":
            display = "Dashboard"
        elif display == "Agent Benchmark":
            display = "Agents"
        elif display == "Playbook":
            display = "Playbook"
        elif display == "Report":
            display = "Report"
        pages.append({
            "name": display,
            "href": html_file.name,
            "is_active": current_file.name == html_file.name,
        })
    return pages


def generate_nav(
    project_name: str,
    current_file: Path,
    project_deliverables_dir: Path,
    include_posthog: bool = True,
    home_url: str = "/",
) -> str:
    """Generate the shared nav bar HTML for a deliverable page.

    Args:
        project_name: Display name for the project.
        current_file: Path to the current HTML file (for active state).
        project_deliverables_dir: Path to the project's deliverables/ directory.
        include_posthog: Whether to include PostHog analytics snippet.
        home_url: URL for the "Home" link (master dashboard).

    Returns:
        HTML string containing the nav bar, CSS, and optional PostHog.
    """
    pages = _discover_sibling_pages(current_file, project_deliverables_dir)

    # Build page links
    page_links = ""
    for page in pages:
        active_class = " active" if page["is_active"] else ""
        # Determine relative path from current file to visuals dir
        if current_file.parent.name == "visuals":
            href = page["href"]
        else:
            href = f"visuals/{page['href']}"
        page_links += f'<a href="{href}"{active_class}>{page["name"]}</a>\n      '

    # Determine relative path to index.html
    if current_file.parent.name == "visuals":
        project_index_href = "index.html"
    else:
        project_index_href = "visuals/index.html"

    nav_html = f"""{NAV_CSS}
{POSTHOG_SNIPPET if include_posthog else ''}
<nav class="site-nav">
  <a href="{home_url}" class="nav-home">Home</a>
  <div class="nav-sep"></div>
  <span class="nav-project">{project_name.upper()}</span>
  <button class="nav-hamburger" onclick="document.querySelector('.nav-links').classList.toggle('open')" aria-label="Menu">&#9776;</button>
  <div class="nav-links">
    <a href="{project_index_href}">Overview</a>
    {page_links}
  </div>
</nav>
"""
    return nav_html


def generate_nav_simple(
    project_name: str,
    pages: list[dict[str, str]],
    active_page: str,
    include_posthog: bool = True,
    home_url: str = "/",
) -> str:
    """Generate nav bar with explicit page list (for generated dashboards).

    Args:
        project_name: Display name for the project.
        pages: List of {name, href} dicts.
        active_page: The href of the active page.
        include_posthog: Whether to include PostHog snippet.
        home_url: URL for the home link.

    Returns:
        HTML string.
    """
    page_links = ""
    for page in pages:
        active_class = " active" if page["href"] == active_page else ""
        page_links += f'<a href="{page["href"]}"{active_class}>{page["name"]}</a>\n      '

    nav_html = f"""{NAV_CSS}
{POSTHOG_SNIPPET if include_posthog else ''}
<nav class="site-nav">
  <a href="{home_url}" class="nav-home">Home</a>
  <div class="nav-sep"></div>
  <span class="nav-project">{project_name.upper()}</span>
  <button class="nav-hamburger" onclick="document.querySelector('.nav-links').classList.toggle('open')" aria-label="Menu">&#9776;</button>
  <div class="nav-links">
    {page_links}
  </div>
</nav>
"""
    return nav_html


def inject_nav_into_html(html: str, nav_html: str) -> str:
    """Inject the nav bar into an existing HTML document.

    Inserts right after <body> tag. Adds class="nav-body" to main content
    to account for the sticky nav height.
    """
    if "<body" not in html:
        return html

    # Insert nav after <body...>
    body_idx = html.index("<body")
    body_close = html.index(">", body_idx) + 1
    html = html[:body_close] + "\n" + nav_html + html[body_close:]

    # If there's a root wrapper div, give it nav-body class
    # This adds top margin to account for sticky nav
    if 'class="container"' in html:
        html = html.replace('class="container"', 'class="container nav-body"', 1)
    elif '<div id="root">' in html:
        html = html.replace('<div id="root">', '<div id="root" class="nav-body">', 1)

    return html
