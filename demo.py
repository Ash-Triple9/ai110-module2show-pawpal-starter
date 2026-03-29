from pawpal_system import Owner, Pet, Task, Scheduler

# --- Setup ---
owner = Owner(name="Jordan", email="jordan@email.com", available_minutes=90)

mochi = Pet(name="Mochi", species="dog")
luna = Pet(name="Luna", species="cat")

mochi.add_task(Task(title="Morning walk", duration_minutes=30, priority="high"))
mochi.add_task(Task(title="Feeding", duration_minutes=10, priority="high"))
mochi.add_task(Task(title="Grooming", duration_minutes=25, priority="medium"))
mochi.add_task(Task(title="Trick training", duration_minutes=20, priority="low"))

luna.add_task(Task(title="Litter box cleaning", duration_minutes=10, priority="high"))
luna.add_task(Task(title="Playtime", duration_minutes=15, priority="medium"))
luna.add_task(Task(title="Brushing", duration_minutes=20, priority="low"))

owner.add_pet(mochi)
owner.add_pet(luna)

# --- Schedule all pets ---
print("=== Scheduling for ALL pets ===")
scheduler = Scheduler(owner=owner)
scheduler.build_schedule()
print(scheduler.explain_plan())

# --- Schedule for one pet only ---
print("\n=== Scheduling for Mochi only ===")
scheduler_mochi = Scheduler(owner=owner, pet=mochi)
scheduler_mochi.build_schedule()
print(scheduler_mochi.explain_plan())

# --- Edge case: no tasks ---
print("\n=== Edge case: owner with no pets ===")
empty_owner = Owner(name="Alex", email="alex@email.com", available_minutes=60)
scheduler_empty = Scheduler(owner=empty_owner)
scheduler_empty.build_schedule()
print(scheduler_empty.explain_plan())
