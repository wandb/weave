(async function () {
  const ANALYTICS_DISABLED = window.CONFIG?.ANALYTICS_DISABLED ?? window.WEAVE_CONFIG?.ANALYTICS_DISABLED ?? false;
  if (ANALYTICS_DISABLED) {
    return;
  }
  // OneTrust Cookies Consent Notice
  // OneTrust requires JQuery, and by default loads an outdated version along with its own script.
  // We're turning off that default behavior and loading our own updated version of JQuery instead.
  // We must ensure that JQuery is fully loaded before inserting the OneTrust script
  // to avoid potential timing issues.
  insertScript('/__frontend/jquery-3.6.0.min.js').then(() =>
    insertScript(
      'https://cdn.cookielaw.org/consent/da0f7ab4-835a-42da-beeb-767dcff7d1cc.js'
    )
  );

  function insertCookieControlledScript(
    url,
    cookieControlGroupID,
    callback,
    async
  ) {
    // Use Optanon to conditionally insert tracking scripts. This is the "Onetrust"
    // cookie consent platform (https://app.onetrust.com) that we use to get
    // cookie consent from European users. Cookies can be enabled/disabled by
    // category. Categories are configured in the OneTrust UI. cookieControlGroupID
    // specifies the category.

    window.Optanon.InsertScript(
      url,
      'body',
      callback,
      null,
      cookieControlGroupID,
      async || false
    );
  }

  function addSegmentAnalyticsMethods() {
    var analytics = (window.analytics = window.analytics || []);
    // Segment boilerplate. Add stubs for segment analytics methods so
    // they can be called even if segment is disabled.
    if (analytics.invoked) {
      console.error('Segment snippet included twice.');
    } else {
      analytics.invoked = !0;
      analytics.methods = [
        'trackSubmit',
        'trackClick',
        'trackLink',
        'trackForm',
        'pageview',
        'identify',
        'reset',
        'group',
        'track',
        'ready',
        'alias',
        'debug',
        'page',
        'once',
        'off',
        'on',
        'use',
        'init',
        'user',
        'anonymousId',
      ];
      analytics.factory = function (t) {
        return function () {
          var e = Array.prototype.slice.call(arguments);
          e.unshift(t);
          analytics.push(e);
          return analytics;
        };
      };
      for (var t = 0; t < analytics.methods.length; t++) {
        var e = analytics.methods[t];
        analytics[e] = analytics.factory(e);
      }
    }

    if (window.document.cookie.indexOf('segment_logging') != -1) {
      enableSegmentAnalyticsLogging();
    }
  }

  addSegmentAnalyticsMethods();

  function enableSegmentAnalyticsLogging() {
    const analytics = window.analytics;
    Object.getOwnPropertyNames(analytics)
      .filter(p => {
        return typeof analytics[p] === 'function';
      })
      .forEach(p => {
        const f = analytics[p];
        analytics[p] = function () {
          if (p === 'page') {
            console.groupCollapsed('segment:' + p + ' ' + arguments[1]);
            console.log('category: ', arguments[0]);
            console.log('properties: ', arguments[2]);
            console.groupEnd();
          } else if (p === 'track' || p === 'group' || p === 'identify') {
            console.groupCollapsed('segment:' + p + ' ' + arguments[0]);
            console.log('properties: ', arguments[1]);
            console.groupEnd();
          }
          return f.apply(this, arguments);
        };
      });
  }

  function analyticsCallback() {
    if (window.document.cookie.indexOf('segment_logging') != -1) {
      enableSegmentAnalyticsLogging();
    }
  }

  function enableSegmentAnalytics() {
    // Adds the segment analytics library. This is boilerplate.
    if (!analytics.initialize) {
      analytics.SNIPPET_VERSION = '4.0.0';
      // this is segment's analytics.js library (https://github.com/segmentio/analytics.js-core) bundled with all of our integrations and settings.
      // it can be retrieved from https://cdn.segment.com/analytics.js/v1/WmJvIs1MTqNjKAeQmEyw6TvqyRI5Su2z/analytics.min.js
      // we serve it locally since cdn.segment.com is usually blocked by ad-blockers.
      insertCookieControlledScript('/__frontend/sa.min.js', 2, () =>
        analyticsCallback()
      );

      // autotrack.js provides the trackers required below
      insertCookieControlledScript('/__frontend/autotrack.js', 2);
      window.ga =
        window.ga ||
        function () {
          window.ga.q = window.ga.q || [];
          window.ga.q.push(arguments);
        };
      window.ga('require', 'eventTracker');
      window.ga('require', 'outboundLinkTracker');
      window.ga('require', 'urlChangeTracker');
      window.ga('require', 'cleanUrlTracker');
      window.ga('require', 'impressionTracker');
      window.ga('require', 'maxScrollTracker');
      window.ga('require', 'mediaQueryTracker');
      window.ga('require', 'outboundFormTracker');
      window.ga('require', 'pageVisibilityTracker');
    }
  }

  function enablePendo() {
    (function (apiKey) {
      (function (p, e, n, d, o) {
        var v, w, x, y, z;
        o = p[d] = p[d] || {};
        o._q = o._q || [];
        v = ['initialize', 'identify', 'updateOptions', 'pageLoad', 'track'];
        for (w = 0, x = v.length; w < x; ++w)
          (function (m) {
            o[m] =
              o[m] ||
              function () {
                o._q[m === v[0] ? 'unshift' : 'push'](
                  [m].concat([].slice.call(arguments, 0))
                );
              };
          })(v[w]);
        insertCookieControlledScript(
          'https://cdn.pendo.io/agent/static/' + apiKey + '/pendo.js',
          2,
          () => {
            if (window.__INITIALIZE_PENDO != null) {
              window.__INITIALIZE_PENDO();
            }
          },
          true
        );
      })(window, document, 'script', 'pendo');
    })('6cf55906-1f5f-4b4b-551a-75200e56ad3e');
  }

  window.thirdPartyAnalyticsOK = false;
  window.OptanonWrapper = function () {
    window.thirdPartyAnalyticsOK = true;
    // This function runs when the user changes their cookie consent settings,
    // or when optanon determines we don't need to check for cookie consent.
    enableSegmentAnalytics();
    enablePendo();
  };
})();
