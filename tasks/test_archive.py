from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.utils.html import escape

from accounts.models import UserProfile

from .models import Category, Task, TaskAssignment


class TaskArchiveTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.manager = users.create_user(username="archive_manager")
        cls.other_manager = users.create_user(username="archive_other_manager")
        cls.pending_manager = users.create_user(username="archive_pending_manager")
        for user in (cls.manager, cls.other_manager, cls.pending_manager):
            UserProfile.objects.filter(user=user).update(role=UserProfile.Role.MANAGER)
        UserProfile.objects.filter(user=cls.pending_manager).update(is_approved=False)
        cls.employee = users.create_user(username="archive_employee")
        cls.pending_employee = users.create_user(username="archive_pending_employee")
        UserProfile.objects.filter(user=cls.pending_employee).update(is_approved=False)
        cls.no_profile = users.create_user(username="archive_no_profile")
        UserProfile.objects.filter(user=cls.no_profile).delete()
        cls.category = Category.objects.create(name="Archive testing")
        cls.due = timezone.localdate() + timedelta(days=7)
        cls.task = Task.objects.create(
            title="Keep this task's records",
            description="The original task description.",
            due_date=cls.due,
            employees_needed=2,
            is_priority=True,
            created_by=cls.manager,
        )
        cls.task.categories.add(cls.category)
        cls.archived = Task.objects.create(
            title="Previously archived task",
            description="Restore this existing record.",
            due_date=cls.due,
            created_by=cls.manager,
            is_archived=True,
            archived_at=timezone.now() - timedelta(days=1),
        )
        cls.archived.categories.add(cls.category)
        cls.other_archived = Task.objects.create(
            title="Other manager's private archive",
            description="Not visible to the first manager.",
            due_date=cls.due,
            created_by=cls.other_manager,
            is_archived=True,
            archived_at=timezone.now(),
        )

    def setUp(self):
        self.client.force_login(self.manager)
        self.archive_url = reverse("tasks:task_archive", args=[self.task.pk])
        self.restore_url = reverse("tasks:task_restore", args=[self.archived.pk])
        self.history_url = reverse("tasks:task_history")
        self.list_url = reverse("tasks:my_created_tasks")

    def test_archive_preserves_all_task_fields_and_categories(self):
        # Even existing completion metadata must survive; archive is not deletion.
        Task.objects.filter(pk=self.task.pk).update(
            completed_at=timezone.now(), completed_by=self.manager
        )
        before = Task.objects.values().get(pk=self.task.pk)
        before_count = Task.objects.count()
        earliest = timezone.now()
        response = self.client.post(
            self.archive_url,
            {"title": "Tampered title", "created_by": self.other_manager.pk},
        )
        self.assertRedirects(response, self.list_url)
        after = Task.objects.values().get(pk=self.task.pk)
        self.assertTrue(after.pop("is_archived"))
        self.assertGreaterEqual(after.pop("archived_at"), earliest)
        before.pop("is_archived")
        before.pop("archived_at")
        self.assertEqual(after, before)
        self.assertEqual(Task.objects.count(), before_count)
        self.assertSetEqual(set(self.task.categories.all()), {self.category})

    def test_assigned_task_confirmation_explains_block_without_changing_records(self):
        assignment = TaskAssignment.objects.create(task=self.task, assignee=self.employee)
        for method, expected_status in (("get", 200), ("post", 409)):
            with self.subTest(method=method):
                response = getattr(self.client, method)(self.archive_url)
                self.assertEqual(response.status_code, expected_status)
                self.assertRegex(response.content.decode().lower(), r"(assign|claim|accept)")
                self.task.refresh_from_db()
                self.assertFalse(self.task.is_archived)
                self.assertIsNone(self.task.archived_at)
                self.assertTrue(TaskAssignment.objects.filter(pk=assignment.pk).exists())

    def test_restore_is_post_only_and_keeps_the_same_record(self):
        before = Task.objects.values().get(pk=self.archived.pk)
        for method in ("get", "head", "put", "patch", "delete"):
            with self.subTest(method=method):
                self.assertEqual(getattr(self.client, method)(self.restore_url).status_code, 405)
                self.assertEqual(Task.objects.values().get(pk=self.archived.pk), before)
        response = self.client.post(self.restore_url)
        self.assertRedirects(response, self.history_url)
        after = Task.objects.values().get(pk=self.archived.pk)
        self.assertFalse(after.pop("is_archived"))
        self.assertIsNone(after.pop("archived_at"))
        before.pop("is_archived")
        before.pop("archived_at")
        self.assertEqual(after, before)
        self.assertSetEqual(set(self.archived.categories.all()), {self.category})

    def test_restore_requires_login_approval_manager_role_and_ownership(self):
        self.client.logout()
        self.assertRedirects(
            self.client.post(self.restore_url),
            f"{reverse('login')}?next={self.restore_url}",
            fetch_redirect_response=False,
        )
        for user, status in (
            (self.employee, 403),
            (self.pending_employee, 403),
            (self.pending_manager, 403),
            (self.no_profile, 403),
            (self.other_manager, 404),
        ):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                self.assertEqual(self.client.post(self.restore_url).status_code, status)
                self.archived.refresh_from_db()
                self.assertTrue(self.archived.is_archived)
                self.assertIsNotNone(self.archived.archived_at)

    def test_archive_and_restore_reject_stale_or_missing_targets(self):
        for method in ("get", "post"):
            url = reverse("tasks:task_archive", args=[self.archived.pk])
            self.assertEqual(getattr(self.client, method)(url).status_code, 404)
        self.assertEqual(
            self.client.post(reverse("tasks:task_restore", args=[self.task.pk])).status_code,
            404,
        )
        for name in ("tasks:task_archive", "tasks:task_restore"):
            url = reverse(name, args=[self.other_archived.pk + 1000])
            self.assertEqual(self.client.post(url).status_code, 404)

    def test_archive_and_restore_posts_require_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.manager)
        self.assertEqual(client.post(self.archive_url).status_code, 403)
        self.assertEqual(client.post(self.restore_url).status_code, 403)
        self.task.refresh_from_db()
        self.archived.refresh_from_db()
        self.assertFalse(self.task.is_archived)
        self.assertTrue(self.archived.is_archived)
        client.get(self.archive_url)
        token = client.cookies["csrftoken"].value
        self.assertRedirects(
            client.post(self.archive_url, HTTP_X_CSRFTOKEN=token), self.list_url
        )
        self.assertRedirects(
            client.post(self.restore_url, HTTP_X_CSRFTOKEN=token), self.history_url
        )

    def test_legacy_delete_route_cannot_remove_a_task(self):
        with self.assertRaises(NoReverseMatch):
            reverse("tasks:task_delete", args=[self.task.pk])
        for method in ("get", "post", "delete"):
            self.assertEqual(
                getattr(self.client, method)(f"/tasks/{self.task.pk}/delete/").status_code,
                404,
            )
        self.assertTrue(Task.objects.filter(pk=self.task.pk).exists())

    def test_archived_task_cannot_be_edited_and_detail_is_owner_only(self):
        edit_url = reverse("tasks:task_update", args=[self.archived.pk])
        for method in ("get", "post"):
            self.assertEqual(getattr(self.client, method)(edit_url).status_code, 404)
        detail_url = reverse("tasks:task_detail", args=[self.archived.pk])
        self.assertContains(self.client.get(detail_url), escape(self.archived.title))
        for user in (self.employee, self.other_manager, self.pending_manager, self.no_profile):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                self.assertEqual(self.client.get(detail_url).status_code, 404)
        Task.objects.filter(pk=self.archived.pk).update(created_by=self.pending_manager)
        self.client.force_login(self.pending_manager)
        self.assertEqual(self.client.get(detail_url).status_code, 404)
        self.client.force_login(self.employee)
        self.assertContains(
            self.client.get(reverse("tasks:task_detail", args=[self.task.pk])),
            escape(self.task.title),
        )

    def test_manager_history_has_only_own_archives_and_restore_actions(self):
        response = self.client.get(self.history_url)
        self.assertTemplateUsed(response, "tasks/archived_tasks.html")
        self.assertEqual(list(response.context["tasks"]), [self.archived])
        self.assertContains(response, f'action="{self.restore_url}"')
        self.assertContains(
            response, f'href="{reverse("tasks:task_detail", args=[self.archived.pk])}"'
        )
        self.assertNotContains(response, escape(self.other_archived.title))
        self.assertNotContains(response, escape(self.task.title))
        self.assertNotContains(self.client.get(self.list_url), escape(self.archived.title))
        self.assertEqual(self.client.post(self.history_url).status_code, 405)

    def test_history_requires_approved_profile(self):
        for user in (self.pending_manager, self.pending_employee, self.no_profile):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                self.assertEqual(self.client.get(self.history_url).status_code, 403)

    def test_manager_history_paginates_newest_archives_without_leaking_owners(self):
        now = timezone.now()
        recent = Task.objects.bulk_create(
            [
                Task(
                    title=f"Archived task {number}",
                    description="Saved work.",
                    due_date=self.due,
                    created_by=self.manager,
                    is_archived=True,
                    archived_at=now + timedelta(minutes=number),
                )
                for number in range(12)
            ]
        )
        expected = list(reversed(recent)) + [self.archived]
        for page, expected_tasks in ((1, expected[:10]), (2, expected[10:])):
            response = self.client.get(self.history_url, {"page": page})
            self.assertEqual(response.context["page_obj"].paginator.count, 13)
            self.assertEqual(list(response.context["tasks"]), expected_tasks)
            self.assertNotContains(response, escape(self.other_archived.title))
        for value, expected_page in (("invalid", 1), ("999", 2), ("0", 2)):
            response = self.client.get(self.history_url, {"page": value})
            self.assertEqual(response.context["page_obj"].number, expected_page)
            self.assertEqual(response.context["page_obj"].paginator.count, 13)

    def test_archived_assignments_are_hidden_from_active_lists_and_both_calendars(self):
        # Existing archived records may have assignments even though new archives cannot.
        TaskAssignment.objects.create(task=self.archived, assignee=self.employee)
        TaskAssignment.objects.create(task=self.task, assignee=self.employee)
        for user in (self.manager, self.employee):
            self.client.force_login(user)
            events = self.client.get(reverse("calendar_events")).json()
            self.assertEqual([event["id"] for event in events], [self.task.pk])
        response = self.client.get(reverse("tasks:my_accepted_tasks"))
        self.assertContains(response, escape(self.task.title))
        self.assertNotContains(response, escape(self.archived.title))
        self.assertNotContains(self.client.get(reverse("dashboard")), escape(self.archived.title))

    def test_archive_restore_and_employee_acceptance_work_together(self):
        self.assertRedirects(self.client.post(self.archive_url), self.list_url)
        self.assertNotContains(self.client.get(self.list_url), escape(self.task.title))
        self.assertContains(self.client.get(self.history_url), escape(self.task.title))
        self.client.force_login(self.employee)
        self.assertNotContains(self.client.get(reverse("dashboard")), escape(self.task.title))
        accept_url = reverse("tasks:accept_task", args=[self.task.pk])
        self.client.post(accept_url)
        self.assertFalse(self.task.assignments.exists())
        self.client.force_login(self.manager)
        self.assertRedirects(
            self.client.post(reverse("tasks:task_restore", args=[self.task.pk])),
            self.history_url,
        )
        self.assertContains(self.client.get(self.list_url), escape(self.task.title))
        self.assertNotContains(self.client.get(self.history_url), escape(self.task.title))
        self.client.force_login(self.employee)
        self.assertContains(self.client.get(reverse("dashboard")), escape(self.task.title))
        self.assertRedirects(self.client.post(accept_url), reverse("tasks:my_accepted_tasks"))
        self.assertTrue(
            TaskAssignment.objects.filter(task=self.task, assignee=self.employee).exists()
        )
