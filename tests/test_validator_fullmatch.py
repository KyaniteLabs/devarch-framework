"""Name validators must reject a trailing newline ("$" matches before one)."""

import pytest

from archaeology import api
from archaeology.db import builder, queries

TRAILING = ["users\n", "users\r", "users\n\n"]


@pytest.mark.parametrize("value", TRAILING)
def test_sql_table_validators_reject_trailing_line_breaks(value):
    with pytest.raises(ValueError):
        queries._validate_table_name(value)
    with pytest.raises(ValueError):
        builder._validate_table_name(value)


def test_sql_table_validators_still_accept_identifiers():
    assert queries._validate_table_name("commit_stats") == "commit_stats"
    assert builder._validate_table_name("_eras") == "_eras"
    assert queries._validate_order_by("date DESC") == "date DESC"


@pytest.mark.parametrize("value", ["demo\n", "demo\r"])
def test_api_project_name_rejects_trailing_line_breaks(value):
    assert api._validate_project_name(value) is False
