"""The measurement harness is run by hand (``python tests/perf/module_process_test.py``); its name
ends in ``_test.py``, which pytest would collect, so it is ignored here. The smoke test of the
harness is ``tests/test_module_process_smoke.py``."""

collect_ignore = ["module_process_test.py"]
