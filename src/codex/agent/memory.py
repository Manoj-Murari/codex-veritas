```python
from typing import List

class Task:
    def __init__(self, description: str):
        self.description = description
        self.completed = False

class Memory:
    def __init__(self):
        self.tasks: List[Task] = []

    def add_task(self, task: Task):
        self.tasks.append(task)

    def list_tasks(self) -> List[str]:
        return [task.description for task in self.tasks]


```