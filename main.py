from pawpal_system import Owner, Pet, Task, Scheduler


def main():
    # --- Owner ---
    owner = Owner(name="Jordan", email="jordan@email.com", available_minutes=120)

    # --- Pets ---
    mochi = Pet(name="Mochi", species="dog", special_needs="Sensitive stomach")
    luna = Pet(name="Luna", species="cat")

    # --- Tasks for Mochi ---
    mochi.add_task(Task(title="Morning walk",    duration_minutes=30, priority="high",   frequency="daily"))
    mochi.add_task(Task(title="Feeding",         duration_minutes=10, priority="high",   frequency="daily"))
    mochi.add_task(Task(title="Medication",      duration_minutes=5,  priority="high",   frequency="daily"))
    mochi.add_task(Task(title="Grooming",        duration_minutes=25, priority="medium", frequency="weekly"))
    mochi.add_task(Task(title="Trick training",  duration_minutes=20, priority="low",    frequency="as_needed"))

    # --- Tasks for Luna ---
    luna.add_task(Task(title="Litter box cleaning", duration_minutes=10, priority="high",   frequency="daily"))
    luna.add_task(Task(title="Playtime",            duration_minutes=15, priority="medium", frequency="daily"))
    luna.add_task(Task(title="Brushing",            duration_minutes=20, priority="low",    frequency="weekly"))

    # --- Register pets to owner ---
    owner.add_pet(mochi)
    owner.add_pet(luna)

    # --- Build schedule ---
    scheduler = Scheduler(owner=owner)
    scheduler.build_schedule()

    # --- Print Today's Schedule ---
    print("=" * 50)
    print("         🐾 PawPal+ — Today's Schedule")
    print("=" * 50)
    print(scheduler.explain_plan())
    print("=" * 50)


if __name__ == "__main__":
    main()
