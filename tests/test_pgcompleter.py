import json
import pytest
from pgcli import pgcompleter
import tempfile


def test_load_alias_map_file_missing_file():
    with pytest.raises(
        pgcompleter.InvalidMapFile,
        match=r"Cannot read alias_map_file - /path/to/non-existent/file.json does not exist$",
    ):
        pgcompleter.load_alias_map_file("/path/to/non-existent/file.json")


def test_load_alias_map_file_invalid_json(tmp_path):
    fpath = tmp_path / "foo.json"
    fpath.write_text("this is not valid json")
    with pytest.raises(pgcompleter.InvalidMapFile, match=r".*is not valid json$"):
        pgcompleter.load_alias_map_file(str(fpath))


@pytest.mark.parametrize(
    "table_name, alias",
    [
        ("SomE_Table", "SET"),
        ("SOmeTabLe", "SOTL"),
        ("someTable", "T"),
    ],
)
def test_generate_alias_uses_upper_case_letters_from_name(table_name, alias):
    assert pgcompleter.generate_alias(table_name) == alias


@pytest.mark.parametrize(
    "table_name, alias",
    [
        ("some_tab_le", "stl"),
        ("s_ome_table", "sot"),
        ("sometable", "s"),
    ],
)
def test_generate_alias_uses_first_char_and_every_preceded_by_underscore(
    table_name, alias
):
    assert pgcompleter.generate_alias(table_name) == alias


@pytest.mark.parametrize(
    "table_name, alias_map, alias",
    [
        ("some_table", {"some_table": "my_alias"}, "my_alias"),
        pytest.param(
            "some_other_table", {"some_table": "my_alias"}, "sot", id="no_match_in_map"
        ),
    ],
)
def test_generate_alias_can_use_alias_map(table_name, alias_map, alias):
    assert pgcompleter.generate_alias(table_name, alias_map) == alias


@pytest.mark.parametrize(
    "table_name, alias_map, alias",
    [
        ("some_table", {"some_table": "my_alias"}, "my_alias"),
    ],
)
def test_pgcompleter_alias_uses_configured_alias_map(table_name, alias_map, alias):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as alias_map_file:
        alias_map_file.write(json.dumps(alias_map))
        alias_map_file.seek(0)
        completer = pgcompleter.PGCompleter(
            settings={
                "generate_aliases": True,
                "alias_map_file": alias_map_file.name,
            }
        )
        assert completer.alias(table_name, []) == alias


@pytest.mark.parametrize(
    "table_name, alias_map, alias",
    [
        ("SomeTable", {"SomeTable": "my_alias"}, "my_alias"),
    ],
)
def test_generate_alias_prefers_alias_over_upper_case_name(
    table_name, alias_map, alias
):
    assert pgcompleter.generate_alias(table_name, alias_map) == alias


@pytest.mark.parametrize(
    "table_name, alias",
    [
        ("Some_tablE", "SE"),
        ("SomeTab_le", "ST"),
    ],
)
def test_generate_alias_prefers_upper_case_name_over_underscore_name(table_name, alias):
    assert pgcompleter.generate_alias(table_name) == alias
