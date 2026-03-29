# PawPal+ (Module 2 Project)

You are building **PawPal+**, a Streamlit app that helps a pet owner plan care tasks for their pet.

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
- Consider constraints (time available, priority, owner preferences)
- Produce a daily plan and explain why it chose that plan

Your job is to design the system first (UML), then implement the logic in Python, then connect it to the Streamlit UI.

## What you will build

Your final app should:

- Let a user enter basic owner + pet info
- Let a user add/edit tasks (duration + priority at minimum)
- Generate a daily schedule/plan based on constraints and priorities
- Display the plan clearly (and ideally explain the reasoning)
- Include tests for the most important scheduling behaviors

## Getting started

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Suggested workflow

1. Read the scenario carefully and identify requirements and edge cases.
2. Draft a UML diagram (classes, attributes, methods, relationships).
3. Convert UML into Python class stubs (no logic yet).
4. Implement scheduling logic in small increments.
5. Add tests to verify key behaviors.
6. Connect your logic to the Streamlit UI in `app.py`.
7. Refine UML so it matches what you actually built.

---

## Smarter Scheduling

Beyond the core greedy scheduler, PawPal+ includes several algorithmic improvements that make daily planning more accurate and useful.

### Frequency-aware recurring tasks

Tasks carry a `frequency` field (`"daily"`, `"weekly"`, or `"as_needed"`). The scheduler respects this when loading tasks each day:

- **Daily** and **as_needed** tasks are always eligible.
- **Weekly** tasks are withheld until at least 7 days have passed since they were last completed (tracked via `Task.last_done_date`).

When a recurring task is marked complete, `Pet.complete_and_reschedule()` automatically creates the next occurrence using Python's `timedelta`:

- Daily → `next_due_date = today + timedelta(days=1)`
- Weekly → `next_due_date = today + timedelta(days=7)`

The owner never has to manually re-add recurring tasks.

### Preferred-time sorting

Every task accepts an optional `preferred_time` in `"HH:MM"` 24-hour format (e.g. `"08:00"`, `"17:30"`). Calling `Scheduler.sort_by_time()` returns tasks ordered chronologically using a `sorted()` lambda key that compares the strings directly — zero-padded 24-hour strings sort lexicographically in the same order as chronologically, so no parsing is needed.

### Status and pet filtering

`Scheduler.filter_tasks(pet_name, completed)` lets the owner slice the task pool in any combination:

| Call | Result |
|---|---|
| `filter_tasks(pet_name="Mochi")` | Only Mochi's tasks |
| `filter_tasks(completed=False)` | All pending tasks |
| `filter_tasks(pet_name="Luna", completed=True)` | Luna's completed tasks |

### Conflict detection

The scheduler detects two types of conflicts automatically after every `build_schedule()` call:

**Time conflicts** — If two tasks have `preferred_time` windows that overlap, a warning is generated with the exact clash window (e.g. `"clash from 8:20 AM to 8:30 AM"`). Both same-pet and cross-pet pairs are checked using the standard interval-overlap test: `a_start < b_end AND b_start < a_end`.

**Priority conflicts** — If a higher-priority task was skipped (because it was too long to fit) while a lower-priority task was scheduled, the scheduler flags it and suggests shortening the task or increasing available time.

All warnings surface in `explain_plan()` and in the Streamlit UI without crashing the program.
