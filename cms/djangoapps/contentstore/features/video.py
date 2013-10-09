#pylint: disable=C0111

from lettuce import world, step
from xmodule.modulestore import Location
from contentstore.utils import get_modulestore
from selenium.webdriver.common.keys import Keys

BUTTONS = {
    'CC': '.hide-subtitles',
    'volume': '.volume',
}


@step('I have created a Video component$')
def i_created_a_video_component(step):
    world.create_component_instance(
        step, '.large-video-icon',
        'video',
        '.xmodule_VideoModule',
        has_multiple_templates=False
    )


@step('I have created a Video component with subtitles$')
def i_created_a_video_with_subs(_step):
    _step.given('I have created a Video component with subtitles "OEoXaMPEzfM"')


@step('I have created a Video component with subtitles "([^"]*)"$')
def i_created_a_video_with_subs_with_name(_step, sub_id):
    _step.given('I have created a Video component')

    # Store the current URL so we can return here
    video_url = world.browser.url

    # Upload subtitles for the video using the upload interface
    _step.given('I have uploaded subtitles "{}"'.format(sub_id))

    # Return to the video
    world.visit(video_url)
    world.wait_for_xmodule()


@step('I have uploaded subtitles "([^"]*)"$')
def i_have_uploaded_subtitles(_step, sub_id):
    _step.given('I go to the files and uploads page')

    sub_id = sub_id.strip()
    if not sub_id:
        sub_id = 'OEoXaMPEzfM'
    _step.given('I upload the test file "subs_{}.srt.sjson"'.format(sub_id))


@step('when I view the (.*) it does not have autoplay enabled$')
def does_not_autoplay(_step, video_type):
    world.wait_for_xmodule()
    assert world.css_find('.%s' % video_type)[0]['data-autoplay'] == 'False'
    assert world.css_has_class('.video_control', 'play')


@step('creating a video takes a single click$')
def video_takes_a_single_click(_step):
    component_css = '.xmodule_VideoModule'
    assert world.is_css_not_present(component_css)

    world.css_click("a[data-category='video']")
    assert world.is_css_present(component_css)


@step('I edit the component$')
def i_edit_the_component(_step):
    world.edit_component()


@step('I have (hidden|toggled) captions$')
def hide_or_show_captions(step, shown):
    world.wait_for_xmodule()
    button_css = 'a.hide-subtitles'
    if shown == 'hidden':
        world.css_click(button_css)
    if shown == 'toggled':
        world.css_click(button_css)
        # When we click the first time, a tooltip shows up. We want to
        # click the button rather than the tooltip, so move the mouse
        # away to make it disappear.
        button = world.css_find(button_css)
        # mouse_out is not implemented on firefox with selenium
        if not world.is_firefox:
            button.mouse_out()
        world.css_click(button_css)


@step('I have created a video with only XML data$')
def xml_only_video(step):
    # Create a new video *without* metadata. This requires a certain
    # amount of rummaging to make sure all the correct data is present
    step.given('I have clicked the new unit button')

    # Wait for the new unit to be created and to load the page
    world.wait(1)

    location = world.scenario_dict['COURSE'].location
    store = get_modulestore(location)

    parent_location = store.get_items(Location(category='vertical', revision='draft'))[0].location

    youtube_id = 'ABCDEFG'
    world.scenario_dict['YOUTUBE_ID'] = youtube_id

    # Create a new Video component, but ensure that it doesn't have
    # metadata. This allows us to test that we are correctly parsing
    # out XML
    world.ItemFactory.create(
        parent_location=parent_location,
        category='video',
        data='<video youtube="1.00:%s"></video>' % youtube_id
    )


@step('The correct Youtube video is shown$')
def the_youtube_video_is_shown(_step):
    world.wait_for_xmodule()
    ele = world.css_find('.video').first
    assert ele['data-streams'].split(':')[1] == world.scenario_dict['YOUTUBE_ID']


@step('Make sure captions are (.+)$')
def set_captions_visibility_state(_step, captions_state):
    if captions_state == 'closed':
        if world.css_visible('.subtitles'):
            world.browser.find_by_css('.hide-subtitles').click()
    else:
        if not world.css_visible('.subtitles'):
            world.browser.find_by_css('.hide-subtitles').click()


@step('I hover over button "([^"]*)"$')
def hover_over_button(_step, button):
    world.css_find(BUTTONS[button.strip()]).mouse_over()


@step('Captions (?:are|become) "([^"]*)"$')
def are_captions_visibile(_step, visibility_state):
    _step.given('Captions become "{0}" after 0 seconds'.format(visibility_state))


@step('Captions (?:are|become) "([^"]*)" after (.+) seconds$')
def check_captions_visibility_state(_step, visibility_state, timeout):
    timeout = int(timeout.strip())

    # Captions become invisible by fading out. We must wait by a specified
    # time.
    world.wait(timeout)

    if visibility_state == 'visible':
        assert world.css_visible('.subtitles')
    else:
        assert not world.css_visible('.subtitles')

def find_caption_line_by_data_index(index):
    SELECTOR = ".subtitles > li[data-index='{index}']".format(index=index)
    return world.css_find(SELECTOR).first

@step('I focus on caption line with data-index (\d+)$')
def focus_on_caption_line(_step, index):
    find_caption_line_by_data_index(int(index.strip()))._element.send_keys(Keys.TAB)


@step('I press "enter" button on caption line with data-index (\d+)$')
def focus_on_caption_line(_step, index):
    find_caption_line_by_data_index(int(index.strip()))._element.send_keys(Keys.ENTER)


@step('I see caption line with data-index (\d+) has class "([^"]*)"$')
def caption_line_has_class(_step, index, className):
    SELECTOR = ".subtitles > li[data-index='{index}']".format(index=int(index.strip()))
    world.css_has_class(SELECTOR, className.strip())

