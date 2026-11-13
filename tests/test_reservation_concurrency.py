"""동시 예약 원자성 테스트.

같은 빈자리에 여러 사람이 동시에 예약해도 한 건만 성공해야 한다.
"빈자리 확인" 직후에 지연을 넣어 경쟁 구간을 일부러 넓히므로, 확인과 확정이 한 묶음이 아니면 매번 이중 예약이 재현된다.

실행: python -m unittest tests.test_reservation_concurrency -v   (pytest 로도 실행 가능)
"""

import sys
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.reservation import service  # noqa: E402
from src.reservation.tools import create_reservation  # noqa: E402

DATE = "2026-11-25"  # 더미 예약이 없는 날짜
RACE_DELAY = 0.05     # 빈자리 확인 뒤 일부러 넣는 지연(초)


def run_together(funcs):
    """함수들을 스레드로 동시에 출발시켜 결과 목록을 돌려준다."""
    barrier = threading.Barrier(len(funcs))
    results = [None] * len(funcs)

    def worker(i, fn):
        barrier.wait()  # 모두 준비되면 한꺼번에 출발
        results[i] = fn()

    threads = [threading.Thread(target=worker, args=(i, fn)) for i, fn in enumerate(funcs)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    return results


def slow_taken(original):
    """빈자리 확인(_taken) 직후 지연을 넣어 경쟁 상황을 재현하기 쉽게 만든다."""
    def wrapper(day, hour):
        result = original(day, hour)
        time.sleep(RACE_DELAY)
        return result
    return wrapper


class ReservationConcurrencyTest(unittest.TestCase):
    """create_reservation · close_slot 의 동시 실행 검증 (잠금은 src/reservation/service.py 의 _STATE_LOCK)."""

    def setUp(self):
        """매 테스트를 원본 예약 상태에서 시작한다."""
        service.reset_reservations()
        patcher = mock.patch.object(service, "_taken", slow_taken(service._taken))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(service.reset_reservations)

    def reservations_at(self, hour, facility_id):
        """해당 슬롯에 저장된 예약 목록."""
        return [r for r in service.reservations_snapshot()
                if r["date"] == DATE and r["hour"] == hour and r["facility_id"] == facility_id]

    def test_same_slot_only_one_succeeds(self):
        """같은 슬롯에 20명이 동시에 예약하면 정확히 1건만 성공하고 나머지는 '이미 예약된 슬롯'으로 거절된다."""
        card_nos = [None, "M-1001", "M-1003", "M-1004"]  # 일반인·정기 회원 섞기
        funcs = [lambda c=card_nos[i % 4]: create_reservation.invoke(
                     {"date": DATE, "hour": 10, "facility_id": "BC-1", "card_no": c}) for i in range(20)]
        results = run_together(funcs)

        succeeded = [r for r in results if r["reserved"]]
        self.assertEqual(len(succeeded), 1, f"성공 {len(succeeded)}건 (이중 예약 발생)")
        self.assertTrue(all(r["reason"] == "이미 예약된 슬롯" for r in results if not r["reserved"]))
        self.assertEqual(len(self.reservations_at(10, "BC-1")), 1, "저장된 예약이 1건이 아님")

    def test_different_slots_all_succeed_with_unique_ids(self):
        """서로 다른 시설 15개를 동시에 예약하면 모두 성공하고 예약 번호가 겹치지 않는다."""
        facility_ids = [f"BC-{n}" for n in range(1, 6)] + [f"PM-{n}" for n in range(1, 11)]
        funcs = [lambda f=f: create_reservation.invoke({"date": DATE, "hour": 11, "facility_id": f})
                 for f in facility_ids]
        results = run_together(funcs)

        self.assertTrue(all(r["reserved"] for r in results))
        ids = [r["reservation"]["reservation_id"] for r in results]
        self.assertEqual(len(ids), len(set(ids)), f"예약 번호 중복: {sorted(ids)}")

    def test_close_and_reserve_at_same_time(self):
        """점검 닫기와 예약이 동시에 와도 '닫힌 슬롯에 예약이 남는' 상태가 생기지 않는다 (둘 중 하나만 성공)."""
        for _ in range(5):  # 경쟁 순서가 바뀌어도 매번 성립해야 한다
            service.reset_reservations()
            close, reserve = run_together([
                lambda: service.close_slot(DATE, 12, "PM-1", "그물 교체"),
                lambda: create_reservation.invoke({"date": DATE, "hour": 12, "facility_id": "PM-1"}),
            ])
            closed = any(c["date"] == DATE and c["hour"] == 12 and c["facility_id"] == "PM-1"
                         for c in service.list_closures())
            reserved = len(self.reservations_at(12, "PM-1")) == 1
            self.assertFalse(closed and reserved, "점검으로 닫힌 슬롯에 예약이 저장됨")
            self.assertEqual(close["ok"] + reserve["reserved"], 1, f"닫기 {close} / 예약 {reserve}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
