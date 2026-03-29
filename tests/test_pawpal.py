import pytest
from datetime import date, timedelta
from pawpal_system import Pet, Task, Owner, Scheduler


# ---------------------------------------------------------------------------
# Existing tests
# ---------------------------------------------------------------------------

def test_mark_complete_changes_status():
    task = Task(title="Morning walk", duration_minutes=30, priority="high")
    assert task.completed is False
    task.mark_complete()
    assert task.completed is True


def test_add_task_increases_pet_task_count():
    pet = Pet(name="Mochi", species="dog")
    assert len(pet.tasks) == 0
    pet.add_task(Task(title="Feeding", duration_minutes=10, priority="high"))
    assert len(pet.tasks) == 1
    pet.add_task(Task(title="Grooming", duration_minutes=25, priority="medium"))
    assert len(pet.tasks) != 3


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_owner_with_pet(available_minutes=120):
    """Return a fresh (Owner, Pet, Scheduler) triple."""
    owner = Owner(name="Alex", email="alex@example.com", available_minutes=available_minutes)
    pet = Pet(name="Mochi", species="dog")
    owner.add_pet(pet)
    scheduler = Scheduler(owner=owner)
    return owner, pet, scheduler


def _today():
    return date.today().isoformat()


def _days_ago(n):
    return (date.today() - timedelta(days=n)).isoformat()


def _days_from_now(n):
    return (date.today() + timedelta(days=n)).isoformat()


# ---------------------------------------------------------------------------
# 1. Sorting Correctness
#    Verify tasks are returned in chronological order by preferred_time.
# ---------------------------------------------------------------------------

class TestSortingCorrectness:

    def test_sort_by_time_returns_chronological_order(self):
        """Tasks with preferred_time are sorted earliest → latest."""
        owner, pet, scheduler = _make_owner_with_pet()
        pet.add_task(Task(title="Evening walk",  duration_minutes=30, priority="medium", preferred_time="17:00"))
        pet.add_task(Task(title="Morning walk",  duration_minutes=20, priority="high",   preferred_time="08:00"))
        pet.add_task(Task(title="Afternoon play", duration_minutes=15, priority="low",   preferred_time="13:30"))

        scheduler.load_tasks()
        sorted_tasks = scheduler.sort_by_time()

        assert [t.preferred_time for t in sorted_tasks] == ["08:00", "13:30", "17:00"]

    def test_tasks_without_preferred_time_sort_to_end(self):
        """Tasks with no preferred_time appear after all timed tasks."""
        owner, pet, scheduler = _make_owner_with_pet()
        pet.add_task(Task(title="No-time task",   duration_minutes=10, priority="high"))
        pet.add_task(Task(title="Morning feeding", duration_minutes=10, priority="high", preferred_time="07:00"))

        scheduler.load_tasks()
        sorted_tasks = scheduler.sort_by_time()

        assert sorted_tasks[0].title == "Morning feeding"
        assert sorted_tasks[-1].preferred_time is None

    def test_build_schedule_sorts_high_before_low_priority(self):
        """build_schedule places high-priority tasks ahead of low-priority ones."""
        owner, pet, scheduler = _make_owner_with_pet(available_minutes=60)
        pet.add_task(Task(title="Low task",  duration_minutes=20, priority="low"))
        pet.add_task(Task(title="High task", duration_minutes=20, priority="high"))

        scheduler.build_schedule()
        titles = [t.title for t in scheduler.scheduled_tasks]

        assert titles.index("High task") < titles.index("Low task")

    def test_same_priority_shorter_task_scheduled_first(self):
        """Within the same priority tier, shorter tasks come first."""
        owner, pet, scheduler = _make_owner_with_pet(available_minutes=60)
        pet.add_task(Task(title="Long medium",  duration_minutes=30, priority="medium"))
        pet.add_task(Task(title="Short medium", duration_minutes=10, priority="medium"))

        scheduler.build_schedule()
        titles = [t.title for t in scheduler.scheduled_tasks]

        assert titles.index("Short medium") < titles.index("Long medium")


# ---------------------------------------------------------------------------
# 2. Recurrence Logic
#    Confirm marking a daily task complete spawns the correct next occurrence.
# ---------------------------------------------------------------------------

