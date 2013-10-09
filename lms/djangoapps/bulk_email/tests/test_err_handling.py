"""
Unit tests for handling email sending errors
"""
from itertools import cycle
from mock import patch
from smtplib import SMTPDataError, SMTPServerDisconnected, SMTPConnectError

from django.test.utils import override_settings
from django.conf import settings
from django.core.management import call_command
from django.core.urlresolvers import reverse


from courseware.tests.tests import TEST_DATA_MONGO_MODULESTORE
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory
from student.tests.factories import UserFactory, AdminFactory, CourseEnrollmentFactory

from bulk_email.models import CourseEmail, SEND_TO_ALL
from bulk_email.tasks import perform_delegate_email_batches, send_course_email
from instructor_task.models import InstructorTask
from instructor_task.subtasks import create_subtask_status


class EmailTestException(Exception):
    """Mock exception for email testing."""
    pass


@override_settings(MODULESTORE=TEST_DATA_MONGO_MODULESTORE)
class TestEmailErrors(ModuleStoreTestCase):
    """
    Test that errors from sending email are handled properly.
    """

    def setUp(self):
        self.course = CourseFactory.create()
        self.instructor = AdminFactory.create()
        self.client.login(username=self.instructor.username, password="test")

        # load initial content (since we don't run migrations as part of tests):
        call_command("loaddata", "course_email_template.json")
        self.url = reverse('instructor_dashboard', kwargs={'course_id': self.course.id})

    def tearDown(self):
        patch.stopall()

    @patch('bulk_email.tasks.get_connection', autospec=True)
    @patch('bulk_email.tasks.send_course_email.retry')
    def test_data_err_retry(self, retry, get_conn):
        """
        Test that celery handles transient SMTPDataErrors by retrying.
        """
        get_conn.return_value.send_messages.side_effect = SMTPDataError(455, "Throttling: Sending rate exceeded")
        test_email = {
            'action': 'Send email',
            'to_option': 'myself',
            'subject': 'test subject for myself',
            'message': 'test message for myself'
        }
        self.client.post(self.url, test_email)

        # Test that we retry upon hitting a 4xx error
        self.assertTrue(retry.called)
        (_, kwargs) = retry.call_args
        exc = kwargs['exc']
        self.assertIsInstance(exc, SMTPDataError)

    @patch('bulk_email.tasks.get_connection', autospec=True)
    @patch('bulk_email.tasks.increment_subtask_status')
    @patch('bulk_email.tasks.send_course_email.retry')
    def test_data_err_fail(self, retry, result, get_conn):
        """
        Test that celery handles permanent SMTPDataErrors by failing and not retrying.
        """
        # have every fourth email fail due to blacklisting:
        get_conn.return_value.send_messages.side_effect = cycle([SMTPDataError(554, "Email address is blacklisted"),
                                                                 None, None, None])
        students = [UserFactory() for _ in xrange(settings.EMAILS_PER_TASK)]
        for student in students:
            CourseEnrollmentFactory.create(user=student, course_id=self.course.id)

        test_email = {
            'action': 'Send email',
            'to_option': 'all',
            'subject': 'test subject for all',
            'message': 'test message for all'
        }
        self.client.post(self.url, test_email)

        # We shouldn't retry when hitting a 5xx error
        self.assertFalse(retry.called)
        # Test that after the rejected email, the rest still successfully send
        ((_initial_results), kwargs) = result.call_args
        self.assertEquals(kwargs['skipped'], 0)
        expected_fails = int((settings.EMAILS_PER_TASK + 3) / 4.0)
        self.assertEquals(kwargs['failed'], expected_fails)
        self.assertEquals(kwargs['succeeded'], settings.EMAILS_PER_TASK - expected_fails)

    @patch('bulk_email.tasks.get_connection', autospec=True)
    @patch('bulk_email.tasks.send_course_email.retry')
    def test_disconn_err_retry(self, retry, get_conn):
        """
        Test that celery handles SMTPServerDisconnected by retrying.
        """
        get_conn.return_value.open.side_effect = SMTPServerDisconnected(425, "Disconnecting")
        test_email = {
            'action': 'Send email',
            'to_option': 'myself',
            'subject': 'test subject for myself',
            'message': 'test message for myself'
        }
        self.client.post(self.url, test_email)

        self.assertTrue(retry.called)
        (_, kwargs) = retry.call_args
        exc = kwargs['exc']
        self.assertIsInstance(exc, SMTPServerDisconnected)

    @patch('bulk_email.tasks.get_connection', autospec=True)
    @patch('bulk_email.tasks.send_course_email.retry')
    def test_conn_err_retry(self, retry, get_conn):
        """
        Test that celery handles SMTPConnectError by retrying.
        """
        get_conn.return_value.open.side_effect = SMTPConnectError(424, "Bad Connection")

        test_email = {
            'action': 'Send email',
            'to_option': 'myself',
            'subject': 'test subject for myself',
            'message': 'test message for myself'
        }
        self.client.post(self.url, test_email)

        self.assertTrue(retry.called)
        (_, kwargs) = retry.call_args
        exc = kwargs['exc']
        self.assertIsInstance(exc, SMTPConnectError)

    @patch('bulk_email.tasks.increment_subtask_status')
    @patch('bulk_email.tasks.log')
    def test_nonexistent_email(self, mock_log, result):
        """
        Tests retries when the email doesn't exist
        """
        # create an InstructorTask object to pass through
        course_id = self.course.id
        entry = InstructorTask.create(course_id, "task_type", "task_key", "task_input", self.instructor)
        task_input = {"email_id": -1}
        with self.assertRaises(CourseEmail.DoesNotExist):
            perform_delegate_email_batches(entry.id, course_id, task_input, "action_name")  # pylint: disable=E1101
        ((log_str, _, email_id), _) = mock_log.warning.call_args
        self.assertTrue(mock_log.warning.called)
        self.assertIn('Failed to get CourseEmail with id', log_str)
        self.assertEqual(email_id, -1)
        self.assertFalse(result.called)

    @patch('bulk_email.tasks.log')
    def test_nonexistent_course(self, mock_log):
        """
        Tests exception when the course in the email doesn't exist
        """
        course_id = "I/DONT/EXIST"
        email = CourseEmail(course_id=course_id)
        email.save()
        entry = InstructorTask.create(course_id, "task_type", "task_key", "task_input", self.instructor)
        task_input = {"email_id": email.id}  # pylint: disable=E1101
        with self.assertRaises(Exception):
            perform_delegate_email_batches(entry.id, course_id, task_input, "action_name")  # pylint: disable=E1101
        ((log_str, _, _), _) = mock_log.exception.call_args
        self.assertTrue(mock_log.exception.called)
        self.assertIn('get_course_by_id failed:', log_str)

    @patch('bulk_email.tasks.log')
    def test_nonexistent_to_option(self, mock_log):
        """
        Tests exception when the to_option in the email doesn't exist
        """
        email = CourseEmail(course_id=self.course.id, to_option="IDONTEXIST")
        email.save()
        entry = InstructorTask.create(self.course.id, "task_type", "task_key", "task_input", self.instructor)
        task_input = {"email_id": email.id}  # pylint: disable=E1101
        with self.assertRaises(Exception):
            perform_delegate_email_batches(entry.id, self.course.id, task_input, "action_name")  # pylint: disable=E1101
        ((log_str, opt_str), _) = mock_log.error.call_args
        self.assertTrue(mock_log.error.called)
        self.assertIn('Unexpected bulk email TO_OPTION found', log_str)
        self.assertEqual("IDONTEXIST", opt_str)

    def test_wrong_course_id_in_task(self):
        """
        Tests exception when the course_id in task is not the same as one explicitly passed in.
        """
        email = CourseEmail(course_id=self.course.id, to_option=SEND_TO_ALL)
        email.save()
        entry = InstructorTask.create("bogus_task_id", "task_type", "task_key", "task_input", self.instructor)
        task_input = {"email_id": email.id}  # pylint: disable=E1101
        with self.assertRaisesRegexp(ValueError, 'does not match task value'):
            perform_delegate_email_batches(entry.id, self.course.id, task_input, "action_name")  # pylint: disable=E1101

    def test_wrong_course_id_in_email(self):
        """
        Tests exception when the course_id in CourseEmail is not the same as one explicitly passed in.
        """
        email = CourseEmail(course_id="bogus_course_id", to_option=SEND_TO_ALL)
        email.save()
        entry = InstructorTask.create(self.course.id, "task_type", "task_key", "task_input", self.instructor)
        task_input = {"email_id": email.id}  # pylint: disable=E1101
        with self.assertRaisesRegexp(ValueError, 'does not match email value'):
            perform_delegate_email_batches(entry.id, self.course.id, task_input, "action_name")  # pylint: disable=E1101

    def test_send_email_undefined_email(self):
        # test at a lower level, to ensure that the course gets checked down below too.
        entry = InstructorTask.create(self.course.id, "task_type", "task_key", "task_input", self.instructor)
        entry_id = entry.id  # pylint: disable=E1101
        to_list = ['test@test.com']
        global_email_context = {'course_title': 'dummy course'}
        subtask_id = "subtask-id-value"
        subtask_status = create_subtask_status(subtask_id)
        bogus_email_id = 1001
        with self.assertRaises(CourseEmail.DoesNotExist):
            # we skip the call that updates subtask status, since we've not set up the InstructorTask
            # for the subtask, and it's not important to the test.
            with patch('bulk_email.tasks.update_subtask_status'):
                send_course_email(entry_id, bogus_email_id, to_list, global_email_context, subtask_status)
