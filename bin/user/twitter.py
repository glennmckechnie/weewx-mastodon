# Copyright 2014-2020 Matthew Wall
"""
Tweet weather data

You must first obtain app and oauth credentials in order to tweet.  See the
twitter developer documentation to obtain these:

  https://dev.twitter.com/oauth/overview

Specifically, you will need four things:  app_key, app_key_secret, oauth_token,
and oauth_token_secret.

[StdRESTful]
    [[Twitter]]
        app_key = APP_KEY
        app_key_secret = APP_KEY_SECRET
        oauth_token = OAUTH_TOKEN
        oauth_token_secret = OAUTH_TOKEN_SECRET

Tweets look something like this:

STATION_IDENTIFIER: Ws: 0.0; Wd: -; Wg: 1.1; oT: 7.00; oH: 97.00; P: 1025.307; R: 0.000

The STATION_IDENTIFIER is the first part of the station 'location' defined in
weewx.conf.  To specify a different identifier for tweets, use the 'station'
parameter.  For example:

[StdRESTful]
    [[Twitter]]
        station = hal

The 'format' parameter determines the tweet contents.  The default format is:

format = {station:%.8s}: Ws: {windSpeed:%.1f}; Wd: {windDir:%03.0f}; Wg: {windGust:%.1f}; oT: {outTemp:%.1f}; oH: {outHumidity:%.2f}; P: {barometer:%.3f}; R: {rain:%.3f}

To specify a different tweet message, use the format parameter.  For example,
this would tweet only wind information:

[StdRESTful]
    [[Twitter]]
        format = {station}: Ws: {windSpeed}; Wd: {windDir}; Wg: {windGust}

If there is no value for an observation, the hyphen (-) will display.  If
the observation does not exist, the observation label will not be replaced.
If no format is specified for an observation, the default is used.
For example:

    Ws: {windSpeed}             ->  Ws: 12.3452343
    Ws: {windSpeed:%.3f}        ->  Ws: 12.345

Ordinals can be specified for wind direction:

    Wd: {windDir:%03.0f}        ->  Wd: 090
    Wd: {windDir:ORD}           ->  Wd: E

The dateTime field is handled slightly differently.  For example:

    ts: {dateTime}              ->  ts: 1413994070
    ts: {dateTime:%X}           ->  ts: 16:07:50 22 Oct 2014
    ts: {dateTime:%H:%M:%S}     ->  ts: 16:07:50

By default, the units are those specified by the unit system in the
StdConvert section of weewx.conf.  To specify a different unit system,
use the unit_system option:

[StdRESTful]
    [[Twitter]]
        unit_system = METRICWX

Possible values include US, METRIC, or METRICWX.
"""

try:
    # Python 3
    import queue
except ImportError:
    # Python 2
    import Queue as queue
import re
import sys
import time

try:
    # Test for new-style weewx logging by trying to import weeutil.logger
    import weeutil.logger
    import logging
    log = logging.getLogger(__name__)

    def logdbg(msg):
        log.debug(msg)

    def loginf(msg):
        log.info(msg)

    def logerr(msg):
        log.error(msg)

except ImportError:
    # Old-style weewx logging
    import syslog

    def logmsg(level, msg):
        syslog.syslog(level, 'Twitter: %s' % msg)

    def logdbg(msg):
        logmsg(syslog.LOG_DEBUG, msg)

    def loginf(msg):
        logmsg(syslog.LOG_INFO, msg)

    def logerr(msg):
        logmsg(syslog.LOG_ERR, msg)

import weewx
import weewx.restx
import weewx.units
from weeutil.weeutil import to_bool, accumulateLeaves

from twython import Twython, TwythonError, TwythonAuthError, TwythonRateLimitError

VERSION = "0.15"

if weewx.__version__ < "3":
    raise weewx.UnsupportedFeature("weewx 3 is required, found %s" %
                                   weewx.__version__)



def _format(label, fmt, datum):
    s = fmt % datum if datum is not None else "None"
    return "%s: %s" % (label, s)

def _dir_to_ord(x, ordinals):
    try:
        return ordinals[int(round(x / 22.5))]
    except (ValueError, IndexError):
        pass
    return ordinals[17]


