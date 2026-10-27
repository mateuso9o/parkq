"""Unit tests for parkq_core, written Arrange-Act-Assert. Run: python -m unittest -v"""
import unittest
from datetime import datetime, timedelta

import parkq_core as core

SECRET = b"test-secret"
NOW = datetime(2026, 11, 2, 10, 0, 0)


class TestValidation(unittest.TestCase):
    def test_UT01_valid_phone(self):
        # Arrange
        phone = "0891234567"
        # Act
        ok = core.is_valid_phone(phone)
        # Assert
        self.assertTrue(ok)

    def test_UT02_phone_too_short_or_letters(self):
        # Arrange
        bad = ["089123456", "08912345ab", "0291234567", ""]
        # Act
        results = [core.is_valid_phone(p) for p in bad]
        # Assert
        self.assertEqual(results, [False, False, False, False])

    def test_UT03_thai_plate(self):
        # Arrange
        good, bad = ["กข 1234", "1กข 1234", "ก1"], ["ABC 1234", "กข", "กข 12345"]
        # Act
        good_res = [core.is_valid_plate(p) for p in good]
        bad_res = [core.is_valid_plate(p) for p in bad]
        # Assert
        self.assertTrue(all(good_res))
        self.assertFalse(any(bad_res))


class TestFees(unittest.TestCase):
    def test_UT04_free_within_grace(self):
        # Arrange
        minutes, rate = 15, 20
        # Act
        fee = core.parking_fee(minutes, rate)
        # Assert
        self.assertEqual(fee, 0)

    def test_UT05_started_hour_is_charged(self):
        # Arrange
        rate = 20
        # Act
        fees = [core.parking_fee(16, rate), core.parking_fee(60, rate), core.parking_fee(61, rate)]
        # Assert
        self.assertEqual(fees, [20, 20, 40])

    def test_UT06_booking_price_and_duration_limits(self):
        # Arrange
        rate = 30
        # Act
        price = core.booking_price(3, rate)
        # Assert
        self.assertEqual(price, 90)
        with self.assertRaises(ValueError):
            core.booking_price(0, rate)
        with self.assertRaises(ValueError):
            core.booking_price(25, rate)

    def test_UT07_overstay_fee(self):
        # Arrange
        end = NOW
        # Act
        within_grace = core.overstay_fee(end, end + timedelta(minutes=15), 20)
        over_one_hour = core.overstay_fee(end, end + timedelta(minutes=70), 20)
        # Assert
        self.assertEqual(within_grace, 0)
        self.assertEqual(over_one_hour, 40)

    def test_UT08_refund_rules(self):
        # Arrange
        start, paid = NOW + timedelta(hours=3), 90
        # Act
        early = core.refund_amount(paid, start, start - timedelta(minutes=60))
        late = core.refund_amount(paid, start, start - timedelta(minutes=59))
        after = core.refund_amount(paid, start, start + timedelta(minutes=1))
        # Assert
        self.assertEqual((early, late, after), (90, 0, 0))


class TestLotStatus(unittest.TestCase):
    def test_UT09_available_slots(self):
        # Arrange
        capacity, occupied, reserved = 50, 30, 5
        # Act
        free = core.available_slots(capacity, occupied, reserved)
        # Assert
        self.assertEqual(free, 15)

    def test_UT10_status_thresholds(self):
        # Arrange / Act
        statuses = [
            core.lot_status(50, 30, 0),   # 20 free = 40% -> available
            core.lot_status(50, 41, 0),   # 9 free = 18% -> nearly full
            core.lot_status(50, 45, 5),   # 0 free -> full
            core.lot_status(50, 48, 5),   # oversold by sensors, never negative
        ]
        # Assert
        self.assertEqual(statuses, ["AVAILABLE", "NEARLY_FULL", "FULL", "FULL"])


class TestBooking(unittest.TestCase):
    def test_UT11_valid_booking(self):
        # Arrange
        start = NOW + timedelta(hours=1)
        # Act
        err = core.validate_booking(NOW, start, 2, free_slots=5)
        # Assert
        self.assertIsNone(err)

    def test_UT12_booking_rejections(self):
        # Arrange
        cases = [
            (NOW + timedelta(hours=1), 2, 0),          # lot full
            (NOW - timedelta(hours=1), 2, 5),          # start in the past
            (NOW + timedelta(days=8), 2, 5),           # beyond 7 days
            (NOW + timedelta(hours=1), 0, 5),          # zero hours
        ]
        # Act
        errors = [core.validate_booking(NOW, s, h, f) for s, h, f in cases]
        # Assert
        self.assertEqual(errors, ["LOT_FULL", "START_IN_PAST", "TOO_FAR_AHEAD", "INVALID_DURATION"])

    def test_UT13_no_show(self):
        # Arrange
        start = NOW
        # Act
        at_30 = core.is_no_show(start, NOW + timedelta(minutes=30), entered=False)
        at_31 = core.is_no_show(start, NOW + timedelta(minutes=31), entered=False)
        entered = core.is_no_show(start, NOW + timedelta(hours=2), entered=True)
        # Assert
        self.assertEqual((at_30, at_31, entered), (False, True, False))


