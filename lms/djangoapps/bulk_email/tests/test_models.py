
from django.test import TestCase

from bulk_email.models import CourseEmail, SEND_TO_STAFF
from student.tests.factories import UserFactory


class CourseEmailTest(TestCase):
    """Test the CourseEmail model."""

    def test_creation(self):
        course_id = 'abc/123/doremi'
        sender = UserFactory.create()
        to_option = SEND_TO_STAFF
        subject = "dummy subject"
        html_message = "<html>dummy message</html>"
        CourseEmail.create(course_id, sender, to_option, subject, html_message)

    def test_bad_to_option(self):
        course_id = 'abc/123/doremi'
        sender = UserFactory.create()
        to_option = "fake"
        subject = "dummy subject"
        html_message = "<html>dummy message</html>"
        with self.assertRaises(ValueError):
            CourseEmail.create(course_id, sender, to_option, subject, html_message)
