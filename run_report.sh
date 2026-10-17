#!/bin/bash
# Wrapper the scheduler calls each morning. Uses the project's virtualenv and
# logs output so you can see what happened.
cd "$(dirname "$0")" || exit 1

mkdir -p logs
TIMESTAMP="$(date '+%Y-%m-%d %H:%M:%S')"

# Prefer the project venv; fall back to system python3.
if [ -x "./venv/bin/python3" ]; then
    PYTHON="./venv/bin/python3"
else
    PYTHON="python3"
fi

echo "[$TIMESTAMP] starting daily report" >> logs/report.log
"$PYTHON" daily_report.py >> logs/report.log 2>&1
echo "[$TIMESTAMP] finished with exit code $?" >> logs/report.log
