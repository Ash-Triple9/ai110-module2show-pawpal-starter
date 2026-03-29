from datetime import time as dtime

import streamlit as st
from pawpal_system import Owner, Pet, Task, Scheduler

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")
st.title("🐾 PawPal+")
st.caption("A daily pet care scheduler.")

# ── Session state initialisation ──────────────────────────────────────────────
if "owner" not in st.session_state:
    st.session_state["owner"] = None

if "scheduler" not in st.session_state:
    st.session_state["scheduler"] = None

# ── Section 1: Owner setup ─────────────────────────────────────────────────────
st.header("1. Owner Info")

with st.form("owner_form"):
    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("Your name", value="Jordan")
        email = st.text_input("Email", value="jordan@email.com")
    with col2:
        available_minutes = st.number_input(
            "Minutes available today", min_value=0, max_value=720, value=120, step=10
        )
    save_owner = st.form_submit_button("Save owner info")

if save_owner:
    if not name.strip():
        st.warning("Please enter your name.")
    elif st.session_state["owner"] is None:
        st.session_state["owner"] = Owner(name.strip(), email.strip(), int(available_minutes))
        st.success(f"Owner '{name}' created.")
    else:
        st.session_state["owner"].update_owner(name.strip(), email.strip(), int(available_minutes))
        st.success(f"Owner info updated.")

if st.session_state["owner"] is None:
    st.info("Save your owner info above to continue.")
    st.stop()

owner: Owner = st.session_state["owner"]

# ── Section 2: Pets ────────────────────────────────────────────────────────────
st.divider()
st.header("2. Your Pets")

with st.form("pet_form"):
    col1, col2, col3 = st.columns(3)
    with col1:
        pet_name = st.text_input("Pet name")
    with col2:
        species = st.selectbox("Species", ["dog", "cat", "other"])
    with col3:
        special_needs = st.text_input("Special needs (optional)")
    add_pet = st.form_submit_button("Add pet")

if add_pet:
    if not pet_name.strip():
        st.warning("Please enter a pet name.")
    else:
        new_pet = Pet(
            name=pet_name.strip(),
            species=species,
            special_needs=special_needs.strip() or None,
        )
        owner.add_pet(new_pet)
        st.success(f"Added **{pet_name}** ({species}).")

if owner.pets:
    for pet in owner.pets:
        needs = f" — *{pet.special_needs}*" if pet.special_needs else ""
        st.markdown(f"- **{pet.name}** ({pet.species}){needs}")
else:
    st.info("No pets added yet. Add one above.")

# ── Section 3: Tasks ───────────────────────────────────────────────────────────
st.divider()
st.header("3. Tasks")

if not owner.pets:
    st.info("Add a pet first before adding tasks.")
