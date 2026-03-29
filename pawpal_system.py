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

Tasks that do not fit within the remaining time budget are collected
in ``skipped_tasks`` and reported via ``explain_plan()``.
"""

from dataclasses import dataclass, field
from typing import Optional

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


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
    """

    title: str
    duration_minutes: int
    priority: str           # "low", "medium", or "high"
    frequency: str = "daily"  # "daily", "weekly", "as_needed"
    completed: bool = False
    pet_name: Optional[str] = None

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
        self.title = title
        self.duration_minutes = duration_minutes
        self.priority = priority
        if frequency is not None:
            self.frequency = frequency
        if pet_name is not None:
            self.pet_name = pet_name

    def mark_complete(self) -> None:
        """Mark this task as completed. Completed tasks are excluded from scheduling."""
        self.completed = True

    def mark_incomplete(self) -> None:
        """Reset this task to incomplete so it can be scheduled again."""
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

    def get_pending_tasks(self) -> list[Task]:
        """Return all tasks that have not yet been marked complete."""
        return [t for t in self.tasks if not t.completed]


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

    def get_all_tasks(self) -> list[Task]:
        """
        Aggregate all pending tasks across every pet this owner has.

        This is the primary entry point used by ``Scheduler.load_tasks()``
        to collect tasks without needing to know about individual pets.

        Returns
        -------
        list[Task]
            Flat list of all incomplete tasks from all pets.
        """
        all_tasks = []
        for pet in self.pets:
            all_tasks.extend(pet.get_pending_tasks())
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
    tasks : list[Task]
        The working queue of tasks to be scheduled.
    scheduled_tasks : list[Task]
        Tasks that fit within the time budget after ``build_schedule()``.
    skipped_tasks : list[Task]
        Tasks that were excluded because the time budget ran out.
    """

    def __init__(self, owner: Owner, pet: Optional[Pet] = None) -> None:
        self.owner = owner
        self.pet = pet
        self.tasks: list[Task] = []
        self.scheduled_tasks: list[Task] = []
        self.skipped_tasks: list[Task] = []

    def load_tasks(self) -> None:
        """
        Populate ``self.tasks`` from the owner's pets.

        If ``self.pet`` is set, loads only that pet's pending tasks.
        Otherwise, calls ``owner.get_all_tasks()`` to aggregate across
        all pets.
        """
        if self.pet is not None:
            self.tasks = self.pet.get_pending_tasks()
        else:
            self.tasks = self.owner.get_all_tasks()

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

        Tasks are sorted by priority (high first), then by duration
        (shorter first within the same tier) to maximise the number
        of tasks that fit. Tasks are added to the schedule until the
        time budget is exhausted; remaining tasks go to ``skipped_tasks``.

        Calls ``load_tasks()`` automatically if the queue is empty.

        Returns
        -------
        list[Task]
            The ordered list of tasks that fit within the time budget.
        """
        if not self.tasks:
            self.load_tasks()

        if not self.tasks:
            self.scheduled_tasks = []
            self.skipped_tasks = []
            return []

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

        return self.scheduled_tasks

    def explain_plan(self) -> str:
        """
        Return a human-readable summary of the most recent schedule.

        Shows scheduled tasks with pet label, duration, and priority,
        followed by total time used and any skipped tasks with reasons.

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
                lines.append(
                    f"  ✓ {task.title}{pet_label} | {task.duration_minutes} min | {task.priority} priority"
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

        return "\n".join(lines)
