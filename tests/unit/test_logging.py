"""Logging setup tests."""

import logging

from comet.logging_config import setup_logging


def test_setup_logging_survives_unwritable_dir(tmp_path):
    blocked = tmp_path / "not-a-dir"
    blocked.write_text("x")
    setup_logging("INFO", log_dir=blocked)
    root = logging.getLogger()
    assert root.handlers
    logging.getLogger("comet.test").info("still logs to console")
    setup_logging("DEBUG", log_dir=tmp_path)
    root = logging.getLogger()
    assert root.level == logging.DEBUG
    assert len(root.handlers) == 2

    log_file = tmp_path / "application.log"
    logging.getLogger("comet.test").info("test message")
    for handler in root.handlers:
        handler.flush()
    assert log_file.exists()
