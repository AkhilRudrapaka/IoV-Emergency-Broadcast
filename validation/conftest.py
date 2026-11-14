"""The suite checks the code against the TRACKED results in results/urban, whatever EXP_RESULTS_DIR says: that
variable redirects where a run writes, not the reference the tests read. Tests that write use tmp_path (and pass their
own EXP_RESULTS_DIR to the processes they start). Removed before any test module imports config."""
import os

os.environ.pop("EXP_RESULTS_DIR", None)
