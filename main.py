from pawpal_system import Owner, Pet, Task, Scheduler


def print_section(title: str) -> None:
    print()
    print("=" * 56)
    print(f"  {title}")
    print("=" * 56)


def main():
    # ── Owner ──────────────────────────────────────────────────
    owner = Owner(name="Jordan", email="jordan@email.com", available_minutes=120)

    # ── Pets ───────────────────────────────────────────────────
    mochi = Pet(name="Mochi", species="dog", special_needs="Sensitive stomach")
    luna  = Pet(name="Luna",  species="cat")

    # ── Tasks added deliberately OUT of chronological order ───
    # Mochi — afternoon task registered before the morning ones
    mochi.add_task(Task("Evening walk",   30, "medium", "daily",    preferred_time="17:30"))
    mochi.add_task(Task("Medication",      5, "high",   "daily",    preferred_time="08:00"))
    mochi.add_task(Task("Feeding",        10, "high",   "daily",    preferred_time="07:30"))
    mochi.add_task(Task("Grooming",       25, "medium", "weekly",   preferred_time="10:00"))
    mochi.add_task(Task("Trick training", 20, "low",    "as_needed",preferred_time="15:00"))

    # Luna — evening task registered before the morning ones
    luna.add_task(Task("Playtime",            15, "medium", "daily",  preferred_time="19:00"))
    luna.add_task(Task("Litter box cleaning", 10, "high",   "daily",  preferred_time="09:00"))
    luna.add_task(Task("Brushing",            20, "low",    "weekly", preferred_time="11:00"))

    owner.add_pet(mochi)
    owner.add_pet(luna)

    # ── Load tasks into scheduler ──────────────────────────────
    scheduler = Scheduler(owner=owner, day_start_minutes=480)  # 8:00 AM
    scheduler.load_tasks()

    # ── 1. Sort by preferred_time (HH:MM) before scheduling ───
    print_section("All tasks — sorted by preferred time (HH:MM)")
    for task in scheduler.sort_by_time():
        time_str  = task.preferred_time or "no pref"
        pet_label = f"[{task.pet_name}]" if task.pet_name else ""
        print(f"  {time_str}  {task.title:<25} {pet_label} ({task.priority})")

    # ── 2. Build the daily schedule ────────────────────────────
    scheduler.build_schedule()

    # ── 3. Auto-reschedule demonstration ──────────────────────────────────────
    # complete_and_reschedule() marks the task done AND spawns the next
    # occurrence with next_due_date calculated via timedelta.
    print_section("Auto-reschedule: complete a daily and a weekly task")

    # Complete a daily task — next occurrence due tomorrow (today + timedelta(days=1))
    next_feeding = mochi.complete_and_reschedule("Feeding")
    print(f"  'Feeding' marked complete.")
    if next_feeding:
        print(f"  → Next occurrence (daily):  due on {next_feeding.next_due_date}  (today + 1 day)")

    # Complete a weekly task — next occurrence due in 7 days (today + timedelta(days=7))
    next_grooming = mochi.complete_and_reschedule("Grooming")
    print(f"\n  'Grooming' marked complete.")
    if next_grooming:
        print(f"  → Next occurrence (weekly): due on {next_grooming.next_due_date}  (today + 7 days)")

    # Complete an as_needed task — no next occurrence created
    trick = next((t for t in mochi.tasks if t.title == "Trick training" and not t.completed), None)
    if trick:
        trick.mark_complete()
    print(f"\n  'Trick training' (as_needed) marked complete — no next occurrence created.")

    # ── 3. Filter: only Mochi's tasks ─────────────────────────
    print_section("Filter: Mochi's tasks only")
    for task in scheduler.filter_tasks(pet_name="Mochi"):
        status = "✓" if task.completed else "—"
        print(
            f"  [{status}] {task.title:<22} "
            f"{task.duration_minutes:>3} min  {task.priority}"
        )

    # ── 4. Filter: pending tasks only ─────────────────────────
    print_section("Filter: pending (not yet completed) tasks")
    for task in scheduler.filter_tasks(completed=False):
        pet_label = f"[{task.pet_name}]" if task.pet_name else ""
        print(f"  — {task.title:<25} {pet_label} ({task.priority})")

    # ── 5. Filter: completed tasks only ───────────────────────
    print_section("Filter: completed tasks")
    completed = scheduler.filter_tasks(completed=True)
    if completed:
        for task in completed:
            pet_label = f"[{task.pet_name}]" if task.pet_name else ""
            print(f"  ✓ {task.title:<25} {pet_label} ({task.priority})")
    else:
        print("  (none marked complete yet)")

    # ── 6. Sort scheduled tasks by preferred_time ──────────────
    print_section("Scheduled tasks — sorted by preferred time (HH:MM)")
    for task in scheduler.sort_by_time():
        if task in scheduler.scheduled_tasks:
            time_str = task.preferred_time or "no pref"
            pet_label = f"[{task.pet_name}]" if task.pet_name else ""
            print(f"  {time_str}  {task.title:<25} {pet_label}")

    # ── 7. Full schedule summary ───────────────────────────────
    print_section("PawPal+ — Today's Schedule")
    print(scheduler.explain_plan())
    print("=" * 56)

    # ── 8. Time-conflict detection demo ────────────────────────
    # Build a small owner with tasks whose preferred_time windows
    # intentionally overlap so the detector fires.
    print_section("Time Conflict Detection Demo")

    conflict_owner = Owner("Alex", "alex@example.com", 180)

    rex = Pet("Rex", "dog")
    # Window: 08:00 – 08:30 (30 min)
    rex.add_task(Task("Morning walk",  30, "high",   "daily", preferred_time="08:00"))
    # Window: 08:20 – 09:05 (45 min) → overlaps Morning walk at 08:20–08:30
    rex.add_task(Task("Vet check",     45, "high",   "daily", preferred_time="08:20"))
    # Window: 09:15 – 09:25 (10 min) → no overlap
    rex.add_task(Task("Feeding",       10, "medium", "daily", preferred_time="09:15"))

    mia = Pet("Mia", "cat")
    # Window: 08:10 – 08:25 (15 min) → overlaps Morning walk [Rex] at 08:10–08:25
    #                                 → also overlaps Vet check [Rex] at 08:20–08:25
    mia.add_task(Task("Litter box",    15, "high",   "daily", preferred_time="08:10"))
    # Window: 10:00 – 10:20 (20 min) → no overlap
    mia.add_task(Task("Playtime",      20, "low",    "daily", preferred_time="10:00"))

    conflict_owner.add_pet(rex)
    conflict_owner.add_pet(mia)

    conflict_scheduler = Scheduler(owner=conflict_owner, day_start_minutes=480)
    conflict_scheduler.build_schedule()

    time_conflicts = [c for c in conflict_scheduler.conflicts if c.startswith("Time conflict")]
    if time_conflicts:
        print(f"  {len(time_conflicts)} time conflict(s) detected:\n")
        for warning in time_conflicts:
            print(f"  ⚠️  {warning}")
    else:
        print("  No time conflicts found.")

    print()
    print("  Full plan (with warnings):")
    print(conflict_scheduler.explain_plan())
    print("=" * 56)


if __name__ == "__main__":
    main()
