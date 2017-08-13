# -*- coding: utf-8 -*-
import logging
import datetime

import pytz
import requests

import util

_ENDPOINT_FMT = 'https://api.darksky.net/forecast/{key}/{lat},{long}'

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class PrecipitationSample:
    """
    Represents the chance of precipitation (rain, snow or sleet) and its
    predicted intensity at a point in time.
    """

    def __init__(self, time_: datetime.datetime, probability: float,
                 intensity: float):
        """
        Create a new sample.

        :param time_: When this sample is for (typically an hour starting at
                      this time).
        :param probability: The probability of precipitation, between 0 and 1
                            inclusive.
        :param intensity: The amount of precipitation that will fall during
                          this period in millimeters.
        """
        self.time = time_
        self.probability = probability
        self.intensity = intensity

    @property
    def umbrella_score(self) -> float:
        """
        Calculate the extent to which this sample suggests an umbrella is
        required. 

        :return: A score between 0 and 1 inclusive. 0 indicates an umbrella is
                 definitely not required for this sample, 0.5 indicates
                 ambivalence, and 1 indicates an umbrella is definitely needed.
        """
        if self.probability == 0 and self.intensity == 0:
            return 0
        return 1 - 1 / (self.probability * 10 + self.intensity)

    @staticmethod
    def from_json(json_: dict) -> 'PrecipitationSample':
        """
        Parse a sample returned by the Dark Sky API.

        :param json_: The period JSON. N.B. `si` or `uk2` units are expected.
        :return: The sample in object form.
        """
        return PrecipitationSample(
            pytz.utc.localize(
                datetime.datetime.utcfromtimestamp(json_['time'])),
            json_['precipProbability'],
            json_['precipIntensity'])

    def __str__(self) -> str:
        return '{0}({1}, {2}, {3} mm)'.format(self.__class__.__name__,
                                              self.time,
                                              self.probability,
                                              self.intensity)


def get_location(session: requests.Session, key: str, latitude: float,
                 longitude: float) -> requests.Response:
    """
    Retrieve the API result for a given location.

    :param session: A requests session to use to make the request.
    :param key: The Dark Sky API key to use when making the request.
    :param latitude: The latitude of the location.
    :param longitude: The longitude of the location.
    :return: The request's response object.
    """
    logger.debug('Asking for data for (%f, %f)', latitude, longitude)
    return session.get(
        _ENDPOINT_FMT.format(key=key,
                             lat=latitude,
                             long=longitude),
        params={
            'exclude': ','.join(['currently', 'minutely', 'daily', 'alerts',
                                 'flags']),
            'units': 'uk2'
        })


def assess_location(json_: dict, now: datetime.datetime, begin: datetime.time,
                    end: datetime.time, threshold: float) -> bool:
    """
    Given a location's weather forecast, calculate whether an umbrella is
    necessary.

    :param json_: The API response JSON.
    :param now: The time to regard as right now.
    :param begin: When the working day begins.
    :param end: When the working day ends.
    :param threshold: The precipitation score at or above which an umbrella is
                      required.
    :return: True if an umbrella is required, false otherwise.
    """
    logger.debug('Assessing location (%f, %f)', json_['latitude'],
                 json_['longitude'])
    samples = [PrecipitationSample.from_json(sample)
               for sample in json_['hourly']['data']]
    logger.debug('%d available samples', len(samples))
    samples = [sample for sample in samples
               # we only care about today's weather
               if sample.time.astimezone(begin.tzinfo).date() == now.date() and
               # we don't care about weather earlier today
               sample.time.astimezone(begin.tzinfo) >= now and
               # we only care about weather between the configured times
               util.is_between(sample.time, begin, end)]
    logger.debug('%d relevant samples', len(samples))
    return any([sample.umbrella_score >= threshold for sample in samples])
