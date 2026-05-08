from __future__ import annotations

import argparse
import logging
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from core.card_actions import handle_card_action
from core.feishu_app import FeishuAppConfigError, run_card_action_listener
from core.memory import load_state
from core.settings import DAILY_SCHEDULE_UTC, SERVER_POLL_SECONDS
from skills.daily_finder.run_daily import run_daily_pipeline


def _parse_schedule(value: str) -> tuple[int, int]:
    hour_str, minute_str = value.strip().split(":", 1)
    hour = int(hour_str)
    minute = int(minute_str)
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("schedule must be HH:MM in UTC")
    return hour, minute


def _has_scheduled_run_today() -> bool:
    state = load_state()
    today = datetime.now(timezone.utc).date()
    scheduler = state.get("scheduler", {})
    return scheduler.get("last_scheduled_utc_date") == today.isoformat()


def _mark_scheduled_run_today() -> None:
    state = load_state()
    scheduler = state.setdefault("scheduler", {})
    now = datetime.now(timezone.utc)
    scheduler["last_scheduled_utc_date"] = now.date().isoformat()
    scheduler["last_scheduled_run_at"] = now.isoformat()
    from core.memory import save_state

    save_state(state)


def _should_run_now(schedule_hour: int, schedule_minute: int) -> bool:
    now = datetime.now(timezone.utc)
    if _has_scheduled_run_today():
        return False
    scheduled = now.replace(hour=schedule_hour, minute=schedule_minute, second=0, microsecond=0)
    return now >= scheduled


def _run_daily(push_to_feishu: bool, scheduled: bool = False) -> None:
    started = datetime.now(timezone.utc).isoformat()
    print(f"[{started}] Elena server: running daily scout", flush=True)
    result = run_daily_pipeline(push_to_feishu=push_to_feishu)
    if scheduled:
        _mark_scheduled_run_today()
    print(
        f"[{datetime.now(timezone.utc).isoformat()}] Elena server: daily finished, "
        f"feishu={result['feishu_status']} mode={result.get('feishu_mode')}",
        flush=True,
    )
    if result["fetch_errors"]:
        for error in result["fetch_errors"]:
            print(f"  warning: {error}", flush=True)


def _scheduler_loop(
    schedule_hour: int,
    schedule_minute: int,
    push_to_feishu: bool,
    poll_seconds: int,
    stop_event: threading.Event,
) -> None:
    print(
        f"[scheduler] thread started; schedule_utc={schedule_hour:02d}:{schedule_minute:02d} "
        f"poll={poll_seconds}s push={push_to_feishu}",
        flush=True,
    )
    while not stop_event.is_set():
        try:
            if _should_run_now(schedule_hour, schedule_minute):
                _run_daily(push_to_feishu=push_to_feishu, scheduled=True)
        except Exception as exc:  # noqa: BLE001
            print(f"[{datetime.now(timezone.utc).isoformat()}] scheduler error: {exc}", flush=True)
        stop_event.wait(max(poll_seconds, 5))


def main() -> int:
    parser = argparse.ArgumentParser(description="Elena always-on server loop.")
    parser.add_argument("--once", action="store_true", help="Run daily once immediately and exit.")
    parser.add_argument("--no-push", action="store_true", help="Run without Feishu push.")
    parser.add_argument(
        "--no-listener",
        action="store_true",
        help="Skip the card.action.trigger listener (legacy single-loop mode).",
    )
    parser.add_argument("--schedule", default=DAILY_SCHEDULE_UTC, help="Daily trigger time in UTC, format HH:MM.")
    parser.add_argument("--poll-seconds", type=int, default=SERVER_POLL_SECONDS, help="Polling interval for scheduler.")
    args = parser.parse_args()

    schedule_hour, schedule_minute = _parse_schedule(args.schedule)
    push_to_feishu = not args.no_push

    if args.once:
        _run_daily(push_to_feishu=push_to_feishu, scheduled=False)
        return 0

    print(
        f"Elena server started. schedule_utc={args.schedule}, poll_seconds={args.poll_seconds}, "
        f"push_feishu={push_to_feishu}, listener={'off' if args.no_listener else 'on'}",
        flush=True,
    )

    stop_event = threading.Event()
    scheduler_thread = threading.Thread(
        target=_scheduler_loop,
        args=(schedule_hour, schedule_minute, push_to_feishu, args.poll_seconds, stop_event),
        name="elena-scheduler",
        daemon=True,
    )
    scheduler_thread.start()

    if args.no_listener:
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            print("\nElena server stopped.", flush=True)
            stop_event.set()
        return 0

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    )
    try:
        run_card_action_listener(handle_card_action)
    except FeishuAppConfigError as exc:
        print(f"Feishu app credentials missing — listener disabled. ({exc})", flush=True)
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            pass
    except KeyboardInterrupt:
        pass
    finally:
        print("\nElena server stopped.", flush=True)
        stop_event.set()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