class Twitter(weewx.restx.StdRESTbase):

    _DEFAULT_FORMAT = '{station:%.8s}: Ws: {windSpeed:%.1f}; Wd: {windDir:%03.0f}; Wg: {windGust:%.1f}; oT: {outTemp:%.1f}; oH: {outHumidity:%.2f}; P: {barometer:%.3f}; R: {rain:%.3f}'
    _DEFAULT_FORMAT_NONE = '-'
    _DEFAULT_ORDINALS = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S',
                         'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW', 'N', '-']

    def __init__(self, engine, config_dict):
        """This service recognizes standard restful options plus the following:

        Required parameters:

        twitter authentication credentials:
        app_key
        app_key_secret
        oauth_token
        oauth_token_secret

        Optional parameters:

        station: a short name to identify the weather station
        Default is the station location from [Station]

        unit_system: one of US, METRIC, or METRICWX
        Default is None; units will be those of the data in the database

        format: indicates how the tweet should be rendered
        Default contains basic weather data

        format_None: indicates how a NULL value should be rendered
        Default is -

        format_utc: display time in UTC rather than local time
        Default is False

        binding: either loop or archive
        Default is archive
        """
        super(Twitter, self).__init__(engine, config_dict)
        loginf('service version is %s' % VERSION)

        site_dict = weewx.restx.get_site_dict(config_dict, 'Twitter', 'app_key', 'app_key_secret',
                                              'oauth_token', 'oauth_token_secret')
        if site_dict is None:
            return

        # default the station name
        site_dict.setdefault('station', engine.stn_info.location)

        # if a unit system was specified, get the weewx constant for it.
        # do it here so a bogus unit system will cause weewx to die
        # immediately, not simply cause the twitter thread to crap out.
        usn = site_dict.get('unit_system')
        if usn is not None:
            site_dict['unit_system'] = weewx.units.unit_constants[usn]
            loginf('units will be converted to %s' % usn)

        site_dict.setdefault('format', self._DEFAULT_FORMAT)
        site_dict.setdefault('format_None', self._DEFAULT_FORMAT_NONE)
        site_dict.setdefault('format_utc', False)
        site_dict['format_utc'] = to_bool(site_dict.get('format_utc'))
        site_dict.setdefault('ordinals', self._DEFAULT_ORDINALS)

        # we can bind to archive or loop events, default to archive
        binding = site_dict.pop('binding', 'archive')
        if isinstance(binding, list):
            binding = ','.join(binding)
        loginf('binding is %s' % binding)

        self.data_queue = queue.Queue()
        data_thread = TwitterThread(self.data_queue, **site_dict)
        data_thread.start()

        if 'loop' in binding.lower():
            self.bind(weewx.NEW_LOOP_PACKET, self.handle_new_loop)
        if 'archive' in binding.lower():
            self.bind(weewx.NEW_ARCHIVE_RECORD, self.handle_new_archive)

        loginf("Data will be tweeted for %s" % site_dict['station'])

    def handle_new_loop(self, event):
        # Make a copy... we will modify it
        packet = dict(event.packet)
        packet['binding'] = 'loop'
        self.data_queue.put(packet)

    def handle_new_archive(self, event):
        # Make a copy... we will modify it
        record = dict(event.record)
        record['binding'] = 'archive'
        self.data_queue.put(record)

class TwitterThread(weewx.restx.RESTThread):
    def __init__(self, queue, 
                 app_key, app_key_secret, oauth_token, oauth_token_secret,
                 station, format, format_None, ordinals, format_utc=True,
                 unit_system=None, skip_upload=False,
                 log_success=True, log_failure=True,
                 post_interval=None, max_backlog=sys.maxsize, stale=None,
                 timeout=60, max_tries=3, retry_wait=5):
        super(TwitterThread, self).__init__(queue,
                                            protocol_name='Twitter',
                                            manager_dict=None,
                                            post_interval=post_interval,
                                            max_backlog=max_backlog,
                                            stale=stale,
                                            log_success=log_success,
                                            log_failure=log_failure,
                                            max_tries=max_tries,
                                            timeout=timeout,
                                            retry_wait=retry_wait)
        self.app_key = app_key
        self.app_key_secret = app_key_secret
        self.oauth_token = oauth_token
        self.oauth_token_secret = oauth_token_secret
        self.station = station
        self.format = format
        self.format_None = format_None
        self.ordinals = ordinals
        self.format_utc = format_utc
        self.unit_system = unit_system
        self.skip_upload = to_bool(skip_upload)

    def format_tweet(self, record):
        msg = self.format
        for obs in record:
            oldstr = None
            fmt = '%s'
            pattern = "{%s}" % obs
            m = re.search(pattern, msg)
            if m:
                oldstr = m.group(0)
            else:
                pattern = "{%s:([^}]+)}" % obs
                m = re.search(pattern, msg)
                if m:
                    oldstr = m.group(0)
                    fmt = m.group(1)
            if oldstr is not None:
                if obs == 'dateTime':
                    if self.format_utc:
                        ts = time.gmtime(record[obs])
                    else:
                        ts = time.localtime(record[obs])
                    newstr = time.strftime(fmt, ts)
                elif record[obs] is None:
                    newstr = self.format_None
                elif obs == 'windDir' and fmt.lower() == 'ord':
                    newstr = _dir_to_ord(record[obs], self.ordinals)
                else:
                    newstr = fmt % record[obs]
                msg = msg.replace(oldstr, newstr)
        logdbg('msg: %s' % msg)
        return msg

    def process_record(self, record, dummy_manager):
        if self.unit_system is not None:
            record = weewx.units.to_std_system(record, self.unit_system)
        record['station'] = self.station

        msg = self.format_tweet(record)
        if self.skip_upload:
            loginf('skipping upload')
            return

        # now do the posting
        ntries = 0
        while ntries < self.max_tries:
            ntries += 1
            try:
                twitter = Twython(self.app_key, self.app_key_secret,
                                  self.oauth_token, self.oauth_token_secret)
                twitter.update_status(status=msg)
                return
            except TwythonAuthError as e:
                raise weewx.restx.FailedPost("Authorization failed: %s" % e)
            except (TwythonError, TwythonRateLimitError) as e:
                logerr("Failed attempt %d of %d: %s" %
                       (ntries, self.max_tries, e))
                logdbg("Waiting %d seconds before retry" % self.retry_wait)
                time.sleep(self.retry_wait)
        else:
            raise weewx.restx.FailedPost("Max retries (%d) exceeded" %
                                         self.max_tries)
