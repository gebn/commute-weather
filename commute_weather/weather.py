# -*- coding: utf-8 -*-
import itertools
from typing import Iterable
import logging
import sys
import os
import datetime
import pytz
import json
import requests
import boto3

import util
import darksky

# regardless of where this script is run, we want to work in this timezone
_TIMEZONE = pytz.timezone(os.environ['TIMEZONE'])

# so we are consistent, even if this script's execution strides midnight
_NOW = datetime.datetime.now(_TIMEZONE)

_DARK_SKY_SECRET_KEY = os.environ['DARK_SKY_SECRET_KEY']

_NOTIFICATION_TOPIC_ARN = os.environ['NOTIFICATION_TOPIC_ARN']
_NOTIFICATION_TOPIC_REGION = _NOTIFICATION_TOPIC_ARN.split(':')[3]
_PUSHOVER_APP_TOKEN = os.environ['PUSHOVER_APP_TOKEN']

# at or above this, an umbrella will be recommended
_SCORE_THRESHOLD = float(os.environ['SCORE_THRESHOLD'])
_DAY_BEGIN = datetime.time(int(os.environ['DAY_BEGIN_HOUR']), tzinfo=_TIMEZONE)
_DAY_END = datetime.time(int(os.environ['DAY_END_HOUR']), tzinfo=_TIMEZONE)
_ROUTE = json.loads(os.environ['ROUTE'])

_SNS = boto3.client('sns', region_name=_NOTIFICATION_TOPIC_REGION)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def filter_samples(samples: Iterable[darksky.HourSample],
                   now: datetime.datetime, begin: datetime.time,
                   end: datetime.time) -> Iterable[darksky.HourSample]:
    """
    Remove hours of forecast that we do not care about.

    :param samples: The set of samples to filter.
    :param now: The time to regard as right now.
    :param begin: When the working day begins.
    :param end: When the working day ends.
    :return: Samples that fall within the remainder of the current working day.
    """
    return (sample for sample in samples
            # we only care about today's weather
            if sample.time.astimezone(begin.tzinfo).date() == now.date() and
            # we don't care about weather earlier today
            sample.time.astimezone(begin.tzinfo) >= now and
            # we only care about weather between the configured times
            util.is_between(sample.time, begin, end))


def main() -> None:
    """
    Executes the main bulk of this function.

    :raises RuntimeError: If something goes wrong.
    """
    if len(_ROUTE) == 0:
        raise RuntimeError('The route must contain at least one location')

    if _NOW.time() > _DAY_END:
        raise RuntimeError('There are no more working hours today')

    session = requests.session()
    samples = itertools.chain.from_iterable(
        filter_samples(
            darksky.location_hourly(session, _DARK_SKY_SECRET_KEY, lat, long_),
            _NOW, _DAY_BEGIN, _DAY_END)
        for lat, long_ in _ROUTE)

    # we need to iterate over the whole sequence at least twice due to the min
    # and max temp calculation - laziness doesn't buy anything
    samples = list(samples)

    over_threshold = [sample for sample in samples
                      if sample.umbrella_score >= _SCORE_THRESHOLD]
    umbrella = len(over_threshold) > 0
    logger.info('Umbrella required? %s', umbrella)
    if umbrella:
        logger.info('%d samples were over the threshold of %f',
                    len(over_threshold), _SCORE_THRESHOLD)
        # in case we say an umbrella is required, but it turns out not to be
        for sample in over_threshold:
            logger.debug(sample)

    temperatures = [sample.apparent_temp for sample in samples]
    low = min(temperatures)
    high = max(temperatures)
    logger.info('Low: %.2f, High: %.2f', low, high)

    summary = 'You need to take your umbrella' \
        if umbrella else 'You don\'t need your umbrella!'
    message = {
        'app': _PUSHOVER_APP_TOKEN,
        'body': f'{summary} (Low: {round(low)}°C, High: {round(high)}°C)',
        'url': f'https://darksky.net/forecast/{_ROUTE[0][0]},{_ROUTE[0][1]}'
               f'/uk224/en'
    }
    response = _SNS.publish(
        TopicArn=_NOTIFICATION_TOPIC_ARN,
        Message=json.dumps(message, ensure_ascii=False))
    logger.info(f"Published message {response['MessageId']}")


# noinspection PyUnusedLocal
def lambda_handler(event, context) -> None:
    """
    AWS Lambda entry point.
    
    :param event: The event that triggered this execution.
    :param context: Current runtime information: http://docs.aws.amazon.com
                    /lambda/latest/dg/python-context-object.html.
    :return: The script exit code. 
    """
    logger.info('Event: %s', event)
    main()


if __name__ == '__main__':
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
    logger.debug('Running outside of Lambda')
    main()
