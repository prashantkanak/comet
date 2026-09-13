"""Logging setup tests."""

import logging

from comet.logging_config import setup_logging


def test_setup_logging_creates_log_file(tmp_path):
    setup_logging("DEBUG", log_dir=tmp_path)
    root = logging.getLogger()
    assert root.level == logging.DEBUG
    assert len(root.handlers) == 2

    log_file = tmp_path / "application.log"
    logging.getLogger("comet.test").info("test message")
    for handler in root.handlers:
        handler.flush()
    assert log_file.exists()
