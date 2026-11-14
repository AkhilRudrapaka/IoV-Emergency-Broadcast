"""The portal's downloads are copies of the project's own files; a stale copy is a wrong download.
After changing any of the sources below, run: python build_portal_assets.py"""
import os
import zipfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
read = lambda *path: open(os.path.join(ROOT, *path), "rb").read()


@pytest.mark.parametrize("site", ["portal", "documentation_website/portal"])
def test_portal_downloads_are_current_copies(site):
    sources = {"RESULTS.md": "results/urban/summaries/RESULTS.md", "PROJECT_GUIDE.md": "PROJECT_GUIDE.md",
               "Project_Website_Documentation_Portal.docx": "Project_Website_Documentation_Portal.docx"}
    if site == "portal":
        sources["config.py"] = "config.py"
    for name, source in sources.items():
        assert read(*site.split("/"), "downloads", name) == read(*source.split("/")), \
            f"{site}/downloads/{name} is not a copy of {source}: run python build_portal_assets.py"


def test_source_bundle_holds_the_current_code():
    with zipfile.ZipFile(os.path.join(ROOT, "portal", "downloads", "source.zip")) as bundle:
        names = set(bundle.namelist())
        stale = [n for n in sorted(names) if n != "SNAPSHOT.txt" and bundle.read(n) != read(*n.split("/"))]
    modules = {f for f in os.listdir(ROOT) if f.endswith(".py")}
    tests = {f"validation/{f}" for f in os.listdir(os.path.join(ROOT, "validation")) if f.endswith(".py")}
    assert modules | tests | {"results_viewer.html", "README.md"} <= names, "files missing from source.zip"
    assert not stale, f"source.zip holds old copies of {stale}: run python build_portal_assets.py"
