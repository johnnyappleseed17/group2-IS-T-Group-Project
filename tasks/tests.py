from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape

from accounts.models import UserProfile

from .models import Category, Task, TaskAssignment


class MyCreatedTasksTests(TestCase):
    @classmethod
    def create_manager(cls, username):
        user = get_user_model().objects.create_user(username=username)
        UserProfile.objects.filter(user=user).update(role=UserProfile.Role.MANAGER)
        return user

    @classmethod
    def setUpTestData(cls):
        cls.manager = cls.create_manager("manager")
        cls.other_manager = cls.create_manager("other_manager")
        cls.employee = get_user_model().objects.create_user(username="employee")
        cls.due_date = timezone.localdate() + timedelta(days=7)
        cls.later_task = Task.objects.create(
            title="Prepare next month's schedule",
            description="Plan the upcoming work schedule.",
            due_date=cls.due_date + timedelta(days=7),
            created_by=cls.manager,
        )
        cls.earlier_task = Task.objects.create(
            title="Prepare weekly report",
            description="Summarize this week's completed work.",
            due_date=cls.due_date,
            employees_needed=2,
            created_by=cls.manager,
        )
        cls.other_task = Task.objects.create(
            title="Other manager's private task",
            description="This belongs to another manager.",
            due_date=cls.due_date,
            created_by=cls.other_manager,
        )

    def setUp(self):
        self.url = reverse("tasks:my_created_tasks")

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(self.url)
        self.assertRedirects(
            response,
            f"{reverse('login')}?next={self.url}",
            fetch_redirect_response=False,
        )

    def test_employee_is_denied(self):
        self.client.force_login(self.employee)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_unapproved_manager_is_denied(self):
        UserProfile.objects.filter(user=self.manager).update(is_approved=False)
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_user_without_profile_is_denied(self):
        UserProfile.objects.filter(user=self.manager).delete()
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_approved_manager_sees_own_tasks_in_due_date_order(self):
        self.assertFalse(self.manager.is_staff)
        self.assertFalse(self.manager.is_superuser)
        self.client.force_login(self.manager)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "tasks/my_created_tasks.html")
        self.assertQuerySetEqual(
            response.context["tasks"],
            [self.earlier_task.pk, self.later_task.pk],
            transform=lambda task: task.pk,
        )
        self.assertNotContains(response, escape(self.other_task.title))
        self.assertNotContains(response, self.other_task.description)

    def test_owner_query_parameter_cannot_reveal_other_managers_tasks(self):
        self.client.force_login(self.manager)
        response = self.client.get(self.url, {"created_by": self.other_manager.pk})
        self.assertContains(response, self.earlier_task.title)
        self.assertNotContains(response, escape(self.other_task.title))

    def test_empty_list_shows_a_message_without_other_users_tasks(self):
        new_manager = self.create_manager("new_manager")
        self.client.force_login(new_manager)
        response = self.client.get(self.url)
        self.assertContains(response, "You haven't created any tasks yet.")
        self.assertQuerySetEqual(response.context["tasks"], [])
        self.assertNotContains(response, escape(self.other_task.title))

    def test_task_details_categories_staffing_and_status_are_displayed(self):
        category = Category.objects.create(name="Reporting")
        self.earlier_task.categories.add(category)
        TaskAssignment.objects.create(task=self.earlier_task, assignee=self.employee)
        self.client.force_login(self.manager)
        response = self.client.get(self.url)
        self.assertContains(response, escape(self.earlier_task.description))
        self.assertContains(response, self.due_date.isoformat())
        self.assertContains(response, "Reporting")
        self.assertContains(response, "1 / 2")
        self.assertContains(response, "Claimed")
        self.assertContains(response, "Unclaimed")
        self.assertContains(response, "None")

    def test_task_content_is_html_escaped(self):
        unsafe_title = '<script>alert("task")</script>'
        self.earlier_task.title = unsafe_title
        self.earlier_task.save(update_fields=["title"])
        self.client.force_login(self.manager)
        response = self.client.get(self.url)
        self.assertContains(response, escape(unsafe_title))
        self.assertNotContains(response, unsafe_title)

    def test_task_list_rejects_post_requests(self):
        self.client.force_login(self.manager)
        self.assertEqual(self.client.post(self.url).status_code, 405)

    def test_manager_has_a_task_list_link_on_the_post_login_page(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse("base"))
        self.assertContains(response, f'href="{self.url}"')

    def test_employee_does_not_have_a_manager_task_list_link(self):
        self.client.force_login(self.employee)
        response = self.client.get(reverse("base"))
        self.assertNotContains(response, f'href="{self.url}"')

    def add_tasks_for_pagination(self):
        return Task.objects.bulk_create(
            [
                Task(
                    title=f"Additional task {number + 1}",
                    description="Work for the signed-in manager.",
                    due_date=self.due_date,
                    created_by=self.manager,
                )
                for number in range(12)
            ]
        )

    def test_pagination_keeps_ownership_order_counts_and_navigation(self):
        additional_tasks = self.add_tasks_for_pagination()
        self.client.force_login(self.manager)
        first_page = self.client.get(self.url)
        second_page = self.client.get(self.url, {"page": 2})

        self.assertEqual(first_page.context["page_obj"].paginator.count, 14)
        self.assertQuerySetEqual(
            first_page.context["tasks"],
            [self.earlier_task.pk] + [task.pk for task in additional_tasks[:9]],
            transform=lambda task: task.pk,
        )
        self.assertQuerySetEqual(
            second_page.context["tasks"],
            [task.pk for task in additional_tasks[9:]] + [self.later_task.pk],
            transform=lambda task: task.pk,
        )
        self.assertContains(first_page, "Showing 1 to 10 of 14 tasks.")
        self.assertContains(first_page, 'href="?page=2" rel="next"')
        self.assertNotContains(first_page, 'rel="prev"')
        self.assertContains(second_page, "Showing 11 to 14 of 14 tasks.")
        self.assertContains(second_page, 'href="?page=1" rel="prev"')
        self.assertNotContains(second_page, 'rel="next"')
        for response in (first_page, second_page):
            self.assertNotContains(response, escape(self.other_task.title))

    def test_invalid_page_values_fall_back_without_revealing_other_tasks(self):
        self.add_tasks_for_pagination()
        self.client.force_login(self.manager)
        for page_value, expected_page in (("invalid", 1), ("999", 2), ("0", 2)):
            with self.subTest(page=page_value):
                response = self.client.get(self.url, {"page": page_value})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context["page_obj"].number, expected_page)
                self.assertEqual(response.context["page_obj"].paginator.count, 14)
                self.assertNotContains(response, escape(self.other_task.title))
