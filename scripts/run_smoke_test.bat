@echo off
cd /d "E:\Projects and systems managed by the team of experts\Alpha Wolf Agent"
python scripts\smoke_test.py > E:\Projects and systems managed by the team of experts\Alpha Wolf Agent\smoke_test_20260924_044853.log 2>&1
echo SMOKE_TEST_COMPLETE > smoke_test_done.flag
