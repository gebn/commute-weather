# -*- coding: utf-8 -*-
import logging
import datetime

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def is_between(dt_: datetime.datetime, begin: datetime.time,
               end: datetime.time) -> bool:
    """
    Find whether a datetime is between two start and end times on the relevant
    day. All parameters should be aware (have timezone info).
    
    :param dt_: The datetime to check.
    :param begin: The lower bound of acceptable times.
    :param end: The upper bound of acceptable times.
    :return: True if the datetime is between the times, false otherwise.
    """
    def normalise_(datetime_: datetime.datetime, time_: datetime.time) \
            -> datetime.time:
        """
        Returns the time component of `datetime_` in the same timezone as 
        `time_` so they can be compared.
        
        :param datetime_: The datetime to localise and extract the time of.
        :param time_: The time whose timezone to extract.
        :return: The `datetime_`'s time in the timezone of `time_`.
        """

        # convert the datetime to the same timezone as the time so they can be
        # compared
        localised = datetime_.astimezone(time_.tzinfo)

        # just as an annotation - doesn't affect calculations
        return localised.time().replace(tzinfo=time_.tzinfo)

    return begin <= normalise_(dt_, begin) and normalise_(dt_, end) <= end
