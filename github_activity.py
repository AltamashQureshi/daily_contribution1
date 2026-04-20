"""
╔══════════════════════════════════════════════════════╗
║        GitHub Activity Graph Enhancer v3.0           ║
║             Commits · Realistic Bursts               ║
╚══════════════════════════════════════════════════════╝

Setup:
  pip install requests
  Run inside a cloned GitHub repo directory.

Fill in the CONFIG section below before running.
"""

import os
import sys
import time
import random
import subprocess
from datetime import datetime, timedelta

# ================================================================
#  CONFIG  ← edit this section
# ================================================================

START_DATE        = datetime(2020, 1, 5)
END_DATE          = datetime.today()

GIT_EMAIL         = "your-email@example.com"       # Email linked to your GitHub account
GIT_NAME          = "your-github-username"          # Your GitHub display name
GITHUB_TOKEN      = "YOUR_PAT_HERE"                 # ghp_xxxxxxxxxxxx  (needs repo scope)
GITHUB_USERNAME   = "your-github-username"          # Your GitHub username
GITHUB_REPO       = "your-repo-name"                # Full URL or just repo name e.g. "my-repo"

BRANCH            = "main"
LOG_FILE          = "activity.log"

# ── Commit volume ───────────────────────────────────────────────
COMMIT_WEIGHTS = {
    0:  15,
    1:   8,
    2:  12,
    3:  14,
    4:  13,
    5:  12,
    6:   9,
    7:   7,
    8:   5,
    9:   4,
    10:  3,
    11:  2,
    12:  2,
    13:  1,
    14:  1,
    15:  1,
    16:  1,
    17:  1,
    18:  1,
}

# ── Burst streaks ───────────────────────────────────────────────
BURST_WEEK_PROBABILITY = 0.08
BURST_BONUS_MIN        = 4
BURST_BONUS_MAX        = 8

# ── Reliability ─────────────────────────────────────────────────
API_MAX_RETRIES   = 4
API_RETRY_DELAY   = 6
PUSH_BATCH_SIZE   = 150

# ── Resume support ──────────────────────────────────────────────
CHECKPOINT_FILE   = ".activity_checkpoint"

# ================================================================
#  VOCABULARY
# ================================================================

ACTIONS = [
    "fix", "feat", "refactor", "improve", "add", "remove",
    "optimize", "cleanup", "tweak", "adjust", "enhance", "resolve",
    "implement", "restructure", "document", "migrate", "test",
    "revert", "bump", "patch", "style", "perf", "ci", "chore",
]

SCOPES = [
    "logging", "tracker", "report", "sync", "api", "generator",
    "writer", "parser", "scheduler", "timestamps", "workflow",
    "pipeline", "auth", "cache", "db", "ui", "config", "tests",
    "docs", "ci", "deps", "build", "core", "utils", "types",
]

DETAILS = [
    "edge cases in date handling",
    "performance under high load",
    "randomization logic",
    "output formatting",
    "error handling and retries",
    "data consistency checks",
    "logging format to JSON",
    "file writer buffer flush",
    "commit workflow ordering",
    "retry logic with backoff",
    "null pointer guard",
    "memory leak on large datasets",
    "timezone offset calculation",
    "config validation on startup",
    "unused variable warnings",
    "type hints across module",
    "deprecation warnings",
    "docstring accuracy",
    "test coverage for edge paths",
    "linting issues",
    "CI pipeline speed",
    "startup time",
    "duplicate log entries",
    "missing unit tests",
    "code duplication in helpers",
]

# ================================================================
#  BUILD WEIGHTED COMMIT POOL ONCE
# ================================================================

_COMMIT_POPULATION  = list(COMMIT_WEIGHTS.keys())
_COMMIT_WEIGHT_LIST = list(COMMIT_WEIGHTS.values())

# ================================================================
#  UTILITIES
# ================================================================

def run(cmd, env=None, capture=False):
    return subprocess.run(
        cmd, check=True, env=env,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )

