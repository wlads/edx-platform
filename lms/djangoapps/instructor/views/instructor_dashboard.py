"""
Instructor Dashboard Views
"""

from django.utils.translation import ugettext as _
from django_future.csrf import ensure_csrf_cookie
from django.views.decorators.cache import cache_control
from mitxmako.shortcuts import render_to_response
from django.core.urlresolvers import reverse
from django.utils.html import escape
from django.http import Http404
from django.conf import settings

from xmodule_modifiers import wrap_xmodule
from xmodule.html_module import HtmlDescriptor
from xblock.field_data import DictFieldData
from xblock.fields import ScopeIds
from courseware.access import has_access
from courseware.courses import get_course_by_id
from django_comment_client.utils import has_forum_access
from django_comment_common.models import FORUM_ROLE_ADMINISTRATOR
from xmodule.modulestore.django import modulestore
from student.models import CourseEnrollment

@ensure_csrf_cookie
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
def instructor_dashboard_2(request, course_id):
    """ Display the instructor dashboard for a course. """

    course = get_course_by_id(course_id, depth=None)

    access = {
        'admin': request.user.is_staff,
        'instructor': has_access(request.user, course, 'instructor'),
        'staff': has_access(request.user, course, 'staff'),
        'forum_admin': has_forum_access(
            request.user, course_id, FORUM_ROLE_ADMINISTRATOR
        ),
    }

    if not access['staff']:
        raise Http404()

    sections = [
        _section_course_info(course_id, access),
        _section_membership(course_id, access),
        _section_student_admin(course_id, access),
        _section_data_download(course_id),
        _section_send_email(course_id, access,course),
        _section_analytics(course_id)
    ]

    enrollment_count = sections[0]['enrollment_count']

    disable_buttons = False
    max_enrollment_for_buttons = settings.MITX_FEATURES.get("MAX_ENROLLMENT_INSTR_BUTTONS")
    if max_enrollment_for_buttons is not None:
        disable_buttons = enrollment_count > max_enrollment_for_buttons


    context = {
        'course': course,
        'old_dashboard_url': reverse('instructor_dashboard', kwargs={'course_id': course_id}),
        'sections': sections,
        'disable_buttons': disable_buttons,
    }

    return render_to_response('instructor/instructor_dashboard_2/instructor_dashboard_2.html', context)


"""
Section functions starting with _section return a dictionary of section data.

The dictionary must include at least {
    'section_key': 'circus_expo'
    'section_display_name': 'Circus Expo'
}

section_key will be used as a css attribute, javascript tie-in, and template import filename.
section_display_name will be used to generate link titles in the nav bar.
"""  # pylint: disable=W0105


def _section_course_info(course_id, access):
    """ Provide data for the corresponding dashboard section """
    course = get_course_by_id(course_id, depth=None)

    section_data = {
        'section_key': 'course_info',
        'section_display_name': _('Course Info'),
        'course_id': course_id,
        'access': access,
        'course_display_name': course.display_name,
        'enrollment_count': CourseEnrollment.objects.filter(course_id=course_id).count(),
        'has_started': course.has_started(),
        'has_ended': course.has_ended(),
        'list_instructor_tasks_url': reverse('list_instructor_tasks', kwargs={'course_id': course_id}),
    }

    try:
        advance = lambda memo, (letter, score): "{}: {}, ".format(letter, score) + memo
        section_data['grade_cutoffs'] = reduce(advance, course.grade_cutoffs.items(), "")[:-2]
    except Exception:
        section_data['grade_cutoffs'] = "Not Available"
    # section_data['offline_grades'] = offline_grades_available(course_id)

    try:
        section_data['course_errors'] = [(escape(a), '') for (a, _unused) in modulestore().get_item_errors(course.location)]
    except Exception:
        section_data['course_errors'] = [('Error fetching errors', '')]

    return section_data


def _section_membership(course_id, access):
    """ Provide data for the corresponding dashboard section """
    section_data = {
        'section_key': 'membership',
        'section_display_name': _('Membership'),
        'access': access,
        'enroll_button_url': reverse('students_update_enrollment', kwargs={'course_id': course_id}),
        'unenroll_button_url': reverse('students_update_enrollment', kwargs={'course_id': course_id}),
        'list_course_role_members_url': reverse('list_course_role_members', kwargs={'course_id': course_id}),
        'modify_access_url': reverse('modify_access', kwargs={'course_id': course_id}),
        'list_forum_members_url': reverse('list_forum_members', kwargs={'course_id': course_id}),
        'update_forum_role_membership_url': reverse('update_forum_role_membership', kwargs={'course_id': course_id}),
    }
    return section_data


def _section_student_admin(course_id, access):
    """ Provide data for the corresponding dashboard section """
    section_data = {
        'section_key': 'student_admin',
        'section_display_name': _('Student Admin'),
        'access': access,
        'get_student_progress_url_url': reverse('get_student_progress_url', kwargs={'course_id': course_id}),
        'reset_student_attempts_url': reverse('reset_student_attempts', kwargs={'course_id': course_id}),
        'rescore_problem_url': reverse('rescore_problem', kwargs={'course_id': course_id}),
        'list_instructor_tasks_url': reverse('list_instructor_tasks', kwargs={'course_id': course_id}),
    }
    return section_data


def _section_data_download(course_id):
    """ Provide data for the corresponding dashboard section """
    section_data = {
        'section_key': 'data_download',
        'section_display_name': _('Data Download'),
        'get_grading_config_url': reverse('get_grading_config', kwargs={'course_id': course_id}),
        'get_students_features_url': reverse('get_students_features', kwargs={'course_id': course_id}),
        'get_anon_ids_url': reverse('get_anon_ids', kwargs={'course_id': course_id}),
    }
    return section_data

def _section_send_email(course_id, access,course):
    """ Provide data for the corresponding bulk email section """
    html_module = HtmlDescriptor(course.system, DictFieldData({'data': ''}), ScopeIds(None, None, None, None))
    section_data = {
        'section_key': 'send_email',
        'section_display_name': _('Email'),
        'access': access,
        'send_email': reverse('send_email',kwargs={'course_id': course_id}),
        'editor': wrap_xmodule(html_module.get_html, html_module, 'xmodule_edit.html')()
    }
    return section_data


def _section_analytics(course_id):
    """ Provide data for the corresponding dashboard section """
    section_data = {
        'section_key': 'analytics',
        'section_display_name': _('Analytics'),
        'get_distribution_url': reverse('get_distribution', kwargs={'course_id': course_id}),
        'proxy_legacy_analytics_url': reverse('proxy_legacy_analytics', kwargs={'course_id': course_id}),
    }
    return section_data
