""" 
Project IO Tests
================
Unit tests for src.utils.project_io.

Author: Gia Tenica*
*Gia Tenica is an anagram for Agentic AI. Gia is a fully autonomous AI researcher,
for more information see: https://giatenica.com
"""

import json

import pytest

from src.utils.project_io import get_project_id, load_project_json


@pytest.mark.unit
def test_load_project_json_missing(tmp_path):
    assert load_project_json(str(tmp_path)) == {}


@pytest.mark.unit
def test_get_project_id_missing(tmp_path):
    assert get_project_id(str(tmp_path)) == "unknown"


@pytest.mark.unit
def test_get_project_id_valid(tmp_path):
    project = {"id": "abc12345", "title": "T"}
    (tmp_path / "project.json").write_text(json.dumps(project))
    assert get_project_id(str(tmp_path)) == "abc12345"


@pytest.mark.unit
def test_get_project_id_invalid_json(tmp_path):
    (tmp_path / "project.json").write_text("{not json")
    assert get_project_id(str(tmp_path)) == "unknown"
