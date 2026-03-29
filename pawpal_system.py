"""
pawpal_system.py
================
Backend logic for PawPal+ — a pet care scheduling assistant.

Class hierarchy
---------------
Task
    A single care activity assigned to a pet.

Pet
    A pet owned by an Owner. Holds a list of Tasks.

Owner
    The person using the app. Owns one or more Pets and sets
    the total time available for care each day.

Scheduler
    The scheduling engine. Retrieves pending tasks from an Owner's
    pets, sorts them by priority, and greedily fits as many as
    possible within the owner's available time budget.

Scheduling algorithm
--------------------
Tasks are sorted by:
  1. Priority  — high (0) → medium (1) → low (2)
  2. Duration  — shorter tasks first within the same priority tier
                 (maximises the number of tasks completed)

Frequency filtering
-------------------
``get_pending_tasks()`` respects the ``Task.frequency`` field:
  - ``"daily"`` and ``"as_needed"`` tasks are always eligible.
  - ``"weekly"`` tasks are eligible only when never completed or
    last completed ≥ 7 days ago (tracked via ``Task.last_done_date``).

Time slots
----------
``build_schedule()`` assigns a ``scheduled_start`` (minutes from
midnight) to each scheduled task, starting from
``Scheduler.day_start_minutes`` (default 480 = 8:00 AM).

Conflict detection
------------------
After building the schedule the scheduler checks for priority
inversions — cases where a higher-priority task was skipped while
lower-priority tasks were scheduled. Detected conflicts are stored
in ``Scheduler.conflicts`` and included in ``explain_plan()``.

Tasks that do not fit within the remaining time budget are collected
in ``skipped_tasks`` and reported via ``explain_plan()``.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
VALID_PRIORITIES = set(PRIORITY_ORDER.keys())
VALID_FREQUENCIES = {"daily", "weekly", "as_needed"}


@dataclass
class Task:
    """
    Represents a single pet care activity.

    Attributes
    ----------
    title : str
        Short name for the task (e.g. "Morning walk").
    duration_minutes : int
        How long the task takes in minutes.
    priority : str
        Scheduling urgency — one of ``"high"``, ``"medium"``, or ``"low"``.
    frequency : str
        How often the task recurs — ``"daily"`` (default), ``"weekly"``,
        or ``"as_needed"``.
    completed : bool
        ``True`` once the task has been marked done for the day.
    pet_name : str or None
        Name of the pet this task belongs to. Set automatically by
        ``Pet.add_task()``.
    last_done_date : str or None
        ISO date (``"YYYY-MM-DD"``) of the most recent ``mark_complete()``
        call. Used by ``is_due_today()`` to gate weekly tasks.
    scheduled_start : int or None
        Minutes from midnight assigned by ``Scheduler.build_schedule()``.
        ``None`` when not yet scheduled.
    preferred_time : str or None
        Owner's preferred wall-clock start time in ``"HH:MM"`` 24-hour
        format (e.g. ``"08:00"``, ``"17:30"``). Used by
        ``Scheduler.sort_by_time()`` to order tasks chronologically.
        ``None`` means no preference; such tasks sort to the end.
    next_due_date : str or None
        ISO date (``"YYYY-MM-DD"``) on or after which this task becomes
        eligible again. Set automatically by ``Pet.complete_and_reschedule()``
        on the freshly created next-occurrence instance:

        - ``"daily"``  → today + 1 day  (via ``timedelta(days=1)``)
        - ``"weekly"`` → today + 7 days (via ``timedelta(days=7)``)
        - ``"as_needed"`` → not set; no next occurrence is created

        When ``None``, ``is_due_today()`` falls back to frequency logic.
    """

    title: str
    duration_minutes: int
    priority: str           # "low", "medium", or "high"
    frequency: str = "daily"  # "daily", "weekly", "as_needed"
    completed: bool = False
    pet_name: Optional[str] = None
    last_done_date: Optional[str] = None   # set on mark_complete()
    scheduled_start: Optional[int] = None  # set by Scheduler
    preferred_time: Optional[str] = None   # "HH:MM" owner preference
    next_due_date: Optional[str] = None    # set by complete_and_reschedule()

    def __post_init__(self) -> None:
        if self.priority not in VALID_PRIORITIES:
            raise ValueError(
                f"priority must be one of {sorted(VALID_PRIORITIES)}, got {self.priority!r}"
            )
        if self.frequency not in VALID_FREQUENCIES:
            raise ValueError(
                f"frequency must be one of {sorted(VALID_FREQUENCIES)}, got {self.frequency!r}"
            )
        if self.preferred_time is not None:
            parts = self.preferred_time.split(":")
            if (
                len(parts) != 2
                or not parts[0].isdigit()
                or not parts[1].isdigit()
                or not (0 <= int(parts[0]) <= 23)
                or not (0 <= int(parts[1]) <= 59)
            ):
                raise ValueError(
                    f"preferred_time must be 'HH:MM' (24-hour), got {self.preferred_time!r}"
                )

    def is_due_today(self, today: Optional[str] = None) -> bool:
        """
        Return ``True`` if this task is eligible for today's schedule.

        Evaluation order
        ----------------
        1. If ``next_due_date`` is set (placed by ``complete_and_reschedule``),
           the task is eligible only on or after that date — this takes
           priority over the frequency rules below.
        2. ``"daily"`` and ``"as_needed"`` tasks are always eligible.
        3. ``"weekly"`` tasks are eligible when never completed or when
           last completed ≥ 7 days ago (``last_done_date`` check).

        Parameters
        ----------
        today : str, optional
            ISO date string ``"YYYY-MM-DD"``. Defaults to today's date.

        Returns
        -------
        bool
            ``True`` when the task should be offered for scheduling today,
            ``False`` when it should be withheld (e.g. a weekly task done
            yesterday, or a freshly rescheduled daily task not yet due).
        """
        if today is None:
            today = date.today().isoformat()

        # next_due_date gate — set by complete_and_reschedule() on the
        # freshly spawned instance; overrides all frequency logic.
        if self.next_due_date is not None:
            return date.fromisoformat(today) >= date.fromisoformat(self.next_due_date)

        if self.frequency in ("daily", "as_needed"):
            return True

        # weekly — eligible only after a 7-day gap since last completion
        if self.last_done_date is None:
            return True
        last = date.fromisoformat(self.last_done_date)
        return (date.fromisoformat(today) - last).days >= 7

    def update_task(
        self,
        title: str,
        duration_minutes: int,
        priority: str,
        frequency: Optional[str] = None,
        pet_name: Optional[str] = None,
    ) -> None:
        """
        Update the task's fields in place.

        Parameters
        ----------
        title : str
            New task title.
        duration_minutes : int
            New duration in minutes.
        priority : str
            New priority level (``"high"``, ``"medium"``, or ``"low"``).
        frequency : str, optional
            New frequency. Left unchanged if ``None``.
        pet_name : str, optional
            New pet association. Left unchanged if ``None``.
        """
        if priority not in VALID_PRIORITIES:
            raise ValueError(
                f"priority must be one of {sorted(VALID_PRIORITIES)}, got {priority!r}"
            )
        if frequency is not None and frequency not in VALID_FREQUENCIES:
            raise ValueError(
                f"frequency must be one of {sorted(VALID_FREQUENCIES)}, got {frequency!r}"
            )
        self.title = title
        self.duration_minutes = duration_minutes
        self.priority = priority
        if frequency is not None:
            self.frequency = frequency
        if pet_name is not None:
            self.pet_name = pet_name

    def mark_complete(self) -> None:
        """
        Mark this task as completed and record the completion date.

        Sets ``completed`` to ``True`` and writes today's ISO date to
        ``last_done_date``.  ``last_done_date`` is read by ``is_due_today()``
        to gate ``"weekly"`` tasks — a weekly task whose ``last_done_date``
        is less than 7 days ago will not appear in ``get_pending_tasks()``.

        For recurring tasks (``"daily"`` or ``"weekly"``), prefer calling
        ``Pet.complete_and_reschedule()`` instead, which marks this instance
        complete *and* automatically creates the next-occurrence copy.
        """
        self.completed = True
        self.last_done_date = date.today().isoformat()

    def mark_incomplete(self) -> None:
        """
        Reset this task to incomplete so it can be scheduled again.

        Clears the ``completed`` flag without touching ``last_done_date`` or
        ``next_due_date``, so frequency gating remains intact.  Use this to
        undo an accidental completion within the same session.
        """
        self.completed = False


@dataclass
class Pet:
    """
    Represents a pet owned by an Owner.

    Attributes
    ----------
    name : str
        The pet's name.
    species : str
        The pet's species (e.g. ``"dog"``, ``"cat"``).
    special_needs : str or None
        Any special care requirements (e.g. ``"Sensitive stomach"``).
    tasks : list[Task]
        All care tasks registered for this pet.
    """

    name: str
    species: str
    special_needs: Optional[str] = None
    tasks: list[Task] = field(default_factory=list)

    def update_pet(self, name: str, species: str, special_needs: Optional[str] = None) -> None:
        """
        Update the pet's details in place.

        Parameters
        ----------
        name : str
            New name.
        species : str
            New species.
        special_needs : str, optional
            Updated special needs. Pass ``None`` to clear.
        """
        self.name = name
        self.species = species
        self.special_needs = special_needs

    def add_task(self, task: Task) -> None:
        """
        Register a task for this pet.

        Automatically sets ``task.pet_name`` to this pet's name before
        appending, so the task always knows which pet it belongs to.

        Parameters
        ----------
        task : Task
            The task to add.
        """
        task.pet_name = self.name
        self.tasks.append(task)

    def remove_task(self, title: str) -> None:
        """
        Remove a task by title.

        If multiple tasks share the same title, all matching tasks are removed.

        Parameters
        ----------
        title : str
            Title of the task(s) to remove.
        """
        self.tasks = [t for t in self.tasks if t.title != title]

    def get_pending_tasks(self, today: Optional[str] = None) -> list[Task]:
        """
        Return tasks that are incomplete and due today based on their frequency.

        Parameters
        ----------
        today : str, optional
            ISO date string ``"YYYY-MM-DD"``. Defaults to today's date.
            Passed through to ``Task.is_due_today()``.

        Returns
        -------
        list[Task]
            Tasks that are not completed and pass the frequency check.
        """
        return [t for t in self.tasks if not t.completed and t.is_due_today(today)]

    def complete_and_reschedule(
        self, title: str, today: Optional[str] = None
    ) -> Optional[Task]:
        """
        Mark a task complete and automatically spawn the next occurrence.

        For recurring tasks the method creates a **new** ``Task`` instance
        (a copy of all fields) whose ``next_due_date`` is calculated with
        Python's ``timedelta``:

        - ``"daily"``  → ``today + timedelta(days=1)``  (tomorrow)
        - ``"weekly"`` → ``today + timedelta(days=7)``  (one week from today)
        - ``"as_needed"`` → task is marked complete; no new instance is created.

        The original task stays in ``self.tasks`` with ``completed=True``
        (useful for history). The new instance is appended and will appear
        in ``get_pending_tasks()`` on or after its ``next_due_date``.

        Parameters
        ----------
        title : str
            Title of the task to complete. The first matching *incomplete*
            task found is used.
        today : str, optional
            ISO date override (``"YYYY-MM-DD"``). Defaults to today's date.
            Primarily for testing without waiting for real dates.

        Returns
        -------
        Task or None
            The newly created next-occurrence ``Task``, or ``None`` when
            the frequency is ``"as_needed"`` or no matching task is found.
        """
        if today is None:
            today = date.today().isoformat()

        task = next(
            (t for t in self.tasks if t.title == title and not t.completed), None
        )
        if task is None:
            return None

        task.mark_complete()

        if task.frequency == "as_needed":
            return None

        today_date = date.fromisoformat(today)
        if task.frequency == "daily":
            next_due = today_date + timedelta(days=1)
        else:  # weekly
            next_due = today_date + timedelta(days=7)

        next_task = Task(
            title=task.title,
            duration_minutes=task.duration_minutes,
            priority=task.priority,
            frequency=task.frequency,
            pet_name=task.pet_name,
            preferred_time=task.preferred_time,
            next_due_date=next_due.isoformat(),
        )
        self.tasks.append(next_task)
        return next_task


class Owner:
    """
    Represents the pet owner using PawPal+.

    Attributes
    ----------
    name : str
        Owner's name.
    email : str
        Owner's email address.
    available_minutes : int
        Total minutes the owner has available for pet care today.
    pets : list[Pet]
        All pets registered to this owner.
    """

    def __init__(self, name: str, email: str, available_minutes: int) -> None:
        self.name = name
        self.email = email
        self.available_minutes = available_minutes
        self.pets: list[Pet] = []

    def update_owner(self, name: str, email: str, available_minutes: int) -> None:
        """
        Update the owner's details in place.

        Parameters
        ----------
        name : str
            New name.
        email : str
            New email address.
        available_minutes : int
            Updated daily time budget in minutes.
        """
        self.name = name
        self.email = email
        self.available_minutes = available_minutes

    def add_pet(self, pet: Pet) -> None:
        """
        Register a pet under this owner.

        Parameters
        ----------
        pet : Pet
            The pet to add.
        """
        self.pets.append(pet)

    def get_pet(self, name: str) -> Optional[Pet]:
        """
        Look up a pet by name.

        Parameters
        ----------
        name : str
            The pet's name to search for.

        Returns
        -------
        Pet or None
            The matching pet, or ``None`` if not found.
        """
        for pet in self.pets:
            if pet.name == name:
                return pet
        return None

    def get_all_tasks(self, today: Optional[str] = None) -> list[Task]:
        """
        Aggregate all pending, due tasks across every pet this owner has.

        This is the primary entry point used by ``Scheduler.load_tasks()``
        to collect tasks without needing to know about individual pets.

        Parameters
        ----------
        today : str, optional
            ISO date string passed through to ``Pet.get_pending_tasks()``.

        Returns
        -------
        list[Task]
            Flat list of all incomplete, frequency-eligible tasks from all pets.
        """
        all_tasks = []
        for pet in self.pets:
            all_tasks.extend(pet.get_pending_tasks(today))
        return all_tasks


class Scheduler:
    """
    The scheduling engine for PawPal+.

    Retrieves pending tasks from an owner's pet(s), sorts them by
    priority and duration, and greedily assigns them within the
    owner's available time budget.

    Attributes
    ----------
    owner : Owner
        The owner whose time budget and pets drive the schedule.
    pet : Pet or None
        If provided, the schedule is scoped to this single pet.
        If ``None``, all pets belonging to the owner are included.
    day_start_minutes : int
        Minute-of-day offset for the first task slot (default 480 = 8:00 AM).
    tasks : list[Task]
        The working queue of tasks to be scheduled.
    scheduled_tasks : list[Task]
        Tasks that fit within the time budget after ``build_schedule()``.
    skipped_tasks : list[Task]
        Tasks that were excluded because the time budget ran out.
    conflicts : list[str]
        Human-readable descriptions of priority inversions detected after
        the last ``build_schedule()`` call.
    """

    def __init__(
        self,
        owner: Owner,
        pet: Optional[Pet] = None,
        day_start_minutes: int = 480,
    ) -> None:
        self.owner = owner
        self.pet = pet
        self.day_start_minutes = day_start_minutes
        self.tasks: list[Task] = []
        self.scheduled_tasks: list[Task] = []
        self.skipped_tasks: list[Task] = []
        self.conflicts: list[str] = []

    def load_tasks(self, today: Optional[str] = None) -> None:
        """
        Populate ``self.tasks`` from the owner's pets.

        Applies frequency filtering via ``is_due_today()`` so weekly tasks
        that were recently completed are excluded automatically.

        If ``self.pet`` is set, loads only that pet's pending tasks.
        Otherwise, calls ``owner.get_all_tasks()`` to aggregate across
        all pets.

        Parameters
        ----------
        today : str, optional
            ISO date string passed through for frequency checks.
        """
        if self.pet is not None:
            self.tasks = self.pet.get_pending_tasks(today)
        else:
            self.tasks = self.owner.get_all_tasks(today)

    def add_task(self, task: Task) -> None:
        """
        Manually add a task to the scheduler queue.

        Useful for adding one-off tasks that aren't attached to a pet.

        Parameters
        ----------
        task : Task
            The task to add directly to the queue.
        """
        self.tasks.append(task)

    def build_schedule(self) -> list[Task]:
        """
        Build the daily schedule using a greedy algorithm.

        Steps performed:
        1. Load frequency-eligible pending tasks (always refreshed).
        2. Sort by priority then duration.
        3. Greedily assign tasks within the time budget.
        4. Assign contiguous time slots starting at ``day_start_minutes``.
        5. Detect priority inversions and record them in ``self.conflicts``.
        6. Detect ``preferred_time`` window overlaps via
           ``detect_time_conflicts()`` and append any warnings.

        Returns
        -------
        list[Task]
            The ordered list of tasks that fit within the time budget.
        """
        today = date.today().isoformat()
        self.load_tasks(today)
        self.conflicts = []

        if not self.tasks:
            self.scheduled_tasks = []
            self.skipped_tasks = []
            return []

        # Clear stale time-slot assignments before re-scheduling
        for task in self.tasks:
            task.scheduled_start = None

        sorted_tasks = sorted(
            self.tasks,
            key=lambda t: (PRIORITY_ORDER.get(t.priority, 99), t.duration_minutes),
        )

        available = self.owner.available_minutes
        self.scheduled_tasks = []
        self.skipped_tasks = []

        for task in sorted_tasks:
            if task.duration_minutes <= available:
                self.scheduled_tasks.append(task)
                available -= task.duration_minutes
            else:
                self.skipped_tasks.append(task)

        # Assign contiguous time slots from day_start_minutes
        current_time = self.day_start_minutes
        for task in self.scheduled_tasks:
            task.scheduled_start = current_time
            current_time += task.duration_minutes

        # Detect priority inversions: skipped task has higher priority
        # than at least one task that was scheduled
        if self.skipped_tasks and self.scheduled_tasks:
            scheduled_priorities = {
                PRIORITY_ORDER.get(t.priority, 99) for t in self.scheduled_tasks
            }
            for skipped in self.skipped_tasks:
                skipped_p = PRIORITY_ORDER.get(skipped.priority, 99)
                if any(sp > skipped_p for sp in scheduled_priorities):
                    self.conflicts.append(
                        f"'{skipped.title}' ({skipped.priority} priority, "
                        f"{skipped.duration_minutes} min) was skipped while "
                        f"lower-priority tasks were scheduled — consider "
                        f"shortening it or increasing available time."
                    )

        # Detect preferred_time window overlaps (same-pet and cross-pet)
        self.conflicts.extend(self.detect_time_conflicts())

        return self.scheduled_tasks

    def sort_by_time(self) -> list[Task]:
        """
        Return tasks sorted chronologically by their ``preferred_time`` attribute.

        Uses Python's ``sorted()`` with a lambda key that compares ``"HH:MM"``
        strings directly — lexicographic order on zero-padded 24-hour strings
        is identical to chronological order, so no integer parsing is needed::

            key=lambda t: t.preferred_time if t.preferred_time is not None else "99:99"

        The sentinel ``"99:99"`` ensures tasks with no ``preferred_time`` sort
        to the end rather than raising an error on ``None`` comparison.

        Source selection
        ----------------
        - ``scheduled_tasks + skipped_tasks`` when ``build_schedule()`` has run.
        - ``self.tasks`` otherwise (after ``load_tasks()`` or ``add_task()``).

        This method does **not** mutate any list; it always returns a new one.

        Returns
        -------
        list[Task]
            A new list ordered from earliest to latest preferred time.
            The original scheduler lists are unchanged.
        """
        source = (
            self.scheduled_tasks + self.skipped_tasks
            if (self.scheduled_tasks or self.skipped_tasks)
            else self.tasks
        )
        return sorted(
            source,
            key=lambda t: t.preferred_time if t.preferred_time is not None else "99:99",
        )

    def filter_tasks(
        self,
        pet_name: Optional[str] = None,
        completed: Optional[bool] = None,
    ) -> list[Task]:
        """
        Return a filtered view of the scheduler's task pool.

        Both filters are optional and composable.  When neither is supplied
        the full source list is returned unchanged.

        Source selection
        ----------------
        - ``scheduled_tasks + skipped_tasks`` when ``build_schedule()`` has run,
          so results reflect the most recent scheduling decision.
        - ``self.tasks`` otherwise (after ``load_tasks()`` or ``add_task()``).

        Parameters
        ----------
        pet_name : str, optional
            When provided, keep only tasks whose ``task.pet_name`` equals
            this value exactly (case-sensitive).  Pass ``None`` to include
            all pets (default).
        completed : bool, optional
            ``True``  → keep only tasks where ``task.completed is True``.
            ``False`` → keep only tasks where ``task.completed is False``.
            ``None``  → no status filter; return tasks regardless of completion.

        Returns
        -------
        list[Task]
            A new filtered list.  The scheduler's internal lists are not
            mutated.

        Examples
        --------
        Filter to one pet's pending tasks::

            scheduler.filter_tasks(pet_name="Mochi", completed=False)

        All completed tasks across every pet::

            scheduler.filter_tasks(completed=True)
        """
        source = (
            self.scheduled_tasks + self.skipped_tasks
            if (self.scheduled_tasks or self.skipped_tasks)
            else self.tasks
        )
        result = source
        if pet_name is not None:
            result = [t for t in result if t.pet_name == pet_name]
        if completed is not None:
            result = [t for t in result if t.completed == completed]
        return result

    def detect_time_conflicts(self) -> list[str]:
        """
        Check all tasks (scheduled and skipped) for ``preferred_time`` window
        overlaps and return warning strings — never raises an exception.

        Strategy (lightweight interval sweep)
        --------------------------------------
        For every task that has a ``preferred_time`` set, compute an integer
        window using ``_parse_time``:

            start = _parse_time(task.preferred_time)          # minutes from midnight
            end   = start + task.duration_minutes

        Then compare every pair (i, j) once (i < j).  Two windows overlap when::

            a_start < b_end  AND  b_start < a_end

        If they overlap the overlapping slice is::

            overlap_start = max(a_start, b_start)
            overlap_end   = min(a_end,   b_end)

        Both pets and cross-pet pairs are checked — the ``pet_name`` label in
        each warning tells the owner exactly which tasks are in conflict.

        Returns
        -------
        list[str]
            One human-readable warning per conflicting pair.
            Empty list when no overlaps are found.
        """
        warnings: list[str] = []

        source = (
            self.scheduled_tasks + self.skipped_tasks
            if (self.scheduled_tasks or self.skipped_tasks)
            else self.tasks
        )

        # Only tasks that carry a preferred_time can produce time conflicts.
        timed = [t for t in source if t.preferred_time is not None]

        for i in range(len(timed)):
            for j in range(i + 1, len(timed)):
                a, b = timed[i], timed[j]

                a_start = self._parse_time(a.preferred_time)
                a_end   = a_start + a.duration_minutes
                b_start = self._parse_time(b.preferred_time)
                b_end   = b_start + b.duration_minutes

                if a_start < b_end and b_start < a_end:
                    overlap_start = self._format_time(max(a_start, b_start))
                    overlap_end   = self._format_time(min(a_end,   b_end))
                    a_pet = f" [{a.pet_name}]" if a.pet_name else ""
                    b_pet = f" [{b.pet_name}]" if b.pet_name else ""
                    warnings.append(
                        f"Time conflict: '{a.title}'{a_pet} ({a.preferred_time},"
                        f" {a.duration_minutes} min) overlaps"
                        f" '{b.title}'{b_pet} ({b.preferred_time},"
                        f" {b.duration_minutes} min)"
                        f" — clash from {overlap_start} to {overlap_end}"
                    )

        return warnings

    @staticmethod
    def _parse_time(hhmm: str) -> int:
        """
        Convert a ``"HH:MM"`` 24-hour string to minutes from midnight.

        This is the inverse of ``_format_time`` and is used by
        ``detect_time_conflicts()`` to turn ``preferred_time`` strings into
        comparable integers for overlap arithmetic.

        Parameters
        ----------
        hhmm : str
            A zero-padded 24-hour time string, e.g. ``"08:00"`` or ``"17:30"``.

        Returns
        -------
        int
            Total minutes from midnight (``"08:30"`` → 510).
        """
        h, m = hhmm.split(":")
        return int(h) * 60 + int(m)

    @staticmethod
    def _format_time(minutes: int) -> str:
        """
        Convert minutes-from-midnight to a human-readable 12-hour time string.

        Wraps safely around midnight using modulo so values ≥ 1440 (24 h)
        are handled without raising.  Used by ``explain_plan()`` to render
        ``scheduled_start`` values and by ``detect_time_conflicts()`` to
        format the overlap window in warning messages.

        Parameters
        ----------
        minutes : int
            Total minutes elapsed since midnight (e.g. 510 = 8:30 AM).

        Returns
        -------
        str
            12-hour clock string with AM/PM suffix, e.g. ``"8:30 AM"`` or
            ``"5:45 PM"``.  Hours are not zero-padded; minutes always are.

        Examples
        --------
        >>> Scheduler._format_time(480)
        '8:00 AM'
        >>> Scheduler._format_time(1035)
        '5:15 PM'
        """
        h, m = divmod(minutes % (24 * 60), 60)
        period = "AM" if h < 12 else "PM"
        h = h % 12 or 12
        return f"{h}:{m:02d} {period}"

    def explain_plan(self) -> str:
        """
        Return a human-readable summary of the most recent schedule.

        Shows scheduled tasks with pet label, time slot, duration, and
        priority, followed by total time used, any skipped tasks, and
        any detected priority conflicts.

        Returns
        -------
        str
            Formatted schedule summary. Returns an instruction string if
            ``build_schedule()`` has not been called yet.
        """
        if not self.scheduled_tasks and not self.skipped_tasks:
            return "No schedule built yet. Call build_schedule() first."

        lines = [
            f"=== PawPal+ Daily Schedule for {self.owner.name} ===",
            f"Available time: {self.owner.available_minutes} minutes\n",
        ]

        if self.scheduled_tasks:
            lines.append("Scheduled tasks:")
            time_used = 0
            for task in self.scheduled_tasks:
                pet_label = f" [{task.pet_name}]" if task.pet_name else ""
                if task.scheduled_start is not None:
                    start = self._format_time(task.scheduled_start)
                    end = self._format_time(task.scheduled_start + task.duration_minutes)
                    time_label = f" | {start}–{end}"
                else:
                    time_label = ""
                lines.append(
                    f"  ✓ {task.title}{pet_label}{time_label}"
                    f" | {task.duration_minutes} min | {task.priority} priority"
                )
                time_used += task.duration_minutes
            lines.append(f"\nTime used: {time_used} / {self.owner.available_minutes} minutes")
        else:
            lines.append("No tasks could be scheduled within the available time.")

        if self.skipped_tasks:
            lines.append("\nSkipped (not enough time remaining):")
            for task in self.skipped_tasks:
                pet_label = f" [{task.pet_name}]" if task.pet_name else ""
                lines.append(
                    f"  ✗ {task.title}{pet_label} | {task.duration_minutes} min | {task.priority} priority"
                )

        if self.conflicts:
            lines.append("\n⚠️  Warnings:")
            for conflict in self.conflicts:
                lines.append(f"  ! {conflict}")

        return "\n".join(lines)
