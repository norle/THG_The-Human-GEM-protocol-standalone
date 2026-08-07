"""Build and validate the published documentation as a fresh site."""

from __future__ import annotations

import json
import posixpath
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).parents[2]


class _LinksAndIds(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []
        self.ids: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if attributes.get("href"):
            self.hrefs.append(attributes["href"])
        if attributes.get("id"):
            self.ids.add(attributes["id"])


def _build_site(tmp_path: Path) -> Path:
    site = tmp_path / "site"
    result = subprocess.run(
        [sys.executable, "-m", "mkdocs", "build", "--strict", "--site-dir", str(site)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return site


def _html_documents(site: Path) -> dict[Path, _LinksAndIds]:
    documents: dict[Path, _LinksAndIds] = {}
    for path in site.rglob("*.html"):
        parser = _LinksAndIds()
        parser.feed(path.read_text())
        documents[path] = parser
    return documents


def _target_file(site: Path, current: Path, href: str) -> tuple[Path, str]:
    parsed = urlparse(href)
    raw_path = unquote(parsed.path)
    site_prefix = "/THG_The-Human-GEM-protocol-standalone/"
    if raw_path.startswith(site_prefix):
        raw_path = raw_path[len(site_prefix) :]
    if raw_path.startswith("/"):
        target = site / raw_path.lstrip("/")
    else:
        relative = posixpath.normpath(
            posixpath.join(current.relative_to(site).parent.as_posix(), raw_path)
        )
        target = site / relative
    if raw_path in ("", ".") or href.endswith("/") or not target.suffix:
        target = target / "index.html"
    return target, unquote(parsed.fragment)


def test_documentation_build_has_no_unresolved_links_or_markup(tmp_path):
    site = _build_site(tmp_path)
    documents = _html_documents(site)

    assert (site / "reference" / "io-and-config" / "index.html").exists()
    assert (site / "examples" / "index.html").exists()
    assert not (site / "plans").exists()
    assert (site / "workflows" / "validation" / "index.html").exists()
    assert not (site / "protocol").exists()

    unresolved: list[str] = []
    for current, parser in documents.items():
        if current.name == "404.html":
            continue
        for href in parser.hrefs:
            parsed = urlparse(href)
            if parsed.scheme or parsed.netloc or href.startswith("javascript:"):
                continue
            target, fragment = _target_file(site, current, href)
            if not target.exists():
                unresolved.append(f"{current.relative_to(site)} -> {href}")
            elif fragment and target.suffix == ".html":
                target_parser = documents.get(target)
                if target_parser is None or fragment not in target_parser.ids:
                    unresolved.append(f"{current.relative_to(site)} -> {href}")
    assert not unresolved, "unresolved internal links:\n" + "\n".join(unresolved)

    literals = [
        str(path.relative_to(site))
        for path in site.rglob("*.html")
        if re.search(r":(?:func|mod):", path.read_text())
    ]
    assert not literals, "unresolved Sphinx markup: " + ", ".join(literals)


def test_navigation_uses_current_user_oriented_information_architecture():
    config = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    for label in (
        "Getting started:",
        "THG workflows:",
        "Tools:",
        "Reference:",
        "Contributing:",
        "About THG:",
    ):
        assert label in config
    for obsolete in (
        "Individual operations",
        "Phase 0 foundations",
        "Capability and evidence status",
        "Published protocol coverage",
    ):
        assert obsolete not in config


def test_canonical_api_inventory_and_workflow_links(tmp_path):
    site = _build_site(tmp_path)
    documents = _html_documents(site)
    inventory = json.loads((ROOT / "docs/api/api-inventory.json").read_text())
    workflow_inventory = json.loads(
        (ROOT / "docs/api/workflow-api-inventory.json").read_text()
    )

    canonical_symbols = {
        f"{module['module']}.{name}"
        for module in inventory["modules"]
        for name in module["symbols"]
    }
    all_ids = [identifier for parser in documents.values() for identifier in parser.ids]
    for symbol in canonical_symbols:
        assert all_ids.count(symbol) == 1, symbol

    for workflow in workflow_inventory["workflows"]:
        page = site / workflow["page"].replace(".md", "") / "index.html"
        html = page.read_text()
        for symbol in workflow["symbols"]:
            assert symbol in canonical_symbols, symbol
            assert f"#{symbol}" in html, f"{symbol} is not linked from {page}"

    for compatibility in inventory["compatibility_exports"]:
        package = compatibility["symbol"].removesuffix(".*")
        assert package not in all_ids, package
