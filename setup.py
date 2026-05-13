from setuptools import setup, find_packages
from pathlib import Path

README = (Path(__file__).parent / "README.md").read_text(encoding="utf-8")

setup(
    name="devarch-framework",
    version="0.3.0",
    packages=find_packages(exclude=["tests*", "projects*", "analysis-vectors*"]),
    include_package_data=True,
    install_requires=[
        "click>=8.1",
        "sqlite-utils>=3.0",
        "datasette>=0.64.0",
    ],
    extras_require={
        "dev": ["pytest>=8.0"],
        "mcp": ["mcp[cli]>=1.0.0"],
    },
    entry_points={
        "console_scripts": [
            "devarch=archaeology.cli:main",
            "devarch-mcp=archaeology.mcp_server:main",
        ],
    },
    package_data={
        "archaeology": [
            "visualization/*.html",
            "templates/*.html",
        ],
    },
    python_requires=">=3.10",
    description="Forensic archaeology framework for git repositories",
    long_description=README,
    long_description_content_type="text/markdown",
    url="https://github.com/KyaniteLabs/devarch-framework",
    author="Simon Gonzalez de Cruz",
    author_email="simon@puenteworks.com",
    license="MIT",
    keywords=[
        "git", "repository", "archaeology", "code-analysis", "static-analysis",
        "commit-history", "software-forensics", "engineering-analytics", "cli",
        "sdlc", "git-history", "codebase-review", "developer-tools", "mcp",
    ],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Software Development :: Version Control :: Git",
        "Topic :: Scientific/Engineering :: Information Analysis",
        "Topic :: Utilities",
        "Environment :: Console",
        "Operating System :: OS Independent",
    ],
)
