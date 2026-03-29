# PawPal+ Project Reflection

## 1. System Design

**a. Initial design**

- Briefly describe your initial UML design.

Must haves:
App needs to have owner information in the system if it's not already in. Include info like name, contact number, email, pets owned
Owner can enter pet information that includes pet name, diet, special needs etc. 
Owner can set total available minutes for the day
Tasks have a title, duration and priority
High priority tasks take precedence over low priority tasks
Schedule shows task order, time slots and total time used


Some of the edge cases that I need to look out for are:
What if no tasks are added and a request is made to generate a schedule?
What happens when a single task's duration exceeds the total available time?
What happens when some tasks do not fit and are dropped?
What happens if owner information is inputted incompletely?
What if duplicate pet names are present?
What if total available minutes are set to 0? Should there be a minimum number of minutes auto assigned for each task?
What happens when all tasks have same priority? What decides tie breakers?


- What classes did you include, and what responsibilities did you assign to each?

Class:
Owner
Pet
Tasks
Scheduler

Attributes:
Owner -> name, email, available minutes, pets
Pet -> name, species, special needs
Task -> title, duration minutes, priority, pet_name
Scheduler -> owner, pet, tasks

Methods:
Owner -> update_owner(name, email, available_minutes), add_pet(pet)
Pet -> update_pet(name, species, special_needs)
Task -> update_task(title, duration minutes, priority)
Scheduler -> build_schedule(), explain_plan(), add_task(task)



**b. Design changes**

- Did your design change during implementation?
Yes, I asked the AI agent in Cursor about my UML design as well as the responsibilities that I assigned to my classes.
- If yes, describe at least one change and why you made it.
One of the changes that I made after my initial design is removing a method called request_schedule() that I assigned to the Owner class. I realized that the Owner class is a data container which holds information about the person and should not be responsible for trigerring schedule logic. Since the scheduler class already had a build_schedule() method, I made the decision to remove the request_schedule() method.
It also suggested that Task class should have a field for the pet that the task is assigned to, which I felt is a good addition as well.
---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

- What constraints does your scheduler consider (for example: time, priority, preferences)?

The scheduler considers three layered constraints. First, **time** — the owner's `available_minutes` acts as a hard budget; no task is scheduled once the remaining budget would go negative. Second, **priority** — tasks are ranked `high → medium → low`, and the sort order ensures high-priority tasks are always considered before lower-priority ones. Third, **frequency** — a `"weekly"` task is withheld from the schedule if it was completed fewer than 7 days ago, and a `"daily"` or rescheduled task is withheld until its `next_due_date`. An optional fourth layer, `preferred_time`, lets the owner express a chronological preference, which is used by `sort_by_time()` and flagged when two windows overlap.

- How did you decide which constraints mattered most?

Time is the hardest constraint because it is physically non-negotiable — you cannot fit 130 minutes of tasks into a 120-minute window. Priority is the next most important because it determines which tasks survive when the budget runs out. Frequency was added because without it a "weekly" bath would reappear every day. Preferred time is intentionally the softest constraint — it influences ordering and generates warnings, but never overrides priority or budget decisions.

**b. Tradeoffs**

- Describe one tradeoff your scheduler makes.

The scheduler uses a **greedy algorithm** rather than an optimal one. Tasks are sorted by priority (high → medium → low) and then by duration (shortest first within the same tier), and they are added to the schedule one by one until the time budget runs out. This means the scheduler can produce a suboptimal result — for example, if the owner has 60 minutes available and the tasks are a high-priority 55-minute walk and two medium-priority 30-minute tasks, the greedy approach picks the 55-minute walk first (leaving only 5 minutes), skipping both 30-minute tasks. An optimal solver (like a 0/1 knapsack algorithm) would instead pick the two 30-minute tasks, completing twice as many activities in the same window.

- Why is that tradeoff reasonable for this scenario?

