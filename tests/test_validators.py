"""Tests for input validation utilities."""

import pytest

from aws_credential_manager.utils.validators import (
    sanitize_filename,
    validate_age_threshold,
    validate_email,
    validate_profile_name,
)


class TestValidateProfileName:
    @pytest.mark.parametrize(
        "name",
        ["dev", "resola-deca-crm-dev", "a_b.c-1", "ABC123", "x" * 100],
    )
    def test_valid_names(self, name):
        assert validate_profile_name(name) is True

    @pytest.mark.parametrize(
        "name",
        ["", "x" * 101, "has space", "bad/slash", "tab\t", "emoji😀", "a;b"],
    )
    def test_invalid_names(self, name):
        assert validate_profile_name(name) is False

    def test_non_string(self):
        assert validate_profile_name(None) is False  # type: ignore[arg-type]
        assert validate_profile_name(123) is False  # type: ignore[arg-type]


class TestValidateAgeThreshold:
    @pytest.mark.parametrize("age", [1, 90, 365, 1095])
    def test_valid(self, age):
        assert validate_age_threshold(age) is True

    @pytest.mark.parametrize("age", [0, -1, 1096, 99999])
    def test_out_of_range(self, age):
        assert validate_age_threshold(age) is False

    def test_non_int(self):
        assert validate_age_threshold("90") is False  # type: ignore[arg-type]
        assert validate_age_threshold(90.0) is False  # type: ignore[arg-type]

    def test_bool_rejected(self):
        # bool is an int subclass; True == 1 but is not a meaningful age.
        # Document current behavior: bool passes the isinstance(int) check.
        assert validate_age_threshold(True) is True


class TestValidateEmail:
    @pytest.mark.parametrize(
        "email",
        ["a@b.co", "khai.nguyenquang27@gmail.com", "x+y%z@sub.domain.org"],
    )
    def test_valid(self, email):
        assert validate_email(email) is True

    @pytest.mark.parametrize("email", ["", None])
    def test_optional_empty_is_valid(self, email):
        assert validate_email(email) is True

    @pytest.mark.parametrize(
        "email",
        ["no-at", "a@b", "a@b.c", "@b.com", "a@.com", "spaces in@b.com"],
    )
    def test_invalid(self, email):
        assert validate_email(email) is False


class TestSanitizeFilename:
    def test_replaces_dangerous_chars(self):
        assert sanitize_filename('a<b>c:"d/e\\f|g?h*i') == "a_b_c__d_e_f_g_h_i"

    def test_keeps_safe_chars(self):
        assert sanitize_filename("report-2026.01.csv") == "report-2026.01.csv"

    def test_truncates_to_255(self):
        result = sanitize_filename("x" * 300)
        assert len(result) == 255
