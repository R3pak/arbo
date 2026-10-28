"""
Decides whether the menu job should really check the menu right now.

GitHub can only schedule jobs in UTC time, which doesn't follow daylight
saving. So GitHub starts the job every 30 minutes, and this script looks at
the time in Davis and only says "yes" at the times we actually want:

  * 6:00 AM every day, to load the day's menu before anything opens
  * every hour while the DCs are open (7 AM to 10 PM, Monday to Friday)
  * every 30 minutes in the last hour of each meal, because that's when the
    DCs swap dishes out (e.g. eggs come off so pasta can go on)

To change the times, edit the settings just below.
"""

import os
import sys
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

DAVIS = ZoneInfo("America/Los_Angeles")

DAILY_CHECK = time(6, 0)                 # every day, open or not
OPEN_DAYS = {0, 1, 2, 3, 4}              # Monday to Friday (Python counts Monday as 0)
OPENS, CLOSES = time(7, 0), time(22, 0)  # earliest opening and latest closing of any DC

# When each meal ends. The hour before each of these gets a check every 30 minutes.
# 8 PM is when Latitude closes.
MEAL_ENDS = [time(11, 0), time(17, 0), time(20, 0), time(22, 0)]

# The cron lines in update-menu.yml run at :05 and :35, a few minutes after the
# hour, because GitHub is busiest (and slowest) exactly on the hour.
CRON_OFFSET_MINUTES = 5


def wanted(slot):
    """slot is a Davis-time datetime on the hour or half hour. Should we check then?"""
    t = slot.time()
    if t == DAILY_CHECK:
        return True, "morning menu load"
    if slot.weekday() not in OPEN_DAYS:
        return False, "the DCs are closed today"
    if not (OPENS <= t < CLOSES):
        return False, "the DCs are closed right now"
    if slot.minute == 0:
        return True, "hourly check while open"
    for end in MEAL_ENDS:
        meal_end = slot.replace(hour=end.hour, minute=end.minute)
        if meal_end - timedelta(hours=1) <= slot < meal_end:
            return True, f"last hour before {meal_end:%-I:%M %p}"
    return False, "half-hour checks only happen in the last hour of a meal"


def intended_slot(now_utc, schedule):
    """
    Work out which time GitHub *meant* to run us at. GitHub sometimes starts
    jobs late, so we go back to the most recent :05 or :35 (whichever cron line
    fired), then take off the 5-minute offset.
    """
    cron_minute = int(schedule.split()[0])
    slot = now_utc.replace(second=0, microsecond=0)
    while slot.minute != cron_minute:
        slot -= timedelta(minutes=1)
    return (slot - timedelta(minutes=CRON_OFFSET_MINUTES)).astimezone(DAVIS)


def main():
    event = os.environ.get("EVENT", "")
    if event != "schedule":
        decision, reason, label = True, f"started by hand ({event or 'local run'})", ""
    else:
        slot = intended_slot(datetime.now(timezone.utc), os.environ["SCHEDULE"])
        decision, reason = wanted(slot)
        label = f"{slot:%a %-I:%M %p} Davis time: "
    print(f"{label}{'checking the menu' if decision else 'skipping'} ({reason})")
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a") as f:
            f.write(f"run={'true' if decision else 'false'}\n")


if __name__ == "__main__":
    sys.exit(main())