def git_time(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S")

def sorted_times_in_day(day: datetime, n: int):
    """Generate n sorted, gap-enforced random datetimes within `day`.
    70% of commits land in working hours (08:00-20:00)."""
    times = []
    for _ in range(n):
        if random.random() < 0.70:
            offset = random.randint(8 * 60, 20 * 60)
        else:
            offset = random.randint(0, 1439)
        times.append(day + timedelta(minutes=offset))
    times.sort()
    for i in range(1, len(times)):
        if times[i] <= times[i - 1]:
            times[i] = times[i - 1] + timedelta(minutes=1)
    return times

def generate_commit_message() -> str:
    action = random.choice(ACTIONS)
    scope  = random.choice(SCOPES)
    detail = random.choice(DETAILS)
    if random.random() < 0.45:
        return f"{action}({scope}): {detail}"
    return f"{action} {scope}: {detail}"

def choose_commits_today(in_burst: bool) -> int:
    base = random.choices(_COMMIT_POPULATION, weights=_COMMIT_WEIGHT_LIST, k=1)[0]
    if in_burst and base > 0:
        base += random.randint(BURST_BONUS_MIN, BURST_BONUS_MAX)
    return base

def progress_bar(day_num: int, total: int, label: str, width: int = 38):
    pct  = day_num / total if total else 1
    done = int(width * pct)
    bar  = "█" * done + "░" * (width - done)
    sys.stdout.write(f"\r  [{bar}] {day_num:>5}/{total}  {label}")
    sys.stdout.flush()

# ================================================================
#  CHECKPOINT
# ================================================================

def checkpoint_read():
    if os.path.exists(CHECKPOINT_FILE):
        try:
            return datetime.strptime(open(CHECKPOINT_FILE).read().strip(), "%Y-%m-%d")
        except Exception:
            pass
    return None

def checkpoint_write(dt: datetime):
    with open(CHECKPOINT_FILE, "w") as f:
        f.write(dt.strftime("%Y-%m-%d"))

# ================================================================
#  GIT PUSH
# ================================================================

def safe_push(branch: str):
    """Fetch remote, rebase local commits on top, then push."""
    try:
        run(["git", "fetch", "origin", branch], capture=True)
        run(["git", "rebase", f"origin/{branch}"], capture=True)
    except subprocess.CalledProcessError:
        try:
            run(["git", "rebase", "--abort"], capture=True)
        except Exception:
            pass
        run(["git", "push", "--force-with-lease", "-u", "origin", branch])
        return
    run(["git", "push", "-u", "origin", branch])

# ================================================================
#  STATS
# ================================================================

class Stats:
    def __init__(self):
        self.commits = 0
        self.active_days = 0
        self.max_day = 0

    def record_day(self, n: int):
        self.commits += n
        if n > 0:
            self.active_days += 1
            self.max_day = max(self.max_day, n)

    def report(self):
        print("\n")
        print("╔══════════════════════════════════════╗")
        print("║            Run Complete               ║")
        print("╠══════════════════════════════════════╣")
        print(f"║  Total commits   : {self.commits:<17} ║")
        print(f"║  Active days     : {self.active_days:<17} ║")
        print(f"║  Peak day        : {self.max_day:<17} ║")
        print("╚══════════════════════════════════════╝")
        print("\n  Check your GitHub contribution graph!\n")

# ================================================================
#  VALIDATION + SETUP
# ================================================================

def validate_config():
    errors = []
    if GITHUB_TOKEN == "YOUR_PAT_HERE":
        errors.append("GITHUB_TOKEN is not set")
    if not GITHUB_REPO or GITHUB_REPO == "YOUR_REPO_NAME_HERE":
        errors.append("GITHUB_REPO is not set")
    if errors:
        print("\n  Config errors - edit the CONFIG section at the top:\n")
        for e in errors:
            print(f"    * {e}")
        sys.exit(1)

def setup_git():
    run(["git", "config", "user.name",  GIT_NAME])
    run(["git", "config", "user.email", GIT_EMAIL])
    run(["git", "checkout", "-B", BRANCH])
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w") as f:
            f.write("# activity log - auto-generated\n")
        run(["git", "add", LOG_FILE])
        run(["git", "commit", "-m", "chore: init activity log"])

# ================================================================
#  MAIN
# ================================================================

def main():
    validate_config()
    setup_git()

    total_days  = (END_DATE - START_DATE).days + 1
    resume_from = checkpoint_read()

    if resume_from and resume_from > START_DATE:
        current = resume_from + timedelta(days=1)
        skipped = (current - START_DATE).days
        print(f"\n  Resuming from {current.strftime('%Y-%m-%d')} ({skipped} days already done)\n")
    else:
        current = START_DATE
        print(f"\n  Starting from {START_DATE.strftime('%Y-%m-%d')}\n")

    print(f"  Date range  : {START_DATE.strftime('%Y-%m-%d')} -> {END_DATE.strftime('%Y-%m-%d')}")
    print(f"  Total days  : {total_days}")
    print(f"  Commit dist : {min(COMMIT_WEIGHTS)}-{max(COMMIT_WEIGHTS)}/day  (weighted)")
    print()

    stats        = Stats()
    commit_buf   = 0
    burst_streak = 0

    while current <= END_DATE:
        date_str   = current.strftime("%Y-%m-%d")
        day_number = (current - START_DATE).days + 1

        # ── Burst logic ──────────────────────────────────────────
        if burst_streak > 0:
            in_burst     = True
            burst_streak -= 1
        elif random.random() < BURST_WEEK_PROBABILITY:
            in_burst     = True
            burst_streak = random.randint(3, 7)
        else:
            in_burst = False

        # ── How many commits today ────────────────────────────────
        n = choose_commits_today(in_burst)
        progress_bar(
            day_number, total_days,
            label=f"{date_str}  {'burst' if in_burst else '     '}  {n:>2} commits"
        )

        # ── Make commits ──────────────────────────────────────────
        if n > 0:
            times = sorted_times_in_day(current, n)
            for ts in times:
                with open(LOG_FILE, "a") as f:
                    f.write(f"{date_str} | {random.randint(1, 9_999_999)}\n")
                run(["git", "add", LOG_FILE])
                env = os.environ.copy()
                env["GIT_AUTHOR_DATE"]    = git_time(ts)
                env["GIT_COMMITTER_DATE"] = git_time(ts)
                run(["git", "commit", "-m", generate_commit_message()], env=env)
                commit_buf += 1

            if commit_buf >= PUSH_BATCH_SIZE:
                safe_push(BRANCH)
                commit_buf = 0

        stats.record_day(n)
        checkpoint_write(current)
        current += timedelta(days=1)

    # ── Final push ────────────────────────────────────────────────
    print("\n\n  Pushing final batch ...")
    safe_push(BRANCH)

    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)

    stats.report()


if __name__ == "__main__":
    main()
