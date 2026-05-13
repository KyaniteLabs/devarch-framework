"""DevArch MCP Server — AI assistant integration for repository archaeology."""

from .server import mcp


def main():
    """Entry point for the devarch-mcp command."""
    mcp.run(transport="stdio")


__all__ = ["mcp", "main"]
