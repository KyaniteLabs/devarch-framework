#!/usr/bin/env python3
"""
Feature parity check tool for comparing DEV-ARCH and devarch-framework.

This script compares two repositories to ensure feature parity across:
- CLI Commands
- Analysis Vectors
- Python Modules
- Config Files
- Test Files
- Templates

Returns exit code 0 if parity is 100%, 1 otherwise.
"""

import argparse
import ast
import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple


class ParityChecker:
    """Check feature parity between two repositories."""

    def __init__(self, repo_a: str, repo_b: str):
        self.repo_a = Path(repo_a).resolve()
        self.repo_b = Path(repo_b).resolve()
        self.results = []

    def check_cli_commands(self) -> Tuple[bool, str, Set[str]]:
        """Compare CLI commands registered in Click apps."""
        cli_a = self.repo_a / "archaeology" / "cli.py"
        cli_b = self.repo_b / "archaeology" / "cli.py"

        if not cli_a.exists() or not cli_b.exists():
            return False, "CLI files not found", set()

        commands_a = self._extract_click_commands(cli_a)
        commands_b = self._extract_click_commands(cli_b)

        # Filter out internal functions (starting with _)
        commands_a = {c for c in commands_a if not c.startswith('_')}
        commands_b = {c for c in commands_b if not c.startswith('_')}

        missing = commands_a - commands_b
        total = len(commands_a)
        present = total - len(missing)

        if missing:
            return False, f"GAP ({present}/{total} in dev-arch, {len(commands_b)}/{total} in framework)", missing
        return True, f"PARITY ({total}/{total})", set()

    def _extract_click_commands(self, cli_file: Path) -> Set[str]:
        """Extract Click command names from a CLI file."""
        commands = set()

        try:
            with open(cli_file, 'r') as f:
                tree = ast.parse(f.read())

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Check if this function is decorated as a command
                    for decorator in node.decorator_list:
                        # Look for @main.command() or @click.command()
                        if isinstance(decorator, ast.Call):
                            if hasattr(decorator.func, 'attr'):
                                if decorator.func.attr == 'command':
                                    commands.add(node.name)
                            elif isinstance(decorator.func, ast.Name):
                                if decorator.func.id == 'command':
                                    commands.add(node.name)
                        # Look for @main.command (without call)
                        elif isinstance(decorator, ast.Attribute):
                            if decorator.attr == 'command':
                                commands.add(node.name)

        except Exception as e:
            print(f"Warning: Could not parse {cli_file}: {e}", file=sys.stderr)

        return commands

    def check_analysis_vectors(self) -> Tuple[bool, str, Set[str]]:
        """Compare analysis-vectors directories."""
        vectors_a = self.repo_a / "analysis-vectors"
        vectors_b = self.repo_b / "analysis-vectors"

        if not vectors_a.exists() or not vectors_b.exists():
            return False, "analysis-vectors directories not found", set()

        files_a = {f.name for f in vectors_a.glob("*.md")}
        files_b = {f.name for f in vectors_b.glob("*.md")}

        missing = files_a - files_b
        total = len(files_a)
        present = total - len(missing)

        if missing:
            return False, f"GAP ({present}/{total} in dev-arch, {len(files_b)}/{total} in framework)", missing
        return True, f"PARITY ({total}/{total})", set()

    def check_python_modules(self) -> Tuple[bool, str, Set[str]]:
        """Compare archaeology/ package structure."""
        pkg_a = self.repo_a / "archaeology"
        pkg_b = self.repo_b / "archaeology"

        if not pkg_a.exists() or not pkg_b.exists():
            return False, "archaeology packages not found", set()

        files_a = self._get_python_files(pkg_a)
        files_b = self._get_python_files(pkg_b)

        missing = files_a - files_b
        total = len(files_a)
        present = total - len(missing)

        if missing:
            return False, f"GAP ({present}/{total} in dev-arch, {len(files_b)}/{total} in framework)", missing
        return True, f"PARITY ({total}/{total})", set()

    def _get_python_files(self, pkg_dir: Path) -> Set[str]:
        """Get all Python files relative to package root."""
        files = set()
        for py_file in pkg_dir.rglob("*.py"):
            # Skip __pycache__ and test directories
            if "__pycache__" in str(py_file):
                continue
            # Get relative path from package root
            rel_path = py_file.relative_to(pkg_dir)
            files.add(str(rel_path))
        return files

    def check_config_files(self) -> Tuple[bool, str, Set[str]]:
        """Compare config/ directories."""
        config_a = self.repo_a / "config"
        config_b = self.repo_b / "config"

        if not config_a.exists() or not config_b.exists():
            return False, "config directories not found", set()

        expected_files = {
            "defaults.json",
            "project-schema.json",
            "profile.json",
            "datasette-metadata.yaml"
        }

        files_a = {f.name for f in config_a.iterdir() if f.is_file()}
        files_b = {f.name for f in config_b.iterdir() if f.is_file()}

        # Check for expected files in both
        missing_a = expected_files - files_a
        missing_b = expected_files - files_b

        if missing_a or missing_b:
            return False, "GAP (missing expected config files)", missing_a | missing_b

        return True, f"PARITY ({len(expected_files)}/{len(expected_files)})", set()

    def check_test_files(self) -> Tuple[bool, str, Set[str]]:
        """Compare tests/ directories."""
        tests_a = self.repo_a / "tests"
        tests_b = self.repo_b / "tests"

        if not tests_a.exists() or not tests_b.exists():
            return False, "tests directories not found", set()

        files_a = {f.name for f in tests_a.glob("test_*.py")}
        files_b = {f.name for f in tests_b.glob("test_*.py")}

        missing = files_a - files_b
        total = len(files_a)
        present = total - len(missing)

        if missing:
            return False, f"GAP ({present}/{total} in dev-arch, {len(files_b)}/{total} in framework)", missing
        return True, f"PARITY ({total}/{total})", set()

    def check_templates(self) -> Tuple[bool, str, Set[str]]:
        """Compare visualization templates."""
        viz_a = self.repo_a / "archaeology" / "visualization"
        viz_b = self.repo_b / "archaeology" / "visualization"

        if not viz_a.exists() or not viz_b.exists():
            return False, "visualization directories not found", set()

        templates_a = {f.name for f in viz_a.glob("*.html")}
        templates_b = {f.name for f in viz_b.glob("*.html")}

        missing = templates_a - templates_b
        total = len(templates_a)
        present = total - len(missing)

        if missing:
            return False, f"GAP ({present}/{total} in dev-arch, {len(templates_b)}/{total} in framework)", missing
        return True, f"PARITY ({total}/{total})", set()

    def run_all_checks(self) -> int:
        """Run all parity checks and return exit code."""
        print(f"PARITY CHECK: DEV-ARCH vs devarch-framework")
        print("═" * 55)
        print()

        checks = [
            ("CLI Commands", self.check_cli_commands),
            ("Analysis Vectors", self.check_analysis_vectors),
            ("Python Modules", self.check_python_modules),
            ("Config Files", self.check_config_files),
            ("Tests", self.check_test_files),
            ("Templates", self.check_templates),
        ]

        all_passed = True
        gap_count = 0

        for name, check_func in checks:
            passed, status, missing = check_func()
            symbol = "✓" if passed else "✗"
            print(f"{name}: {status} {symbol}")

            if not passed:
                all_passed = False
                if missing:
                    gap_count += len(missing)
                    for item in sorted(missing):
                        print(f"  Missing: {item}")

        print()
        if all_passed:
            print("Overall: 100% parity ✓")
            return 0
        else:
            total_checks = len(checks)
            passed_checks = sum(1 for _, func in checks if func()[0])
            percentage = int((passed_checks / total_checks) * 100)
            print(f"Overall: {percentage}% parity ({gap_count} gap{'s' if gap_count != 1 else ''})")
            return 1


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Check feature parity between dev-archaeology and devarch-framework"
    )
    parser.add_argument(
        "--dev-arch",
        default=os.getcwd(),
        help="Path to DEV-ARCH repository"
    )
    parser.add_argument(
        "--framework",
        default=os.getcwd(),
        help="Path to devarch-framework repository"
    )

    args = parser.parse_args()

    checker = ParityChecker(args.dev_arch, args.framework)
    return checker.run_all_checks()


if __name__ == "__main__":
    sys.exit(main())
