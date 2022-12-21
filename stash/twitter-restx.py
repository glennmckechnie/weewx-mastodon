"""
Tweet weather data

Installation:

0) install twython
   pip install twython

1) put this file in bin/user

2) add the following configuration stanza to weewx.conf

[StdRESTful]
    [[Twitter]]
        station = STATION_IDENTIFIER
        app_key = APP_KEY
        app_secret = APP_SECRET
        oauth_token = OAUTH_TOKEN
        oauth_token_secret = OAUTH_TOKEN_SECRET

[Engines]
    [[WxEngine]]
        restful_services = ... , user.twitter.Twitter

3) restart weewx
    sudo /etc/init.d/weewx stop
    sudo /etc/init.d/weewx start
"""

import Queue
import sys
import syslog

import weewx
import weewx.restx

def logmsg(level, msg):
    syslog.syslog(level, 'restx: Twitter: %s' % msg)

def logdbg(msg):
    logmsg(syslog.LOG_DEBUG, msg)

def loginf(msg):
    logmsg(syslog.LOG_INFO, msg)

def logerr(msg):
    logmsg(syslog.LOG_ERR, msg)

class Twitter(weewx.restx.StdRESTbase):
    def __init__(self, engine, config_dict):
        super(Twitter, self).__init__(engine, config_dict)
        try:
            site_dict = weewx.restx.get_dict(config_dict, 'Twitter')
            site_dict['station']
            site_dict['app_key']
            site_dict['app_key_secret']
            site_dict['oauth_token']
            site_dict['oauth_token_secret']
        except KeyError, e:
            logerr("Data will not be posted: Missing option %s" % e)
            return
        self.loop_queue = Queue.Queue()
        self.loop_thread = TwitterThread(self.loop_queue, **site_dict)
        self.loop_thread.start()
        self.bind(weewx.NEW_LOOP_PACKET, self.new_loop_packet)
        loginf("Data will be tweeted for %s" % site_dict['station'])

    def new_loop_packet(self, event):
        self.loop_queue.put(event.packet)

class TwitterThread(weewx.restx.RESTThread):
    def __init__(self, queue, 
                 station,
                 app_key, app_key_secret, oauth_token, oauth_token_secret,
                 log_success=True, log_failure=True,
                 post_interval=300, max_backlog=sys.maxint, stale=None,
                 timeout=60, max_tries=3, retry_wait=5):
        super(TwitterThread, self).__init__(queue,
                                            protocol_name='Twitter',
                                            database_dict=None,
                                            post_interval=post_interval,
                                            max_backlog=max_backlog,
                                            stale=stale,
                                            log_success=log_success,
                                            log_failure=log_failure,
                                            max_tries=max_tries,
                                            timeout=timeout,
                                            retry_wait=retry_wait)
        self.station = station
        self.app_key = app_key
        self.app_key_secret = app_key_secret
        self.oauth_token = oauth_token
        self.oauth_token_secret = oauth_token_secret

    def process_record(self, record, dummy_archive):
        wstr = "%s: ts: %s; P: %s; iT: %s; oT: %s; iH: %s; oH: %s; Ws: %s; Wg: %s; Wd: %s; R: %s" % (
            self.station,
            record['dateTime'],
            record['barometer'],
            record['inTemp'], record['outTemp'],
            record['inHumidity'], record['outHumidity'],
            record['windSpeed'], record['windGust'], record['windDir'],
            record['rain'])
        ntries = 0
        while ntries < self.max_tries:
            ntries += 1
            twitter = Twython(self.app_key, self.app_secret,
                              self.oauth_token, self.oauth_token_secret)
            twitter.update_status(status=wstr)
            except (TwythonError, TwythonAuthError, TwythonRateLimitError), e:
                logerr("Failed attempt %d of %d to tweet: %s" %
                       (ntries, self.max_tries, e))
                logdbg("Waiting %d seconds before retry" % self.retry_wait)
                time.sleep(self.retry_wait)
        else:
            msg = "Max retries (%d) exceeded for tweeting" % self.max_tries
            logerr(msg)

