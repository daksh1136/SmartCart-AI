"""Phase 7 acceptance with isolated test SQLite, never touches working demo data."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPORT = BACKEND.parent / 'reports' / 'phase7-acceptance.json'


def main() -> int:
    command = [sys.executable, '-m', 'pytest', '-q', 'tests']
    print('SmartCart AI — Phase 7 backend and synthetic-vision acceptance')
    print('Isolated temporary database. No live camera, sensor or payment.\n')
    result = subprocess.run(command, cwd=BACKEND, capture_output=True, text=True, check=False)
    output = (result.stdout + ('\n' + result.stderr if result.stderr else '')).strip()
    print(output)
    passed = re.search(r'(\d+) passed', output)
    failed = re.search(r'(\d+) failed', output)
    report = {
        'phase': 7,
        'generated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'result': 'PASS' if result.returncode == 0 else 'FAIL',
        'passed_tests': int(passed.group(1)) if passed else 0,
        'failed_tests': int(failed.group(1)) if failed else (0 if result.returncode == 0 else None),
        'tests': 'API + simulated shelf sensors + synthetic OpenCV frames + mock checkout',
        'frontend_build_validated': False,
        'real_webcam_validated': False,
        'physical_sensors_validated': False,
        'real_payments_validated': False,
        'command': 'python -m pytest -q tests',
        'stdout': output,
    }
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'Acceptance report: {REPORT}')
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
