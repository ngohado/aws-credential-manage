"""Tests for password rotation ordering guarantees."""

from aws_credential_manager.core.password_manager import PasswordManager


class FakeAWS:
    def __init__(self):
        self.login_profile_updates = []

    def get_user(self, profile_name):
        return {"UserName": f"user-{profile_name}"}

    def update_login_profile(self, profile_name, username, password):
        self.login_profile_updates.append((profile_name, username))


class FakeOnePassword:
    def __init__(self, item=None):
        self.item = item
        self.edits = []

    def get_item(self, item_title):
        return self.item

    def generate_password(self):
        return "generated-password"

    def edit_item(self, item_title, **fields):
        self.edits.append(item_title)


class FakeConfig:
    def get_profile_mapping(self, profile_name):
        return None


def make_manager(item=None):
    aws = FakeAWS()
    op = FakeOnePassword(item)
    return PasswordManager(aws, op, FakeConfig()), aws, op


def test_missing_onepassword_item_leaves_aws_password_untouched():
    """A rotated password that cannot be stored would be lost, so never rotate first."""
    manager, aws, op = make_manager(item=None)

    assert manager.update_profile("unmapped-profile") is False
    assert aws.login_profile_updates == []
    assert op.edits == []


def test_missing_onepassword_item_is_reported():
    manager, _, _ = make_manager(item=None)

    assert manager.update_profile("unmapped-profile") is False


def test_existing_item_rotates_and_stores_password():
    manager, aws, op = make_manager(item={"id": "abc"})

    assert manager.update_profile("mapped-profile") is True
    assert aws.login_profile_updates == [("mapped-profile", "user-mapped-profile")]
    assert op.edits == ["mapped-profile"]


def test_dry_run_changes_nothing():
    manager, aws, op = make_manager(item={"id": "abc"})

    assert manager.update_profile("mapped-profile", dry_run=True) is True
    assert aws.login_profile_updates == []
    assert op.edits == []
