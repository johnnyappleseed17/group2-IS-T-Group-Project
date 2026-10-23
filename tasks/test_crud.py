from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape

from accounts.models import UserProfile

from .models import Category, Task, TaskAssignment


class TaskCrudTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.manager = users.create_user(username="crud_manager")
        cls.other_manager = users.create_user(username="crud_other_manager")
        cls.unapproved_manager = users.create_user(username="crud_pending_manager")
        for manager in (cls.manager, cls.other_manager, cls.unapproved_manager):
            UserProfile.objects.filter(user=manager).update(role=UserProfile.Role.MANAGER)
        UserProfile.objects.filter(user=cls.unapproved_manager).update(is_approved=False)
        cls.employee = users.create_user(username="crud_employee")
        cls.other_employee = users.create_user(username="crud_other_employee")
        cls.no_profile = users.create_user(username="crud_no_profile")
        UserProfile.objects.filter(user=cls.no_profile).delete()
        cls.category = Category.objects.create(name="Inventory")
        cls.other_category = Category.objects.create(name="Reporting")
        cls.due_date = timezone.localdate() + timedelta(days=7)
        cls.task = Task.objects.create(
            title="Count warehouse stock",
            description="Count the stock in aisle three.",
            due_date=cls.due_date,
            employees_needed=2,
            created_by=cls.manager,
        )
        cls.task.categories.add(cls.category)
        cls.other_task = Task.objects.create(
            title="Other manager's confidential task",
            description="Only its creator can change this task.",
            due_date=cls.due_date,
            created_by=cls.other_manager,
        )

    def setUp(self):
        self.client.force_login(self.manager)
        self.create_url = reverse("tasks:task_create")
        self.list_url = reverse("tasks:my_created_tasks")
        self.edit_url = reverse("tasks:task_update", args=[self.task.pk])
        self.delete_url = reverse("tasks:task_delete", args=[self.task.pk])

    def task_data(self, **changes):
        data = {
            "title": "Prepare the monthly report",
            "description": "Review all department totals.",
            "due_date": self.due_date.isoformat(),
            "employees_needed": "2",
            "categories": [str(self.category.pk), str(self.other_category.pk)],
        }
        data.update(changes)
        return data

    def assert_success_redirect(self, response):
        self.assertRedirects(response, self.list_url, fetch_redirect_response=False)
        self.assertTrue(
            any(message.level == messages.SUCCESS for message in get_messages(response.wsgi_request)),
            "A successful change should provide a success message.",
        )

    def test_anonymous_forms_and_mutations_require_login(self):
        self.client.logout()
        original_count = Task.objects.count()
        for url in (self.create_url, self.edit_url, self.delete_url):
            for method in ("get", "post"):
                with self.subTest(url=url, method=method):
                    data = self.task_data() if method == "post" else {}
                    response = getattr(self.client, method)(url, data)
                    self.assertRedirects(
                        response,
                        f"{reverse('login')}?next={url}",
                        fetch_redirect_response=False,
                    )
        self.assertEqual(Task.objects.count(), original_count)
        self.task.refresh_from_db()
        self.assertEqual(self.task.title, "Count warehouse stock")

    def test_employee_unapproved_manager_and_missing_profile_cannot_use_crud(self):
        original_count = Task.objects.count()
        for user in (self.employee, self.unapproved_manager, self.no_profile):
            self.client.force_login(user)
            for url in (self.create_url, self.edit_url, self.delete_url):
                for method in ("get", "post"):
                    with self.subTest(user=user.username, url=url, method=method):
                        response = getattr(self.client, method)(url, self.task_data())
                        self.assertEqual(response.status_code, 403)
        self.assertEqual(Task.objects.count(), original_count)
        self.task.refresh_from_db()
        self.assertEqual(self.task.title, "Count warehouse stock")

    def test_other_managers_and_missing_tasks_return_404_without_changes(self):
        original_count = Task.objects.count()
        for task_id in (self.other_task.pk, self.other_task.pk + 1000):
            for name in ("tasks:task_update", "tasks:task_delete"):
                url = reverse(name, args=[task_id])
                for method in ("get", "post"):
                    with self.subTest(task_id=task_id, name=name, method=method):
                        response = getattr(self.client, method)(url, self.task_data())
                        self.assertNotContains(response, escape(self.other_task.title), status_code=404)
        self.assertEqual(Task.objects.count(), original_count)
        self.other_task.refresh_from_db()
        self.assertEqual(self.other_task.title, "Other manager's confidential task")

    def test_crud_rejects_unsupported_http_methods(self):
        for url in (self.create_url, self.edit_url, self.delete_url):
            for method in ("put", "patch", "delete"):
                with self.subTest(url=url, method=method):
                    response = getattr(self.client, method)(url)
                    self.assertEqual(response.status_code, 405)
        self.assertTrue(Task.objects.filter(pk=self.task.pk).exists())

    def test_forms_expose_only_editable_fields_and_prefill_an_iso_date(self):
        editable_fields = {"title", "description", "due_date", "employees_needed", "categories"}
        for url in (self.create_url, self.edit_url):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                form = response.context["form"]
                self.assertEqual(set(form.fields), editable_fields)
                self.assertFalse(form.fields["categories"].required)
                self.assertEqual(form.fields["due_date"].widget.input_type, "date")
        self.assertContains(response, f'value="{self.due_date.isoformat()}"')
        self.assertEqual(set(response.context["form"]["categories"].value()), {self.category.pk})

    def test_create_saves_fields_categories_and_uses_the_authenticated_creator(self):
        self.assertFalse(self.manager.is_staff)
        self.assertFalse(self.manager.is_superuser)
        response = self.client.post(
            self.create_url,
            self.task_data(
                created_by=self.other_manager.pk,
                is_archived="on",
                archived_at=timezone.now().isoformat(),
                completed_at=timezone.now().isoformat(),
                completed_by=self.other_manager.pk,
            ),
        )
        self.assert_success_redirect(response)
        task = Task.objects.get(title="Prepare the monthly report")
        self.assertEqual(task.description, "Review all department totals.")
        self.assertEqual(task.due_date, self.due_date)
        self.assertEqual(task.employees_needed, 2)
        self.assertEqual(task.created_by_id, self.manager.pk)
        self.assertSetEqual(set(task.categories.all()), {self.category, self.other_category})
        self.assertFalse(task.is_archived)
        self.assertIsNone(task.archived_at)
        self.assertIsNone(task.completed_at)
        self.assertIsNone(task.completed_by_id)

    def test_create_accepts_no_categories(self):
        response = self.client.post(self.create_url, self.task_data(categories=[]))
        self.assert_success_redirect(response)
        self.assertFalse(Task.objects.get(title="Prepare the monthly report").categories.exists())

    def test_invalid_create_keeps_bound_values_errors_and_database_unchanged(self):
        original_count = Task.objects.count()
        response = self.client.post(
            self.create_url,
            self.task_data(title="", due_date="invalid-date", employees_needed="0"),
        )
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertTrue(form.is_bound)
        self.assertTrue({"title", "due_date", "employees_needed"}.issubset(form.errors))
        for field in ("title", "due_date", "employees_needed"):
            self.assertContains(response, escape(form.errors[field][0]))
        self.assertEqual(form["description"].value(), "Review all department totals.")
        self.assertContains(response, "Review all department totals.")
        self.assertEqual(Task.objects.count(), original_count)

    def test_unknown_category_is_rejected_without_creating_a_task(self):
        original_count = Task.objects.count()
        response = self.client.post(
            self.create_url, self.task_data(categories=[str(self.other_category.pk + 1000)])
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("categories", response.context["form"].errors)
        self.assertEqual(Task.objects.count(), original_count)

    def test_edit_updates_allowed_details_without_reassigning_or_completing_the_task(self):
        assignment = TaskAssignment.objects.create(task=self.task, assignee=self.employee)
        new_date = self.due_date + timedelta(days=2)
        response = self.client.post(
            self.edit_url,
            self.task_data(
                due_date=new_date.isoformat(),
                employees_needed="1",
                categories=[str(self.other_category.pk)],
                created_by=self.other_manager.pk,
                is_archived="on",
                completed_at=timezone.now().isoformat(),
                completed_by=self.other_manager.pk,
            ),
        )
        self.assert_success_redirect(response)
        self.task.refresh_from_db()
        self.assertEqual(self.task.title, "Prepare the monthly report")
        self.assertEqual(self.task.description, "Review all department totals.")
        self.assertEqual(self.task.due_date, new_date)
        self.assertEqual(self.task.employees_needed, 1)
        self.assertEqual(self.task.created_by_id, self.manager.pk)
        self.assertFalse(self.task.is_archived)
        self.assertIsNone(self.task.completed_at)
        self.assertIsNone(self.task.completed_by_id)
        self.assertSetEqual(set(self.task.categories.all()), {self.other_category})
        self.assertTrue(TaskAssignment.objects.filter(pk=assignment.pk, task=self.task).exists())

    def test_invalid_edit_preserves_saved_fields_and_categories(self):
        response = self.client.post(
            self.edit_url,
            self.task_data(due_date="invalid-date", categories=[str(self.other_category.pk)]),
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].is_bound)
        self.assertIn("due_date", response.context["form"].errors)
        self.assertContains(response, escape(response.context["form"].errors["due_date"][0]))
        self.assertContains(response, "Prepare the monthly report")
        self.task.refresh_from_db()
        self.assertEqual(self.task.title, "Count warehouse stock")
        self.assertEqual(self.task.description, "Count the stock in aisle three.")
        self.assertEqual(self.task.due_date, self.due_date)
        self.assertEqual(self.task.employees_needed, 2)
        self.assertSetEqual(set(self.task.categories.all()), {self.category})

    def test_edit_cannot_reduce_capacity_below_existing_assignments(self):
        TaskAssignment.objects.create(task=self.task, assignee=self.employee)
        TaskAssignment.objects.create(task=self.task, assignee=self.other_employee)
        response = self.client.post(self.edit_url, self.task_data(employees_needed="1"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("employees_needed", response.context["form"].errors)
        self.assertContains(response, escape(response.context["form"].errors["employees_needed"][0]))
        self.task.refresh_from_db()
        self.assertEqual(self.task.employees_needed, 2)
        self.assertEqual(self.task.title, "Count warehouse stock")
        self.assertEqual(self.task.assignments.count(), 2)
        self.assert_success_redirect(
            self.client.post(self.edit_url, self.task_data(employees_needed="2"))
        )

    def test_delete_get_is_a_confirmation_and_does_not_delete(self):
        response = self.client.get(self.delete_url)
        self.assertContains(response, self.task.title)
        self.assertContains(response, 'method="post"')
        self.assertTrue(Task.objects.filter(pk=self.task.pk).exists())

    def test_delete_post_removes_only_the_unclaimed_task_and_reports_success(self):
        response = self.client.post(self.delete_url)
        self.assert_success_redirect(response)
        self.assertFalse(Task.objects.filter(pk=self.task.pk).exists())
        self.assertTrue(Task.objects.filter(pk=self.other_task.pk).exists())
        self.assertTrue(Category.objects.filter(pk=self.category.pk).exists())

    def test_even_completed_assignments_prevent_hard_deletion(self):
        assignment = TaskAssignment.objects.create(
            task=self.task, assignee=self.employee, completed_at=timezone.now()
        )
        response = self.client.post(self.delete_url)
        self.assertContains(response, f'href="{self.edit_url}"', status_code=409)
        self.assertTrue(Task.objects.filter(pk=self.task.pk).exists())
        self.assertTrue(TaskAssignment.objects.filter(pk=assignment.pk).exists())
        self.assertRegex(response.content.decode().lower(), r"(assign|claim|accept)")

    def test_delete_rechecks_claims_added_after_the_confirmation_page(self):
        self.assertEqual(self.client.get(self.delete_url).status_code, 200)
        assignment = TaskAssignment.objects.create(task=self.task, assignee=self.employee)
        response = self.client.post(self.delete_url)
        self.assertEqual(response.status_code, 409)
        self.assertTrue(Task.objects.filter(pk=self.task.pk).exists())
        self.assertTrue(TaskAssignment.objects.filter(pk=assignment.pk).exists())

    def test_crud_posts_require_csrf_and_valid_token_allows_submission(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.manager)
        original_count = Task.objects.count()
        for url in (self.create_url, self.edit_url, self.delete_url):
            with self.subTest(url=url):
                self.assertEqual(client.post(url, self.task_data()).status_code, 403)
        self.assertEqual(Task.objects.count(), original_count)
        self.task.refresh_from_db()
        self.assertEqual(self.task.title, "Count warehouse stock")
        form_page = client.get(self.create_url)
        self.assertContains(form_page, 'name="csrfmiddlewaretoken"')
        response = client.post(
            self.create_url,
            self.task_data(),
            HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value,
        )
        self.assert_success_redirect(response)

    def test_manager_navigation_connects_dashboard_list_and_task_actions(self):
        dashboard = self.client.get(reverse("dashboard"))
        self.assertContains(dashboard, f'href="{self.list_url}"')
        self.assertContains(dashboard, f'href="{self.create_url}"')
        response = self.client.get(self.list_url)
        for url in (self.create_url, self.edit_url, self.delete_url):
            self.assertContains(response, f'href="{url}"')
        self.assertNotContains(
            response, f'href="{reverse("tasks:task_update", args=[self.other_task.pk])}"'
        )
        self.client.force_login(self.employee)
        employee_dashboard = self.client.get(reverse("dashboard"))
        self.assertNotContains(employee_dashboard, f'href="{self.create_url}"')
        self.assertNotContains(employee_dashboard, f'href="{self.list_url}"')

    def test_created_and_edited_tasks_work_with_employee_claiming_and_accepted_list(self):
        self.assert_success_redirect(
            self.client.post(self.create_url, self.task_data(employees_needed="1"))
        )
        task = Task.objects.get(title="Prepare the monthly report")
        self.client.force_login(self.employee)
        available = self.client.get(reverse("dashboard"))
        self.assertContains(available, task.title)
        accept_url = reverse("tasks:accept_task", args=[task.pk])
        self.assertContains(available, f'action="{accept_url}"')
        response = self.client.post(accept_url)
        self.assertRedirects(response, reverse("tasks:my_accepted_tasks"))
        self.assertTrue(TaskAssignment.objects.filter(task=task, assignee=self.employee).exists())
        self.client.force_login(self.other_employee)
        self.assertNotContains(self.client.get(reverse("dashboard")), task.title)
        self.client.force_login(self.manager)
        edited_date = self.due_date + timedelta(days=3)
        self.assert_success_redirect(
            self.client.post(
                reverse("tasks:task_update", args=[task.pk]),
                self.task_data(
                    title="Review corrected department totals",
                    description="Use the revised figures before submitting.",
                    due_date=edited_date.isoformat(),
                    employees_needed="1",
                    categories=[str(self.other_category.pk)],
                ),
            )
        )
        self.client.force_login(self.employee)
        accepted = self.client.get(reverse("tasks:my_accepted_tasks"))
        for text in (
            "Review corrected department totals",
            "Use the revised figures before submitting.",
            edited_date.isoformat(),
            self.other_category.name,
        ):
            self.assertContains(accepted, text)
        self.assertNotContains(accepted, "Prepare the monthly report")
        self.client.force_login(self.manager)
        self.assertEqual(
            self.client.post(reverse("tasks:task_delete", args=[task.pk])).status_code, 409
        )

    def test_dashboard_requires_login_and_an_approved_known_profile(self):
        url = reverse("dashboard")
        self.client.logout()
        self.assertRedirects(
            self.client.get(url),
            f"{reverse('login')}?next={url}",
            fetch_redirect_response=False,
        )
        UserProfile.objects.filter(user=self.other_employee).update(role="unknown")
        for user in (self.unapproved_manager, self.no_profile, self.other_employee):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_employee_availability_excludes_finished_tasks_with_unfilled_capacity(self):
        TaskAssignment.objects.create(
            task=self.task, assignee=self.other_employee, completed_at=timezone.now()
        )
        self.assertFalse(self.task.is_full)
        self.assertTrue(self.task.is_finished)
        self.client.force_login(self.employee)
        response = self.client.get(reverse("dashboard"))
        self.assertNotContains(response, self.task.title)
        self.assertContains(response, escape(self.other_task.title))
