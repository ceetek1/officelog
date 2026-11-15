"""Rotating codes (spec §5, §12; decision D2): stale QR and stale typed codes are rejected."""

import json
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from app import codes

MASTER = b"test-master-secret-0123456789abcdef"
SOURCE = codes.MasterSecretSource(MASTER)
LAGOS = ZoneInfo("Africa/Lagos")


def date_of(unix: float) -> date:
    return datetime.fromtimestamp(unix, LAGOS).date()


T = datetime(2026, 11, 16, 8, 0, 0, tzinfo=timezone.utc).timestamp()  # start of a 30 s window


def qr_at(unix: float) -> str:
    return codes.qr_content(codes.day_secret(MASTER, date_of(unix)), codes.qr_window(unix))


def typed_at(unix: float) -> str:
    return codes.typed_code(codes.day_secret(MASTER, date_of(unix)), codes.typed_window(unix))


def test_truncation_matches_rfc_6238_sha256_vectors():
    key = b"12345678901234567890123456789012"
    assert codes.code6(key, 1) == "119246"            # 46119246 in the RFC, last 6 digits
    assert codes.code6(key, 37037036) == "084774"     # 68084774


def test_qr_from_current_and_previous_window_is_accepted():
    qr = qr_at(T)
    assert codes.check_qr(qr, T, SOURCE, date_of) == codes.qr_window(T)
    assert codes.check_qr(qr, T + 4.9, SOURCE, date_of) is not None   # same window
    assert codes.check_qr(qr, T + 9.9, SOURCE, date_of) is not None   # previous window


def test_qr_two_windows_old_is_rejected():
    qr = qr_at(T)
    assert codes.check_qr(qr, T + 10, SOURCE, date_of) is None


def test_15_second_old_qr_is_rejected():
    """Step 2 done check."""
    assert codes.check_qr(qr_at(T), T + 15, SOURCE, date_of) is None
    assert codes.check_qr(qr_at(T + 2), T + 17, SOURCE, date_of) is None


def test_qr_from_the_future_or_tampered_is_rejected():
    assert codes.check_qr(qr_at(T + 5), T, SOURCE, date_of) is None
    w = codes.qr_window(T)
    real = qr_at(T)
    wrong = real[:-1] + str((int(real[-1]) + 1) % 10)
    assert codes.check_qr(wrong, T, SOURCE, date_of) is None
    assert codes.check_qr(f"ATT1.{w}.12345", T, SOURCE, date_of) is None
    assert codes.check_qr("hello", T, SOURCE, date_of) is None


def test_qr_made_with_another_secret_is_rejected():
    other = codes.MasterSecretSource(b"another-master-secret-000000000000")
    assert codes.check_qr(qr_at(T), T, other, date_of) is None


def test_typed_code_works_for_the_30_seconds_it_is_shown():
    code = typed_at(T)
    for dt in (0, 10, 29.9):
        assert codes.check_typed(code, T + dt, SOURCE, date_of) == codes.typed_window(T)


def test_typed_code_has_a_few_seconds_of_slack_after_it_changes():
    code = typed_at(T)
    assert codes.check_typed(code, T + 30 + codes.TYPED_SLACK - 0.1, SOURCE, date_of) is not None


def test_stale_typed_code_is_rejected():
    code = typed_at(T)
    assert codes.check_typed(code, T + 30 + codes.TYPED_SLACK, SOURCE, date_of) is None
    assert codes.check_typed(code, T + 65, SOURCE, date_of) is None


def test_typed_and_qr_codes_use_different_keys():
    """Separate keys: a typed code is not the QR code of the same window number, and vice versa."""
    s = codes.day_secret(MASTER, date_of(T))
    qr_key, typed_key = codes.purpose_key(s, "qr"), codes.purpose_key(s, "typed")
    assert qr_key != typed_key
    differ = sum(codes.code6(qr_key, w) != codes.code6(typed_key, w) for w in range(100))
    assert differ >= 99


def test_each_day_has_its_own_secret():
    assert codes.day_secret(MASTER, date(2026, 11, 16)) != codes.day_secret(MASTER, date(2026, 11, 17))


def test_vectors_file_matches_this_module():
    """The same file is checked by frontend/src/codes.test.ts, so both sides stay identical."""
    data = json.loads(Path(__file__).with_name("fixtures").joinpath("code_vectors.json").read_text())
    master = data["master"].encode()
    for v in data["vectors"]:
        s = codes.day_secret(master, date.fromisoformat(v["work_date"]))
        assert s.hex() == v["day_secret_hex"]
        assert codes.qr_window(v["unix"]) == v["qr_window"]
        assert codes.qr_content(s, v["qr_window"]) == v["qr"]
        assert codes.typed_window(v["unix"]) == v["typed_window"]
        assert codes.typed_code(s, v["typed_window"]) == v["typed"]