For a daily pet care app with a realistic task list of 5–20 items, the greedy approach is entirely reasonable. It is fast (O(n log n) for the sort), easy to understand, and easy to explain to an owner — "high-priority tasks go first, and shorter tasks are preferred when priorities are equal." An optimal knapsack solution would add significant code complexity and would be much harder to reason about or debug, without meaningfully improving outcomes for the small task counts this app is designed for. The priority inversion warning system also partially compensates for the greedy approach's weakness by alerting the owner whenever a higher-priority task was skipped while lower-priority ones were scheduled.

---

## 3. AI Collaboration

**a. How you used AI**

- How did you use AI tools during this project (for example: design brainstorming, debugging, refactoring)?

AI tools in Cursor were used across every phase of the project, but with a different role at each stage. During **design**, I used chat to stress-test my initial UML — asking "does this class have the right responsibilities?" and "what edge cases am I missing?" rather than asking it to generate the design for me. During **implementation**, I used inline completions to speed up boilerplate (`@dataclass` field declarations, `__post_init__` validation blocks) and chat to talk through algorithm decisions like the greedy sort key. During **testing**, I used chat to brainstorm edge cases organized by category (boundary conditions, recurrence logic, conflict detection) and then wrote the actual test functions myself so I understood each assertion. During **documentation**, I used chat to draft prose for the README and reflection, then edited for accuracy and voice.

- What kinds of prompts or questions were most helpful?

The most effective prompts were **specific and scoped to one decision at a time**: "Should `is_due_today()` live on `Task` or on `Pet`?", "What is the off-by-one risk in the `>= 7` day check?", "List edge cases for the greedy budget loop." Broad prompts like "build me a scheduler" produced output that was hard to evaluate and didn't match my design. Narrow prompts about one method or one test category produced answers I could verify against the existing code and reason about clearly.

**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.

When I asked for help with conflict detection, the AI initially suggested adding a `conflicts` list directly to the `Task` dataclass so each task could record its own overlaps. I rejected this because it violated the single-responsibility principle — a `Task` is a data container and should not know about other tasks or scheduling decisions. I kept `conflicts` on the `Scheduler` class instead, where scheduling decisions are made, and had `detect_time_conflicts()` compare tasks as pairs. This kept `Task` clean and made the conflict logic easy to test in isolation.

- How did you evaluate or verify what the AI suggested?

I evaluated every suggestion against two questions: (1) does this fit the class responsibilities I defined in my UML, and (2) can I write a test that would catch a bug in this logic? If the answer to either was "not easily," I pushed back or redesigned. For the conflict detection case, I confirmed the right design by tracing through what `build_schedule()` already knew — it has access to all tasks simultaneously, making it the natural place to do pairwise comparisons. The `Task` class has no such visibility.

---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?

The 26-test suite covers four areas. **Sorting correctness** (4 tests): `sort_by_time()` returns tasks in chronological `preferred_time` order; tasks without a time preference sort to the end; `build_schedule()` orders high before low priority; shorter tasks precede longer ones within the same priority tier. **Recurrence logic** (8 tests): daily and weekly reschedules produce the correct `next_due_date`; the rescheduled task is absent from today's pending list but present on its due date; a weekly task is withheld for exactly 6 days and re-eligible on day 7; `as_needed` tasks produce no follow-up occurrence; completing a non-existent task returns `None` safely. **Conflict detection** (5 tests): overlapping and identical `preferred_time` windows produce warnings; adjacent non-overlapping windows do not; priority inversions are flagged; tasks with no `preferred_time` produce no spurious warnings. **Edge cases** (7 tests): pet with no tasks, zero budget, exact-fit budget, one-minute-over budget, and all three `ValueError` validation paths.

- Why were these tests important?

The recurrence boundary (`>= 7` days) and the budget boundary (`<=` not `<`) are both places where an off-by-one error is completely silent — the app runs without crashing but schedules the wrong tasks. The conflict detection tests are important because the overlap condition uses strict `<` inequality, and swapping it to `<=` would silently stop flagging adjacent windows as conflicts. Without explicit tests for these three points, regressions in any of them would be invisible to a manual reviewer.

**b. Confidence**

- How confident are you that your scheduler works correctly?

High confidence in the core scheduling contract. Every branching path in the greedy loop, the recurrence gate, and the conflict detection sweep is exercised by at least one test. The test suite runs in under 0.2 seconds and all 26 tests pass.

