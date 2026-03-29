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
- How did you decide which constraints mattered most?

**b. Tradeoffs**

- Describe one tradeoff your scheduler makes.

The scheduler uses a **greedy algorithm** rather than an optimal one. Tasks are sorted by priority (high → medium → low) and then by duration (shortest first within the same tier), and they are added to the schedule one by one until the time budget runs out. This means the scheduler can produce a suboptimal result — for example, if the owner has 60 minutes available and the tasks are a high-priority 55-minute walk and two medium-priority 30-minute tasks, the greedy approach picks the 55-minute walk first (leaving only 5 minutes), skipping both 30-minute tasks. An optimal solver (like a 0/1 knapsack algorithm) would instead pick the two 30-minute tasks, completing twice as many activities in the same window.

- Why is that tradeoff reasonable for this scenario?

For a daily pet care app with a realistic task list of 5–20 items, the greedy approach is entirely reasonable. It is fast (O(n log n) for the sort), easy to understand, and easy to explain to an owner — "high-priority tasks go first, and shorter tasks are preferred when priorities are equal." An optimal knapsack solution would add significant code complexity and would be much harder to reason about or debug, without meaningfully improving outcomes for the small task counts this app is designed for. The priority inversion warning system also partially compensates for the greedy approach's weakness by alerting the owner whenever a higher-priority task was skipped while lower-priority ones were scheduled.

---

## 3. AI Collaboration

**a. How you used AI**

- How did you use AI tools during this project (for example: design brainstorming, debugging, refactoring)?
- What kinds of prompts or questions were most helpful?

**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.
- How did you evaluate or verify what the AI suggested?

---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?
- Why were these tests important?

**b. Confidence**

- How confident are you that your scheduler works correctly?
- What edge cases would you test next if you had more time?

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?
