# Manager task CRUD

Managers can create tasks from the dashboard or **Created Tasks**, then edit or archive their own tasks from the list. **Task History** shows their archived tasks and provides a **Restore task** button. Existing employee dashboards and acceptance links continue to use the same models and routes.

## Routes

| Page | URL | Django URL name |
| --- | --- | --- |
| Own created tasks | `/tasks/mine/` | `tasks:my_created_tasks` |
| Create | `/tasks/create/` | `tasks:task_create` |
| Edit | `/tasks/<task_id>/edit/` | `tasks:task_update` |
| Archive confirmation | `/tasks/<task_id>/archive/` | `tasks:task_archive` |
| Restore (POST only) | `/tasks/<task_id>/restore/` | `tasks:task_restore` |
| Task history / manager archives | `/tasks/history/` | `tasks:task_history` |

Create, edit and archive accept GET for the page and POST for submission. Viewing the archive confirmation never changes a task. Restore accepts POST only. Forms include CSRF protection. The old task-delete URL is removed; category deletion is unchanged.

## Behavior

- The account must have an approved manager profile. Staff/superuser status alone does not grant access.
- Managers can modify only tasks they created. Other managers' task IDs return 404.
- Editable fields are title, description, due date, number of employees needed and optional existing categories. The server sets the creator; ownership, archive and completion fields cannot be changed through these forms.
- The number needed must be at least one and cannot fall below the current assignment count. Editing preserves existing assignments.
- Any assignment, including a completed assignment, prevents archiving. The confirmation page explains this and links to editing. A blocked archive POST returns 409 and preserves the task and assignments. The assignment check is repeated on POST, so accepting the task after the confirmation page was opened still prevents archiving.
- Archiving saves `is_archived=True` and the current `archived_at` timestamp. It preserves the task record, categories and other fields. Archived tasks are excluded from Created Tasks, employee availability, accepted lists and calendar feeds. Direct acceptance is blocked, and the manager must restore a task before editing it.
- Managers see only their own archived tasks in Task History, ten per page with the newest archive first. Only the approved manager who created an archived task can open its detail page or restore it. Employee completed-task history keeps its existing behavior.
- Restoring clears `is_archived` and `archived_at`, preserving the original due date, priority, categories and completion fields. Normal availability rules apply again. Restore returns to Task History; create/edit/archive return to Created Tasks with a success message.
- Created Tasks shows ten tasks per page, ordered by priority, due date and ID.
- The shared layout displays messages. The dashboard requires an approved account and does not offer finished tasks for acceptance.

No model or migration changes are required. Task creation does not create new categories; category administration remains separate.

## Try the archive flow

1. Sign in as an approved manager and open **Created Tasks**.
2. Choose **Archive** on a task with no accepted assignments, then confirm.
3. Open **Task History**. The task should be there with its archive date.
4. Choose **Restore task**, then open **Created Tasks** again.
5. Try archiving a task that an employee has accepted. The page should explain why it cannot be archived.

The task's due date stays the same when it is restored. Employee Task History still shows completed assignments.

## Verification - November 11, 2026

Built on shared main `9f2e86d`. All 117 tests passed, including 13 new archive tests and updated CRUD/history checks. Django's system check reported no issues, `makemigrations --check --dry-run` reported no changes, and `git diff --check` passed. Tests used Django's separate test database.

Verified archive/restore data preservation, approved-manager ownership, safe confirmation GETs, CSRF protection, blocked assigned tasks (including claims added after confirmation), archive pagination, active-list/calendar filtering, archived detail/edit restrictions, and restoring a task before employee acceptance. The old task-delete URL returns 404. Existing employee history tests still pass.

No deployment or browser-based verification was performed for this change. The existing SQLite concurrency limitation described below still applies.

## Verification - October 23, 2026 (historical)

The following results describe the original CRUD release. Sprint 2 replaces the task deletion behavior below with archiving.

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
