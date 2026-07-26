import json
import logging
import uuid
from pathlib import Path
from typing import Optional
from collections import deque
from datetime import datetime
from lynch.state.schema import Transition

logger = logging.getLogger(__name__)


class Recorder:
    """
    Logger for DRL batches that manages scenario-level
    persistence and real-time history buffering for evaluation.

    Note: This class is NOT thread-safe. All calls must be made from a single thread.
    """

    def __init__(self, dir_path: str, max_history_size: int = 100) -> None:
        """
        Initializes the batch directory and the evaluation sliding window.

        Args:
            dir_path: Path to the directory where all batch results will be stored.
            max_history_size: Maximum number of recent transitions kept in RAM.
        """
        self.__dir = Path(dir_path)
        self.__dir.mkdir(parents=True, exist_ok=True)
        self.__history = deque(maxlen=max_history_size)
        self.__current_file = None
        self.__first_seed = None
        self.__last_seed = None

    @property
    def history(self):
        """Returns the current scenario's sliding window history as a list of Transition objects."""
        return list(self.__history)

    @property
    def current_file_path(self) -> str | None:
        """Filename (not full path) of the active history file, or None."""
        if self.__current_file is not None:
            return self.__current_file.name
        return None

    def start_scenario(self, scenario_name: str, seed: Optional[int] = None) -> None:
        """
        Creates a new unique .jsonl file for a specific scenario run.
        Uses a timestamp and unique ID to prevent filename collisions.

        Args:
            scenario_name: Name of the scenario being run.
            seed: Random seed used for this episode's domain randomization.
                  Tracks the first and last seed seen for the batch summary.
        """
        if self.__current_file is not None:
            self.end_scenario()
        now = datetime.now().strftime('%m%d%H%M') # Ex: 06091425
        tid = uuid.uuid4().hex[:8]
        file_path = self.__dir / f"history_{scenario_name}_{now}_{tid}.jsonl"
        self.__current_file = open(file_path, "a", buffering=1, encoding="utf-8")
        if seed is not None:
            if self.__first_seed is None:
                self.__first_seed = seed
            self.__last_seed = seed

    def put(self, transition: Transition) -> None:
        """
        Records a transition.
        Persists to disk if a scenario is active and appends to the RAM buffer.

        Args:
            transition: The transition object to record.
        """
        if self.__current_file is not None:
            self.__current_file.write(transition.to_recorder_json() + "\n")
        self.__history.append(transition)

    def end_scenario(self) -> Optional[str]:
        """Closes the current scenario file handle and resets the RAM buffer.

        Returns:
            The full path of the closed history file, or None if no scenario was active.
        """
        path = None
        if self.__current_file is not None:
            path = str(self.__current_file.name)
            self.__current_file.close()
            self.__current_file = None
        self.__history.clear()
        return path

    def summarize_batch(self) -> str:
        """
        Aggregates metrics from all .jsonl history files in the batch directory.
        Generates a summary.json file with totals and averages for both agents.

        Returns:
            The path to the generated summary.json file.
        """
        summary_file = self.__dir / "summary.json"

        summary = {
            "tests_ran": 0,
            "tests_passed": 0,
            "seeds": [self.__first_seed, self.__last_seed],
            "avg_score": 0.0,
            "total_score": 0.0,
        }

        for run_file in self.__dir.glob("history_*.jsonl"):
            try:
                with open(run_file, "r", encoding="utf-8") as f:
                    last_line = deque((line for line in f if line.strip()), maxlen=1)
                    if not last_line:
                        continue

                    # The new format: {"next_state": [...], "cur_state": [...], "actions": ..., "rewards": ..., "done": true|false}
                    last_transition = json.loads(last_line[0])

                summary["tests_ran"] += 1
                r = last_transition.get("rewards", 0.0)

                summary["total_score"] += r

                if r != 0:
                    summary["tests_passed"] += 1

            except (json.JSONDecodeError, IOError, IndexError) as e:
                logger.debug(f"Skipping corrupt file {run_file.name}: {e}")
                continue

        if summary["tests_ran"] > 0:
            summary["avg_score"] = summary["total_score"] / summary["tests_ran"]

        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(summary, f)

        return str(summary_file)
