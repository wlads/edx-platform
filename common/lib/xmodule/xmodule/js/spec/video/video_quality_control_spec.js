(function() {
  describe('VideoQualityControl', function() {
    var state, videoControl, videoQualityControl, oldOTBD;

    function initialize() {
      loadFixtures('video.html');
      state = new Video('#example');
      videoControl = state.videoControl;
      videoQualityControl = state.videoQualityControl;
    }

    beforeEach(function() {
      oldOTBD = window.onTouchBasedDevice;
      window.onTouchBasedDevice = jasmine
                                      .createSpy('onTouchBasedDevice')
                                      .andReturn(false);
    });

    afterEach(function() {
      $('source').remove();
      window.onTouchBasedDevice = oldOTBD;
    });

    describe('constructor', function() {
      var SELECTOR = 'a.quality_control';

      beforeEach(function() {
        initialize();
      });

      it('render the quality control', function() {
        var container = videoControl.secondaryControlsEl;
        expect(container).toContain(SELECTOR);
      });

      it('bind the quality control', function() {
        var handler = videoQualityControl.toggleQuality;
        expect($(SELECTOR)).toHandleWith('click', handler);
      });
    });
  });

}).call(this);
