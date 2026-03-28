from dataclasses import dataclass
from typing import Optional


@dataclass
class Pet:
    name: str
    species: str
    special_needs: Optional[str] = None

    def update_pet(self, name: str, species: str, special_needs: Optional[str] = None) -> None:
        pass


@dataclass
class Task:
    title: str
    duration_minutes: int
    priority: str  # "low", "medium", or "high"
    pet_name: Optional[str] = None

    def update_task(self, title: str, duration_minutes: int, priority: str, pet_name: Optional[str] = None) -> None:
        pass


class Owner:
    def __init__(self, name: str, email: str, available_minutes: int) -> None:
        self.name = name
        self.email = email
        self.available_minutes = available_minutes
        self.pets: list[Pet] = []

    def update_owner(self, name: str, email: str, available_minutes: int) -> None:
        pass

    def add_pet(self, pet: Pet) -> None:
        pass


class Scheduler:
    def __init__(self, owner: Owner, pet: Pet) -> None:
        self.owner = owner
        self.pet = pet
        self.tasks: list[Task] = []
        self.scheduled_tasks: list[Task] = []
        self.skipped_tasks: list[Task] = []

    def add_task(self, task: Task) -> None:
        pass

    def build_schedule(self) -> list[Task]:
        pass

    def explain_plan(self) -> str:
        pass
