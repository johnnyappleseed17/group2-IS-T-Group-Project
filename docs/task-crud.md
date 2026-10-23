# Manager task CRUD

Managers can create tasks from the dashboard or **Created Tasks**, then edit or delete their own tasks from the list. Existing employee dashboards and acceptance links continue to use the same models and routes.

## Routes

| Page | URL | Django URL name |
| --- | --- | --- |
| Own created tasks | `/tasks/mine/` | `tasks:my_created_tasks` |
| Create | `/tasks/create/` | `tasks:task_create` |
| Edit | `/tasks/<task_id>/edit/` | `tasks:task_update` |
| Delete confirmation | `/tasks/<task_id>/delete/` | `tasks:task_delete` |

Create, edit and delete accept GET for the page and POST for submission. Viewing the delete confirmation never deletes a task. Forms include CSRF protection and show validation errors without losing entered values.

## Behavior

- The account must have an approved manager profile. Staff/superuser status alone does not grant access.
- Managers can modify only tasks they created. Other managers' task IDs return 404.
- Editable fields are title, description, due date, number of employees needed and optional existing categories. The server sets the creator; ownership, archive and completion fields cannot be changed through these forms.
- The number needed must be at least one and cannot fall below the current assignment count. Editing preserves existing assignments.
- Any assignment, including a completed assignment, prevents permanent deletion. The confirmation page explains this and links to editing. A blocked delete POST returns 409 and preserves the task and assignments.
- Successful submissions return to the created-task list with a success message. The existing list still shows ten tasks per page, ordered by due date and ID.
- The shared layout displays messages. The dashboard requires an approved account and does not offer finished tasks for acceptance.

No model or migration changes are required. Task creation does not create new categories; category administration remains separate.

## Verification — October 23, 2026

Integrated with the latest shared main at `64050d5` before this change. All 35 discovered tests passed: 14 existing list tests and 21 CRUD/integration tests. Django's system check reported no issues, and the migration check reported no changes.

Run from the repository folder in PowerShell:

```powershell
.\.venv\Scripts\python.exe manage.py test --verbosity 2
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
```

The test runner creates a separate in-memory database. The cases and assertions are in `tasks/tests.py` and `tasks/test_crud.py`.

| Test actions | Expected result | Actual result |
| --- | --- | --- |
| Visit or submit CRUD pages anonymously, as an employee, as an unapproved manager, or without a profile. | Login redirect or 403; no task changes. | PASS |
| Request another manager's or a nonexistent task for edit/delete, including POST. | 404; no disclosure or changes. | PASS |
| Send unsupported methods or submit without a CSRF token; then submit with a valid token. | Unsupported methods return 405, missing token returns 403, valid submission succeeds. | PASS |
| Open create/edit forms. | Only allowed fields appear; categories are optional; edit date is prefilled in ISO format. | PASS |
| Create with categories and forged creator/archive/completion fields; also create without categories. | Allowed values and categories persist; authenticated creator wins; protected fields retain defaults. | PASS |
| Submit blank/invalid values or a nonexistent category. | Visible errors and bound values; database unchanged. | PASS |
| Edit details/categories and attempt to change protected fields. | Details update; ownership/completion and assignment records remain unchanged. | PASS |
| Reduce capacity below two existing assignments, then submit capacity equal to two. | First submission is rejected; second succeeds. | PASS |
| GET delete confirmation, then POST an unclaimed task. | GET leaves it intact; POST deletes only the task and preserves categories/other tasks. | PASS |
| Delete tasks with active or completed assignments; add a claim after opening confirmation and submit again. | 409; task and assignments remain intact. | PASS |
| Navigate manager dashboard/list/action links and inspect employee navigation. | Manager actions are connected; employee pages do not expose manager controls. | PASS |
| Create as a manager, accept as an employee, edit as the manager, then read the employee's accepted list. | Created task is available; acceptance fills capacity; edits propagate; assigned task cannot be deleted. | PASS |
| Visit the dashboard anonymously/with invalid approval/profile, and test a finished but partially staffed task. | Access is denied appropriately; finished task is absent from availability. | PASS |
| Run the original ownership, pagination, escaping and list-method tests. | Existing list behavior remains correct. | PASS |

Browser checks also passed on an isolated local database: manager login, creation, persisted edit values, employee availability and acceptance, updated staffing/status, and blocked deletion after acceptance. The normal project database was not used for these checks.

Task edits/deletes and acceptance use transactions and lock the task row where the database supports row locking. SQLite does not provide row-level `select_for_update()` locking; these checks verify sequential behavior, not concurrent load guarantees. Deployment was not performed as part of this change.
