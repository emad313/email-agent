from storage import Storage


def test_duplicate_message_is_ignored(tmp_path):
    storage = Storage(tmp_path / "state.db")
    assert storage.record_message("id", "a@example.com", "subject", "processing")
    assert not storage.record_message("id", "a@example.com", "subject", "processing")
    assert storage.has_message("id")


def test_status_update_and_action_log(tmp_path):
    storage = Storage(tmp_path / "state.db")
    storage.record_message("id", "a@example.com", "subject", "processing")
    storage.update_message("id", "drafted", "saved")
    storage.log_action("id", "reply", "success")
    assert storage.get_status_counts() == {"drafted": 1}


def test_error_message_can_be_retried(tmp_path):
    storage = Storage(tmp_path / "state.db")
    assert storage.record_message("id", "a@example.com", "subject", "processing")
    storage.update_message("id", "error", "temporary failure")
    assert storage.record_message("id", "a@example.com", "subject", "processing")
    assert storage.get_message("id")["status"] == "processing"