class TestRecurrenceLogic:

    def test_daily_task_reschedule_creates_next_occurrence(self):
        """complete_and_reschedule on a daily task adds one new Task."""
        pet = Pet(name="Mochi", species="dog")
        pet.add_task(Task(title="Morning walk", duration_minutes=30, priority="high", frequency="daily"))

        next_task = pet.complete_and_reschedule("Morning walk", today=_today())

        assert next_task is not None
        assert len(pet.tasks) == 2  # original + new occurrence

    def test_daily_task_next_due_date_is_tomorrow(self):
        """Next occurrence for a daily task is due exactly one day later."""
        pet = Pet(name="Mochi", species="dog")
        pet.add_task(Task(title="Morning walk", duration_minutes=30, priority="high", frequency="daily"))

        today = _today()
        next_task = pet.complete_and_reschedule("Morning walk", today=today)

        assert next_task.next_due_date == _days_from_now(1)

    def test_weekly_task_next_due_date_is_seven_days_out(self):
        """Next occurrence for a weekly task is due exactly 7 days later."""
        pet = Pet(name="Mochi", species="dog")
        pet.add_task(Task(title="Bath time", duration_minutes=45, priority="medium", frequency="weekly"))

        next_task = pet.complete_and_reschedule("Bath time", today=_today())

        assert next_task.next_due_date == _days_from_now(7)

    def test_as_needed_task_produces_no_next_occurrence(self):
        """complete_and_reschedule on an as_needed task returns None."""
        pet = Pet(name="Mochi", species="dog")
        pet.add_task(Task(title="Vet visit", duration_minutes=60, priority="high", frequency="as_needed"))

        result = pet.complete_and_reschedule("Vet visit", today=_today())

        assert result is None
        assert len(pet.tasks) == 1  # no new task appended

    def test_next_occurrence_not_due_until_its_date(self):
        """A freshly rescheduled daily task does not appear in today's pending list."""
        pet = Pet(name="Mochi", species="dog")
        pet.add_task(Task(title="Morning walk", duration_minutes=30, priority="high", frequency="daily"))
        today = _today()
        pet.complete_and_reschedule("Morning walk", today=today)

        pending = pet.get_pending_tasks(today=today)

        assert all(t.title != "Morning walk" or not t.completed for t in pending)
        assert len(pending) == 0  # the rescheduled task is not due until tomorrow

    def test_weekly_task_not_due_within_seven_days(self):
        """A weekly task completed today is not pending for the next 6 days."""
        pet = Pet(name="Mochi", species="dog")
        pet.add_task(Task(title="Bath time", duration_minutes=45, priority="medium", frequency="weekly",
                          last_done_date=_today()))

        for offset in range(1, 7):
            pending_titles = [t.title for t in pet.get_pending_tasks(today=_days_from_now(offset))]
            assert "Bath time" not in pending_titles

    def test_weekly_task_due_on_day_seven(self):
        """A weekly task is eligible again exactly 7 days after completion."""
        pet = Pet(name="Mochi", species="dog")
        pet.add_task(Task(title="Bath time", duration_minutes=45, priority="medium", frequency="weekly",
                          last_done_date=_days_ago(7)))

        pending_titles = [t.title for t in pet.get_pending_tasks(today=_today())]

        assert "Bath time" in pending_titles

    def test_complete_nonexistent_task_returns_none(self):
        """complete_and_reschedule on an unknown title returns None without crashing."""
        pet = Pet(name="Mochi", species="dog")
        result = pet.complete_and_reschedule("Ghost task")
        assert result is None


# ---------------------------------------------------------------------------
# 3. Conflict Detection
#    Verify the Scheduler flags overlapping preferred_time windows.
# ---------------------------------------------------------------------------

