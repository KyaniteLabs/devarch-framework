from setuptools import setup, find_packages
from pathlib import Path

README = (Path(__file__).parent / "README.md").read_text(encoding="utf-8")

setup(
    name="devarch-framework",
    version="0.2.0",
    packages=find_packages(exclude=["tests*", "projects*", "analysis-vectors*"]),
    install_requires=[
        "click>=8.1",
        "sqlite-utils>=3.0",
        "datasette>=0.64.0",
    ],
    extras_require={
        "dev": ["pytest>=8.0"],
    },
    entry_points={
        "console_scripts": [
            "devarch=archaeology.cli:main",
        ],
    },
    python_requires=">=3.10",
    description="Forensic archaeology framework for git repositories",
    long_description=README,
    long_description_content_type="text/markdown",
    url="https://github.com/Pastorsimon1798/devarch-framework",
    author="Simon Gonzalez de Cruz",
    author_email="",
    license="MIT",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Build Tools",
        "Topic :: Software Development :: Version Control :: Git",
    ],
)
