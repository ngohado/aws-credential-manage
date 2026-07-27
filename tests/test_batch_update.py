"""Tests for batch credential maintenance."""

from types import SimpleNamespace

from aws_credential_manager.core.credential_manager import CredentialManager


class FakeConfig:
    def __init__(self, names):
        self._profiles = [{"name": name} for name in names]

    def get_aws_profiles(self):
        return self._profiles


class FakeOperationManager:
    def __init__(self, result=True):
        self.result = result
        self.calls = []

    def update_profile(self, profile_name, dry_run=False):
        self.calls.append((profile_name, dry_run))
        return self.result

    def refresh_key(self, profile_name, dry_run=False):
        self.calls.append((profile_name, dry_run))
        return self.result


def make_manager(names=("profile-one", "profile-two")):
    manager = CredentialManager.__new__(CredentialManager)
    manager.config = FakeConfig(names)
    manager.passwords = SimpleNamespace()
    manager.access_keys = SimpleNamespace()
    return manager


def test_password_filters_exclusions_in_config_order(capsys):
    manager = make_manager(("profile-one", "profile-two", "profile-three"))
    password = FakeOperationManager()
    manager.passwords.update_profile = password.update_profile

    assert manager.batch_update("password", ["profile-two"]) is True
    assert password.calls == [
        ("profile-one", False),
        ("profile-three", False),
    ]
    assert "2/2" in capsys.readouterr().out


def test_access_key_forwards_dry_run():
    manager = make_manager()
    access_keys = FakeOperationManager()
    manager.access_keys.refresh_key = access_keys.refresh_key

    assert manager.batch_update("access-key", [], dry_run=True) is True
    assert access_keys.calls == [
        ("profile-one", True),
        ("profile-two", True),
    ]


def test_both_runs_password_before_access_key_per_profile():
    manager = make_manager()
    events = []
    manager.passwords.update_profile = lambda name, dry_run=False: (
        events.append(("password", name)) or True
    )
    manager.access_keys.refresh_key = lambda name, dry_run=False: (
        events.append(("access-key", name)) or True
    )

    assert manager.batch_update("both") is True
    assert events == [
        ("password", "profile-one"),
        ("access-key", "profile-one"),
        ("password", "profile-two"),
        ("access-key", "profile-two"),
    ]


def test_both_skips_access_key_after_password_failure_and_continues():
    manager = make_manager()
    password_calls = []
    access_key_calls = []
    manager.passwords.update_profile = lambda name, dry_run=False: (
        password_calls.append(name) or name == "profile-two"
    )
    manager.access_keys.refresh_key = lambda name, dry_run=False: (
        access_key_calls.append(name) or True
    )

    assert manager.batch_update("both") is False
    assert password_calls == ["profile-one", "profile-two"]
    assert access_key_calls == ["profile-two"]


def test_rejects_unknown_exclusion():
    assert make_manager().batch_update("password", ["missing-profile"]) is False


def test_rejects_excluding_every_profile():
    manager = make_manager()
    assert manager.batch_update("password", ["profile-one", "profile-two"]) is False


def test_continues_after_failure_and_returns_false():
    manager = make_manager()
    calls = []
    manager.passwords.update_profile = lambda name, dry_run=False: (
        calls.append(name) or name == "profile-two"
    )

    assert manager.batch_update("password") is False
    assert calls == ["profile-one", "profile-two"]


def test_cli_batch_update_dispatches_operation(monkeypatch):
    import importlib

    calls = []

    class FakeManager:
        def __init__(self, credentials_path, vault):
            pass

        def check_op_session(self):
            return True

        def batch_update(self, operation, excluded_profiles, dry_run):
            calls.append((operation, excluded_profiles, dry_run))
            return True

    cli_main = importlib.import_module("aws_credential_manager.cli.main")
    monkeypatch.setattr(cli_main, "CredentialManager", FakeManager)

    assert cli_main.main([
        "--dry-run", "batch-update", "access-key",
        "--exclude", "profile-one",
        "--exclude", "profile-two",
    ]) == 0
    assert calls == [
        ("access-key", ["profile-one", "profile-two"], True),
    ]


def test_cli_batch_update_returns_nonzero_when_batch_fails(monkeypatch):
    import importlib

    class FakeManager:
        def __init__(self, credentials_path, vault):
            pass

        def check_op_session(self):
            return True

        def batch_update(self, operation, excluded_profiles, dry_run):
            return False

    cli_main = importlib.import_module("aws_credential_manager.cli.main")
    monkeypatch.setattr(cli_main, "CredentialManager", FakeManager)

    assert cli_main.main(["batch-update", "password"]) == 1