class TestConflictDetection:

    def test_overlapping_preferred_times_produce_warning(self):
        """Two tasks whose time windows overlap generate a conflict warning."""
        owner, pet, scheduler = _make_owner_with_pet(available_minutes=120)
        pet.add_task(Task(title="Morning walk",   duration_minutes=30, priority="high",   preferred_time="08:00"))
        pet.add_task(Task(title="Morning feeding", duration_minutes=30, priority="medium", preferred_time="08:15"))

        scheduler.build_schedule()

        assert len(scheduler.conflicts) >= 1
        conflict_text = " ".join(scheduler.conflicts)
        assert "Morning walk" in conflict_text or "Morning feeding" in conflict_text

    def test_exact_same_preferred_time_flagged(self):
        """Two tasks starting at the identical time are always overlapping."""
        owner, pet, scheduler = _make_owner_with_pet(available_minutes=120)
        pet.add_task(Task(title="Walk",    duration_minutes=20, priority="high",   preferred_time="09:00"))
        pet.add_task(Task(title="Feeding", duration_minutes=15, priority="medium", preferred_time="09:00"))

        scheduler.build_schedule()

        assert any("Walk" in c or "Feeding" in c for c in scheduler.conflicts)

    def test_adjacent_non_overlapping_windows_produce_no_warning(self):
        """Tasks whose windows touch (end == start of next) do NOT conflict."""
        owner, pet, scheduler = _make_owner_with_pet(available_minutes=120)
        # 08:00–08:30 and 08:30–09:00 — strictly adjacent, not overlapping
        pet.add_task(Task(title="Walk",    duration_minutes=30, priority="high",   preferred_time="08:00"))
        pet.add_task(Task(title="Feeding", duration_minutes=30, priority="medium", preferred_time="08:30"))

        scheduler.build_schedule()

        time_conflicts = [c for c in scheduler.conflicts if "conflict" in c.lower()]
        assert len(time_conflicts) == 0

    def test_priority_inversion_flagged_when_high_priority_skipped(self):
        """A skipped high-priority task while low-priority tasks are scheduled triggers a conflict."""
        owner, pet, scheduler = _make_owner_with_pet(available_minutes=30)
        # Low-priority task fits; high-priority task is too long
        pet.add_task(Task(title="Quick groom", duration_minutes=20, priority="low"))
        pet.add_task(Task(title="Long vet prep", duration_minutes=60, priority="high"))

        scheduler.build_schedule()

        assert "Long vet prep" in scheduler.skipped_tasks[0].title
        assert any("Long vet prep" in c for c in scheduler.conflicts)

    def test_no_conflicts_when_no_preferred_times_set(self):
        """Tasks without preferred_time produce no time-conflict warnings."""
        owner, pet, scheduler = _make_owner_with_pet(available_minutes=120)
        pet.add_task(Task(title="Walk",    duration_minutes=20, priority="high"))
        pet.add_task(Task(title="Feeding", duration_minutes=10, priority="medium"))

        scheduler.build_schedule()

        time_conflicts = [c for c in scheduler.conflicts if "conflict" in c.lower()]
        assert len(time_conflicts) == 0


# ---------------------------------------------------------------------------
# 4. Edge Cases — Empty / Boundary Conditions
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_pet_with_no_tasks_returns_empty_schedule(self):
        """build_schedule on a pet with no tasks returns an empty list."""
        owner, pet, scheduler = _make_owner_with_pet()
        scheduler.build_schedule()
        assert scheduler.scheduled_tasks == []
        assert scheduler.skipped_tasks == []

    def test_zero_available_minutes_skips_all_tasks(self):
        """With 0 available minutes every task lands in skipped_tasks."""
        owner, pet, scheduler = _make_owner_with_pet(available_minutes=0)
        pet.add_task(Task(title="Walk", duration_minutes=10, priority="high"))
        scheduler.build_schedule()
        assert scheduler.scheduled_tasks == []
        assert len(scheduler.skipped_tasks) == 1

    def test_task_exactly_fills_budget_is_scheduled(self):
        """A task whose duration equals available_minutes is accepted (<=)."""
        owner, pet, scheduler = _make_owner_with_pet(available_minutes=30)
        pet.add_task(Task(title="Walk", duration_minutes=30, priority="high"))
        scheduler.build_schedule()
        assert len(scheduler.scheduled_tasks) == 1
        assert scheduler.skipped_tasks == []

    def test_task_one_minute_over_budget_is_skipped(self):
        """A task one minute longer than the budget is skipped."""
        owner, pet, scheduler = _make_owner_with_pet(available_minutes=29)
        pet.add_task(Task(title="Walk", duration_minutes=30, priority="high"))
        scheduler.build_schedule()
        assert scheduler.scheduled_tasks == []
        assert len(scheduler.skipped_tasks) == 1

    def test_invalid_priority_raises_value_error(self):
        """Constructing a Task with an invalid priority raises ValueError."""
        with pytest.raises(ValueError, match="priority"):
            Task(title="Bad task", duration_minutes=10, priority="urgent")

    def test_invalid_frequency_raises_value_error(self):
        """Constructing a Task with an invalid frequency raises ValueError."""
        with pytest.raises(ValueError, match="frequency"):
            Task(title="Bad task", duration_minutes=10, priority="high", frequency="hourly")

    def test_malformed_preferred_time_raises_value_error(self):
        """preferred_time values outside HH:MM 24-hour format raise ValueError."""
        with pytest.raises(ValueError, match="preferred_time"):
            Task(title="Bad task", duration_minutes=10, priority="high", preferred_time="25:00")