class TestTicketQR(unittest.TestCase):
    def setUp(self):
        self.start = NOW
        self.end = NOW + timedelta(hours=2)
        self.token = core.make_ticket_token("TK0001", "LOT01", self.start, self.end, SECRET)

    def test_UT14_valid_entry(self):
        # Arrange
        scan_time = NOW + timedelta(minutes=5)
        # Act
        result = core.check_entry(self.token, "LOT01", scan_time, SECRET, used_ids=set())
        # Assert
        self.assertEqual(result, "OK")

    def test_UT15_forged_or_malformed_qr(self):
        # Arrange
        forged = self.token.replace("LOT01", "LOT02")
        # Act
        r1 = core.check_entry(forged, "LOT02", NOW, SECRET, set())
        r2 = core.check_entry("hello", "LOT01", NOW, SECRET, set())
        # Assert
        self.assertEqual((r1, r2), ("INVALID_QR", "INVALID_QR"))

    def test_UT16_wrong_lot_and_reuse(self):
        # Act
        wrong_lot = core.check_entry(self.token, "LOT09", NOW, SECRET, set())
        reused = core.check_entry(self.token, "LOT01", NOW, SECRET, {"TK0001"})
        # Assert
        self.assertEqual((wrong_lot, reused), ("WRONG_LOT", "ALREADY_USED"))

    def test_UT17_time_window(self):
        # Arrange
        too_early = NOW - timedelta(minutes=31)
        early_ok = NOW - timedelta(minutes=30)
        no_show = NOW + timedelta(minutes=31)
        # Act
        results = [core.check_entry(self.token, "LOT01", t, SECRET, set())
                   for t in (too_early, early_ok, no_show)]
        # Assert
        self.assertEqual(results, ["TOO_EARLY", "OK", "NO_SHOW_RELEASED"])

    def test_UT18_gate_in_other_time_zone(self):
        # Arrange (regression for DEF-01: server issues ticket in Bangkok time, gate clock runs in UTC)
        from datetime import timezone
        bkk = timezone(timedelta(hours=7))
        start = datetime(2026, 11, 2, 10, 0, tzinfo=bkk)
        token = core.make_ticket_token("TK0002", "LOT01", start, start + timedelta(hours=2), SECRET)
        gate_now = datetime(2026, 11, 2, 3, 5, tzinfo=timezone.utc)   # = 10:05 Bangkok
        # Act
        result = core.check_entry(token, "LOT01", gate_now, SECRET, set())
        # Assert
        self.assertEqual(result, "OK")


class TestExitGate(unittest.TestCase):
    def setUp(self):
        self.end = NOW + timedelta(hours=2)
        self.token = core.make_ticket_token("TK0003", "LOT01", NOW, self.end, SECRET)

    def test_UT19_exit_on_time_and_overstay(self):
        # Arrange (regression for DEF-04: the QR used to enter must also open the exit gate)
        on_time = self.end + timedelta(minutes=10)
        late = self.end + timedelta(minutes=70)
        # Act
        r1 = core.check_exit(self.token, "LOT01", "PARKED", on_time, 20, SECRET)
        r2 = core.check_exit(self.token, "LOT01", "PARKED", late, 20, SECRET)
        # Assert
        self.assertEqual(r1, ("OK", 0))
        self.assertEqual(r2, ("PAY_OVERSTAY", 40))

    def test_UT20_exit_rejections(self):
        # Act
        not_entered = core.check_exit(self.token, "LOT01", "WAITING", NOW, 20, SECRET)
        done = core.check_exit(self.token, "LOT01", "DONE", NOW, 20, SECRET)
        wrong_lot = core.check_exit(self.token, "LOT02", "PARKED", NOW, 20, SECRET)
        forged = core.check_exit(self.token[:-1] + "0", "LOT01", "PARKED", NOW, 20, SECRET)
        # Assert
        self.assertEqual([not_entered[0], done[0], wrong_lot[0], forged[0]],
                         ["NOT_ENTERED", "ALREADY_EXITED", "WRONG_LOT", "INVALID_QR"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