else:
    pet_names = [p.name for p in owner.pets]

    with st.form("task_form"):
        selected_pet_name = st.selectbox("Assign to pet", pet_names)
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            task_title = st.text_input("Task title", value="Morning walk")
        with col2:
            duration = st.number_input("Duration (min)", min_value=1, max_value=240, value=20)
        with col3:
            priority = st.selectbox("Priority", ["high", "medium", "low"])
        with col4:
            frequency = st.selectbox("Frequency", ["daily", "weekly", "as_needed"])
        add_task = st.form_submit_button("Add task")

    if add_task:
        if not task_title.strip():
            st.warning("Please enter a task title.")
        else:
            target_pet = owner.get_pet(selected_pet_name)
            target_pet.add_task(
                Task(
                    title=task_title.strip(),
                    duration_minutes=int(duration),
                    priority=priority,
                    frequency=frequency,
                )
            )
            st.session_state["scheduler"] = None  # invalidate old schedule
            st.success(f"Added **{task_title}** to {selected_pet_name}.")

    # ── Filter controls ───────────────────────────────────────────────────────
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        filter_pet = st.selectbox("Filter by pet", ["All"] + pet_names, key="filter_pet")
    with col_f2:
        filter_status = st.selectbox(
            "Filter by status", ["All", "Pending", "Completed"], key="filter_status"
        )

    # ── Task list with completion checkboxes ──────────────────────────────────
    task_changed = False
    any_shown = False

    for pet in owner.pets:
        if filter_pet != "All" and pet.name != filter_pet:
            continue

        tasks_to_show = pet.tasks
        if filter_status == "Pending":
            tasks_to_show = [t for t in tasks_to_show if not t.completed]
        elif filter_status == "Completed":
            tasks_to_show = [t for t in tasks_to_show if t.completed]

        if not tasks_to_show:
            continue

        any_shown = True
        st.markdown(f"**{pet.name}'s tasks:**")

        for t in tasks_to_show:
            col_chk, col_info, col_meta = st.columns([1, 5, 2])
            with col_chk:
                new_val = st.checkbox(
                    "done",
                    value=t.completed,
                    key=f"done_{pet.name}_{t.title}",
                    label_visibility="collapsed",
                )
            with col_info:
                title_fmt = f"~~{t.title}~~" if t.completed else t.title
                st.markdown(
                    f"{title_fmt} — {t.duration_minutes} min"
                    f" | **{t.priority}** priority | _{t.frequency}_"
                )
            with col_meta:
                if t.frequency == "weekly":
                    last = t.last_done_date or "never"
                    st.caption(f"Last done: {last}")

            if new_val != t.completed:
                if new_val:
                    # complete_and_reschedule marks the task done AND
                    # appends a fresh next-occurrence instance for daily/weekly tasks.
                    pet.complete_and_reschedule(t.title)
                else:
                    t.mark_incomplete()
                task_changed = True

    if not any_shown:
        st.info("No tasks match the current filter.")

    if task_changed:
        st.session_state["scheduler"] = None
        st.rerun()

# ── Section 4: Generate schedule ──────────────────────────────────────────────
st.divider()
st.header("4. Today's Schedule")

col_time, col_gap = st.columns([2, 3])
with col_time:
    day_start = st.time_input("Schedule starts at", value=dtime(8, 0), key="day_start")
day_start_minutes = day_start.hour * 60 + day_start.minute

if st.button("Generate schedule", type="primary"):
    if not owner.get_all_tasks():
        st.warning("Add at least one task before generating a schedule.")
    else:
        scheduler = Scheduler(owner=owner, day_start_minutes=day_start_minutes)
        scheduler.build_schedule()
        st.session_state["scheduler"] = scheduler

if st.session_state["scheduler"] is not None:
    scheduler: Scheduler = st.session_state["scheduler"]

    if scheduler.scheduled_tasks:
        time_used = sum(t.duration_minutes for t in scheduler.scheduled_tasks)
        st.success(
            f"Scheduled **{len(scheduler.scheduled_tasks)} task(s)** — "
            f"{time_used} / {owner.available_minutes} minutes used."
        )
        st.table(
            [
                {
                    "Task": t.title,
                    "Pet": t.pet_name or "—",
                    "Start": (
                        Scheduler._format_time(t.scheduled_start)
                        if t.scheduled_start is not None else "—"
                    ),
                    "End": (
                        Scheduler._format_time(t.scheduled_start + t.duration_minutes)
                        if t.scheduled_start is not None else "—"
                    ),
                    "Duration (min)": t.duration_minutes,
                    "Priority": t.priority,
                    "Frequency": t.frequency,
                }
                for t in scheduler.scheduled_tasks
            ]
        )
    else:
        st.error("No tasks could be scheduled within your available time.")

    if scheduler.conflicts:
        st.warning(f"⚠️ {len(scheduler.conflicts)} priority conflict(s) detected")
        for conflict in scheduler.conflicts:
            st.error(f"**Conflict:** {conflict}")

    if scheduler.skipped_tasks:
        with st.expander(f"⚠️ {len(scheduler.skipped_tasks)} task(s) skipped — not enough time"):
            for task in scheduler.skipped_tasks:
                pet_label = f" [{task.pet_name}]" if task.pet_name else ""
                st.markdown(
                    f"- **{task.title}**{pet_label} — {task.duration_minutes} min ({task.priority} priority)"
                )

    with st.expander("Full plan explanation"):
        st.text(scheduler.explain_plan())
