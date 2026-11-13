"""관리자 대시보드: 이용 이력으로 운영 지표를 계산한다 (파이썬 집계, 개인정보 없음)."""

from collections import Counter, defaultdict

from src.operations.feedback import feedback_summary
from src.operations.schemas import EXPANSION_THRESHOLD, FACILITY_COUNT
from src.reservation.schemas import MEMBER
from src.reservation.service import list_closures, reservations_snapshot
from src.shared.config import load_json

_HISTORY = load_json("usage_history.json")["records"]


def dashboard(days: int = 14) -> dict:
    """최근 days 일의 이용 이력으로 운영 지표를 계산한다."""
    dates = sorted({r["date"] for r in _HISTORY})[-days:]
    period = [r for r in _HISTORY if r["date"] in set(dates)]
    total_slots_per_hour = sum(FACILITY_COUNT.values())

    daily = defaultdict(lambda: {"member": 0, "guest": 0})
    by_hour = Counter()
    by_type = Counter()
    for r in period:
        daily[r["date"]]["member" if r["member_type"] == MEMBER else "guest"] += 1
        by_hour[r["hour"]] += 1
        by_type[r["facility_id"].split("-")[0]] += 1

    n_days = len(dates) or 1
    hourly = [{"hour": h, "utilization": round(by_hour[h] / (total_slots_per_hour * n_days), 3)} for h in range(24)]
    facility = [{"type": name, "utilization": round(by_type[key] / (FACILITY_COUNT[key] * 24 * n_days), 3)}
                for key, name in (("BC", "배팅케이지"), ("PM", "피칭머신"))]
    members = sum(d["member"] for d in daily.values())
    visits = len(period)
    peak = max(hourly, key=lambda x: x["utilization"])
    expansion = [h for h in hourly if h["utilization"] >= EXPANSION_THRESHOLD]
    upcoming = reservations_snapshot()

    return {
        "period": {"from": dates[0] if dates else None, "to": dates[-1] if dates else None, "days": len(dates)},
        "kpis": {
            "visits": visits,
            "avg_daily_visits": round(visits / n_days, 1),
            "avg_utilization": round(visits / (total_slots_per_hour * 24 * n_days), 3),
            "peak_hour": peak["hour"], "peak_utilization": peak["utilization"],
            "member_share": round(members / visits, 3) if visits else 0,
            "upcoming_reservations": len(upcoming),
            "closed_slots": len(list_closures()),
        },
        "daily": [{"date": d, **daily[d], "visits": daily[d]["member"] + daily[d]["guest"]} for d in dates],
        "hourly": hourly,
        "facility": facility,
        "expansion": {"threshold": EXPANSION_THRESHOLD,
                      "hours": [{"hour": h["hour"], "utilization": h["utilization"]} for h in expansion]},
        "feedback": feedback_summary(),
    }
