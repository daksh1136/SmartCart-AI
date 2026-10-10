"""Run SmartCart Phase 6 acceptance suite without touching your demo database.

From the backend folder:
    python scripts/run_acceptance.py

Uses a temporary SQLite database injected by tests/conftest.py.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPORT = BACKEND.parent / 'reports' / 'phase6-acceptance.json'


def main() -> int:
    command = [sys.executable, '-m', 'pytest', '-q', 'tests']
    print('SmartCart AI — Phase 6 acceptance validation')
    print('Uses a temporary test database. No payment is processed.\n')
    completed = subprocess.run(command, cwd=BACKEND, capture_output=True, text=True, check=False)
    output = (completed.stdout + ('\n' + completed.stderr if completed.stderr else '')).strip()
    print(output)
    passed = re.search(r'(\d+) passed', output)
    failed = re.search(r'(\d+) failed', output)
    report = {
        'generated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'phase': 6,
        'suite': 'FastAPI + synthetic camera + simulated fusion + mocked exit',
        'result': 'PASS' if completed.returncode == 0 else 'FAIL',
        'passed_tests': int(passed.group(1)) if passed else 0,
        'failed_tests': int(failed.group(1)) if failed else (0 if completed.returncode == 0 else None),
        'command': 'python -m pytest -q tests',
        'backend_tests_only': True,
        'real_webcam_tested': False,
        'physical_weight_sensors_tested': False,
        'frontend_build_tested_by_script': False,
        'real_payments_tested': False,
        'stdout': output,
    }
    REPORT.parent.mkdir(exist_ok=True, parents=True)
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'\nAcceptance report: {REPORT}')
    return completed.returncode


if __name__ == '__main__':
    raise SystemExit(main())
