"""
Unit tests for email feature flag in new instructor dashboard. 
Additionally tests that bulk email is always disabled for 
non-Mongo backed courses, regardless of email feature flag.
"""

from django.test.utils import override_settings
from django.conf import settings
from django.core.urlresolvers import reverse

from courseware.tests.tests import TEST_DATA_MONGO_MODULESTORE
from student.tests.factories import AdminFactory, UserFactory, CourseEnrollmentFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory
from xmodule.modulestore import XML_MODULESTORE_TYPE

from mock import patch

@override_settings(MODULESTORE=TEST_DATA_MONGO_MODULESTORE)
class TestNewInstructorDashboardEmailView(ModuleStoreTestCase):
    """
    Check for email view on the new instructor dashboard
    """
    def setUp(self):
        self.course = CourseFactory.create()

        # Create instructor account
        instructor = AdminFactory.create()
        self.client.login(username=instructor.username, password="test")

        # URL for instructor dash
        self.url = reverse('instructor_dashboard_2', kwargs={'course_id': self.course.id})
        # URL for email view
        self.email_link = '<a href="" data-section="send_email">Email</a>'

    def tearDown(self):
        """
        Undo all patches.
        """
        patch.stopall()

    # In order for bulk email to work, we must have both the ENABLE_INSTRUCTOR_EMAIL_FLAG
    # set to True and for the course to be Mongo-backed.
    # The flag is enabled and the course is Mongo-backed (should work)
    @patch.dict(settings.MITX_FEATURES, {'ENABLE_INSTRUCTOR_EMAIL': True})
    def test_email_flag_true_mongo_true(self):
        # Assert that the URL for the email view is in the response
        response = self.client.get(self.url)
        self.assertTrue(self.email_link in response.content)

        send_to_label = '<label for="id_to">Send to:</label>'
        self.assertTrue(send_to_label in response.content)
        self.assertEqual(response.status_code,200)

    # The course is Mongo-backed but the flag is disabled (should not work)
    @patch.dict(settings.MITX_FEATURES, {'ENABLE_INSTRUCTOR_EMAIL': False})
    def test_email_flag_false_mongo_true(self):
        # Assert that the URL for the email view is not in the response
        response = self.client.get(self.url)
        self.assertFalse(self.email_link in response.content)

    # The flag is enabled but the course is not Mongo-backed (should not work)
    @patch.dict(settings.MITX_FEATURES,{'ENABLE_INSTRUCTOR_EMAIL': True})
    def test_email_flag_true_mongo_false(self):

	# Since the course facotry uses a MongoModuleStore backing, we use this patch to change the
	# the type to XML-backed.  Thus we can check to ensure the email tab won't display on
	# XML-backed courses.
        with patch('xmodule.modulestore.mongo.base.MongoModuleStore.get_modulestore_type') as mock_modulestore:
            mock_modulestore.return_value = XML_MODULESTORE_TYPE

            response = self.client.get(self.url)
            self.assertFalse(self.email_link in response.content)

    # The flag is disabled and the course is not Mongo-backed (should not work)
    @patch.dict(settings.MITX_FEATURES, {'ENABLE_INSTRUCTOR_EMAIL': False})
    def test_email_flag_false_mongo_false(self):

	# Same method from test_email_flag_true_mongo_false
        with patch('xmodule.modulestore.mongo.base.MongoModuleStore.get_modulestore_type') as mock_modulestore:
            mock_modulestore.return_value = XML_MODULESTORE_TYPE

            # Assert that the URL for the email view is not in the response
            response = self.client.get(self.url)
            self.assertFalse(self.email_link in response.content)
