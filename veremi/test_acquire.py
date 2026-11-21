"""The dataset extractor must refuse archive members that would escape the extraction folder (zip-slip)."""
import zipfile
from pathlib import Path

import pytest

from veremi.acquire import safe_target, vector


@pytest.mark.parametrize("name", ["../evil.json", "a/../../evil.json", "/abs/evil.json", "C:/evil.json", "a\\..\\..\\x"])
def test_unsafe_member_names_are_rejected(tmp_path, name):
    with pytest.raises(ValueError):
        safe_target(tmp_path, zipfile.ZipInfo(name))


def test_symlink_members_are_rejected(tmp_path):
    link = zipfile.ZipInfo("Train/link.json")
    link.external_attr = 0o120777 << 16
    with pytest.raises(ValueError):
        safe_target(tmp_path, link)


def test_normal_member_and_vector_parsing(tmp_path):
    assert safe_target(tmp_path, zipfile.ZipInfo("x/Train/veh_1.json")) == (tmp_path / "x/Train/veh_1.json").resolve()
    assert vector("216557.3,452459.5,0.0") == [216557.3, 452459.5, 0.0]
    assert vector("1,2") is None and vector("nan,1,2") is None and vector("a,b,c") is None
