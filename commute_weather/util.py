# -*- coding: utf-8 -*-
import logging
import boto3
import base64
import time
import datetime
from typing import Callable

import requests

logger = logging.getLogger(__name__)
_KMS = boto3.client('kms')


def kms_decrypt(ciphertext: str) -> bytes:
    """
    Decrypt a value using KMS.
    
    :param ciphertext: The base64-encoded ciphertext. 
    :return: The plaintext bytestring.
    """
    return _KMS.decrypt(
        CiphertextBlob=base64.b64decode(ciphertext))['Plaintext']


def kms_decrypt_str(ciphertext: str, encoding: str = 'utf-8') -> str:
    """
    Decrypt a piece of text using KMS.
    
    :param ciphertext: The base64-encoded ciphertext.
    :param encoding: The encoding of the text.
    :return: The plaintext.
    """
    return kms_decrypt(ciphertext).decode(encoding)


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


def retry_loop(request: Callable[[], requests.Response], attempts: int = 3,
               gap: float = 60) -> requests.Response:
    """
    Issue a request until it succeeds.
    
    :param request: A function that performs the request and returns the raw
                    response object.
    :param attempts: The number of attempts to make before giving up.
    :param gap: The amount of time to wait between attempts in seconds.
    :return: The successful response.
    :raises RuntimeError: If the request failed on the `attempts`th attempt.
    """
    attempt = 0
    response = None
    while attempt < attempts:
        response = request()
        if response.status_code == requests.codes.ok:
            logger.debug('Successfully retrieved %s', response.url)
            return response
        logger.warning('Failed to fetch %s; retrying in %fs...',
                       response.url, gap)
        attempt += 1
        time.sleep(gap)
    logger.error('Failed to fetch %s after %d attempts', response.url, attempts)
    raise RuntimeError(
        'Request failed after {0} attempts: {1}'.format(attempts, response))