- What edge cases would you test next if you had more time?

Multi-pet scheduling — verifying that tasks from two different pets are correctly interleaved by priority and that `pet_name` is always set. Also: a task whose `next_due_date` is in the past (overdue task should surface), and a schedule built at 11:45 PM where time slots wrap past midnight to confirm `_format_time`'s modulo handling renders correctly.

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

The layered constraint system came together more cleanly than I expected. Time, priority, frequency, and preferred time each live in exactly one place in the code and are tested independently — they compose without coupling. The decision to keep `Task` as a pure data container and push all scheduling intelligence into `Scheduler` made every method easy to read, easy to test, and easy to explain in `explain_plan()`. I'm also satisfied with the recurrence design: `complete_and_reschedule()` creates a new Task instance rather than mutating the old one, so the original stays in the task list as history while the next occurrence becomes a first-class object with its own due date.

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

I would replace the greedy sort with a two-pass approach: first schedule all high-priority tasks that fit (regardless of duration order), then fill remaining time with medium and low tasks sorted by duration. The current tie-break (shorter tasks first within a priority tier) occasionally wastes budget — a 5-minute low task scheduled before a 50-minute high task that barely fits would be better served by the high task going first. I would also add a `NotificationService` class to send reminders at each task's `preferred_time`, and a persistence layer (JSON file or SQLite) so tasks and history survive between sessions.

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?

The most important thing I learned is that AI tools amplify whatever clarity or confusion already exists in your design. When I came to a chat session with a specific, well-scoped question — "should this method live on `Task` or `Scheduler`?" — I got a precise, useful answer I could act on immediately. When I asked a vague question — "help me build the scheduler" — I got plausible-looking code that didn't fit my class hierarchy and required more effort to evaluate than to write myself. Being the lead architect means arriving at every AI conversation with a concrete decision to make, not an open-ended problem to hand off. The AI is a fast, knowledgeable collaborator that needs direction, not a replacement for design thinking.

---

## 6. AI Strategy (Cursor)

**a. Most effective features**

The two most effective Cursor features were **inline chat scoped to a selected block of code** and **multi-turn chat sessions organized by phase**. Inline chat was most useful for validation logic and docstrings — I could highlight `__post_init__` and ask "what input should this reject?" without losing context. Multi-turn chat was most useful for test planning: I could describe the behavior under test, ask for edge cases, refine the list, and arrive at a complete set of assertions before writing a single line of test code.

**b. One suggestion rejected or modified**

When drafting the conflict detection method, Cursor suggested storing a `conflicts` list on each `Task` object so tasks could record their own overlaps. I rejected this because it broke the single-responsibility boundary I had established — `Task` is a data container, not a scheduling decision-maker. Only `Scheduler` has visibility over all tasks simultaneously, making it the correct owner of conflict state. I kept the suggestion's core idea (pairwise interval comparison) but moved it entirely into `Scheduler.detect_time_conflicts()`. The result is a method that is independently testable and leaves `Task` with zero knowledge of other tasks.

**c. How separate chat sessions helped**

Keeping distinct chat sessions for UML design, logic implementation, test planning, and documentation prevented context bleed between phases. During the design session I was free to explore and discard class ideas without those dead ends surfacing as suggestions later. During the test session the AI had no knowledge of implementation shortcuts and could challenge assumptions about behavior more honestly. Mixing all phases into one long session would have produced suggestions anchored to earlier decisions I had already moved past.

**d. Being the "lead architect"**

Working with a capable AI accelerates execution dramatically, but it does not replace judgment. Every AI suggestion exists in a vacuum — it does not know your prior design decisions, your team's conventions, or the tradeoffs you consciously chose. As lead architect, my job was to hold that context and use it as a filter. The moments where I pushed back on a suggestion (moving `conflicts` off `Task`, removing `request_schedule()` from `Owner`) were also the moments where my design became more coherent — not because the AI was wrong, but because evaluating its suggestion forced me to articulate exactly why my design was structured the way it was. The skill of working with AI is not prompting; it is knowing when to say no and being able to explain why.
