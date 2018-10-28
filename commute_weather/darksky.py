# -*- coding: utf-8 -*-
from typing import Iterable
import logging
import datetime
import pytz
import requests

_ENDPOINT_FMT = 'https://api.darksky.net/forecast/{key}/{lat},{long}'
_TIMEOUT = 3  # seconds

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class HourSample:
    """
    Represents the weather forecast for a single hour.
    """

    def __init__(self, time_: datetime.datetime, precip_intensity: float,
                 precip_probability: float, apparent_temp: float):
        """
        Create a new sample.

        :param time_: The time this sample starts at.
        :param precip_intensity: The amount of precipitation that will fall
                                 during this period in millimeters.
        :param precip_probability: The probability of precipitation, between 0
                                   and 1 inclusive.
        :param apparent_temp: The "feels-like" temperature for this hour.
        """
        self.time = time_
        self.precip_intensity = precip_intensity
        self.precip_probability = precip_probability
        self.apparent_temp = apparent_temp

    @property
    def umbrella_score(self) -> float:
        """
        Calculate the chance of precipitation (rain, snow or sleet) for this
        sample.

        :return: A score between 0 and 1 inclusive. 0 indicates an umbrella is
                 definitely not required for this sample, 0.5 indicates
                 ambivalence, and 1 indicates an umbrella is definitely needed.
        """
        if self.precip_intensity == 0 and self.precip_probability == 0:
            return 0
        return 1 - 1 / (self.precip_intensity + self.precip_probability * 10)

    @staticmethod
    def from_json(json_: dict) -> 'HourSample':
        """
        Parse a sample returned by the Dark Sky API.

        :param json_: The period JSON. N.B. `si` or `uk2` units are expected.
        :return: The sample in object form.
        """
        return HourSample(
            pytz.utc.localize(
                datetime.datetime.utcfromtimestamp(json_['time'])),
            json_['precipIntensity'],
            json_['precipProbability'],
            json_['apparentTemperature'])

    def __str__(self) -> str:
        return '{0}({1}, {2} mm, P(precip) = {3}, score = {4}, {5}°C)'.format(
            self.__class__.__name__, self.time, self.precip_intensity,
            self.precip_probability, self.umbrella_score, self.apparent_temp)


def location_hourly(session: requests.Session, key: str, latitude: float,
                    longitude: float) -> Iterable[HourSample]:
    """
    Retrieve the hourly forecast for a location.

    :param session: A requests session to use to make the request.
    :param key: The Dark Sky API key to use.
    :param latitude: The latitude of the location.
    :param longitude: The longitude of the location.
    :return: Samples for all hours contained in the response.
    :raises requests.exceptions.HTTPError: If the request fails.
    """
    logger.debug('Asking for data for (%f, %f)', latitude, longitude)
    response = session.get(
        _ENDPOINT_FMT.format(key=key,
                             lat=latitude,
                             long=longitude),
        params={
            'exclude': ','.join(['currently', 'minutely', 'daily', 'alerts',
                                 'flags']),
            'units': 'uk2'
        },
        timeout=_TIMEOUT)
    response.raise_for_status()
    return [HourSample.from_json(sample)
            for sample in response.json()['hourly']['data']]
