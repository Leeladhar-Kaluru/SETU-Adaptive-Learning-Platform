import argparse

import pytest

from scripts.reset_supabase_app_data import require_reset_confirmation


def _args(**overrides):
    values = {
        "confirm": "",
        "backup": "",
        "allow_production": "",
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_reset_refuses_without_the_exact_confirmation(tmp_path):
    backup = tmp_path / "dump.sql"
    backup.write_text("select 1;", encoding="utf-8")
    with pytest.raises(SystemExit):
        require_reset_confirmation(_args(backup=str(backup)))


def test_reset_refuses_without_a_non_empty_backup(tmp_path):
    with pytest.raises(SystemExit):
        require_reset_confirmation(
            _args(
                confirm="DROP-ALL-APPLICATION-TABLES",
                backup=str(tmp_path / "missing.sql"),
                allow_production="SETU-PRODUCTION-RESET",
            )
        )


def test_reset_refuses_without_production_acknowledgement(tmp_path):
    backup = tmp_path / "dump.sql"
    backup.write_text("select 1;", encoding="utf-8")
    with pytest.raises(SystemExit):
        require_reset_confirmation(
            _args(
                confirm="DROP-ALL-APPLICATION-TABLES",
                backup=str(backup),
            )
        )


def test_reset_accepts_all_three_gates(tmp_path):
    backup = tmp_path / "dump.sql"
    backup.write_text("select 1;", encoding="utf-8")
    require_reset_confirmation(
        _args(
            confirm="DROP-ALL-APPLICATION-TABLES",
            backup=str(backup),
            allow_production="SETU-PRODUCTION-RESET",
        )
    )
