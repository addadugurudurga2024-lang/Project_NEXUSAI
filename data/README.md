# NexusAI Enterprise Data Architecture

## Operational Architecture
NexusAI has transitioned from static 50K CSV datasets to an **Authoritative Multi-PM Enterprise Relational & Entity Model** managed dynamically within MongoDB.

### Data Model Hierarchy
```
Admin (Organization-wide visibility)
  └── Project Managers (12 PMs with distinct departmental scopes)
        └── Projects (30 distributed enterprise projects)
              └── Project Teams (~10-14 engineering members per project)
                    ├── Tasks (~18-20 tasks/project with status & hours)
                    ├── Sprints (Completed, Active, Planning sprints)
                    └── Issues (Quality defects & blockers)
```

### Dynamic Feature Extraction & Decision Intelligence
Machine learning inference models (`ml/inference/`) extract operational feature vectors directly in real time from live MongoDB collections (`projects`, `tasks`, `sprints`, `issues`, `employees`) rather than offline static CSV files.
