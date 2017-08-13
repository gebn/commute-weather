# -*- coding: utf-8 -*-
import logging
import sys
import os
import datetime

import chump
import requests
import pytz

import util
import darksky


# regardless of where this script is run, we want to work in this timezone
_TIMEZONE = pytz.timezone(os.environ['TIMEZONE'])

# so we are consistent, even if this script's execution strides midnight
_NOW = datetime.datetime.now(_TIMEZONE)

_DARK_SKY_SECRET_KEY = util.kms_decrypt_str(os.environ['DARK_SKY_SECRET_KEY'])
_PUSHOVER_APP_TOKEN = util.kms_decrypt_str(os.environ['PUSHOVER_APP_TOKEN'])
_PUSHOVER_USER_KEY = util.kms_decrypt_str(os.environ['PUSHOVER_USER_KEY'])

# at or above this, an umbrella will be recommended
_SCORE_THRESHOLD = float(os.environ['SCORE_THRESHOLD'])
_DAY_BEGIN = datetime.time(int(os.environ['DAY_BEGIN_HOUR']), tzinfo=_TIMEZONE)
_DAY_END = datetime.time(int(os.environ['DAY_END_HOUR']), tzinfo=_TIMEZONE)
_ROUTE = []

logging.basicConfig(level=logging.DEBUG, stream=sys.stdout,
                    format='[%(asctime)s:%(name)s:%(levelname)s] %(message)s')
logging.getLogger('chump').setLevel(logging.INFO)  # chump is very verbose
logger = logging.getLogger(__name__)


def _wrapper(json_: dict) -> dict:
    logger.debug('EXECUTING _TMP')
    return json_


def main() -> int:
    assert len(_ROUTE) >= 1

    user = chump.Application(_PUSHOVER_APP_TOKEN).get_user(_PUSHOVER_USER_KEY)
    session = requests.session()

    try:
        umbrella = any(
            [darksky.assess_location(
                _wrapper(util.retry_loop(lambda: darksky.get_location(
                    session, _DARK_SKY_SECRET_KEY, lat, long_)).json()),
                _NOW, _DAY_BEGIN, _DAY_END, _SCORE_THRESHOLD)
             for lat, long_ in _ROUTE])
        logger.debug('Result: %s', umbrella)
    except RuntimeError as e:
        user.send_message('Weather job failed: {0}'.format(e),
                          priority=chump.HIGH)
        return 1

    message = 'You need to take your umbrella...' \
        if umbrella else 'You don\'t need your umbrella!'
    forecast_url = 'https://darksky.net/forecast/{lat},{long}/uk224/en' \
        .format(lat=_ROUTE[0][0], long=_ROUTE[0][1])
    message = user.send_message(message, url=forecast_url)
    if not message.is_sent:
        return 2
    logger.debug('Successfully sent notification %s', message.id)
    return 0


def lambda_handler(event, context) -> int:
    """
    AWS Lambda entry point.
    
    :param event: The event that triggered this execution.
    :param context: Current runtime information: http://docs.aws.amazon.com
                    /lambda/latest/dg/python-context-object.html.
    :return: The script exit code. 
    """
    logger.info('Event: %s', event)
    logger.info('AWS Request ID: %s', context.aws_request_id)
    logger.debug('Running with %s MiB of memory', context.memory_limit_in_mb)
    return main()


if __name__ == '__main__':
    sys.exit(main())
