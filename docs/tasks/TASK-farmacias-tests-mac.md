---
kind: tests
---
# TASK — farmacias-tests-mac

## Goal
Run the matcher regression suite on this node and report the result. Do not change code.

## Files you may touch
- result.json

## Done criteria
- [ ] `PYTHONIOENCODING=utf-8 python3 -m tests.test_matcher_regresion` ran and its last 5 lines are in the report
- [ ] If the command cannot run (permission denied, missing interpreter or dependency), the exact error is in the report and nothing else was attempted

## Report back
- The command, its exit code and its last lines, or the exact refusal.
