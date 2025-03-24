import functools
from typing import Union, List, Dict
import time

import pandas as pd
import requests
from retrying import retry

from .common import LRU_CACHE_SIZE, MAX_ATTEMPT_NUMBER, to_datetime

MAX_RETRIES = 5


# @retry(stop_max_attempt_number=MAX_ATTEMPT_NUMBER)
@functools.lru_cache(maxsize=LRU_CACHE_SIZE)
def get_data(ts_code: int, begin: str, end: str, ntry: int = 0) -> List:
    """
    Requests time series data from the SGS API in json format.
    """

    url = (
        "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{}"
        "/dados?formato=json&dataInicial={}&dataFinal={}"
    )
    request_url = url.format(ts_code, begin, end)
    try:
        response = requests.get(request_url, timeout=10)
        response.raise_for_status()
        response_json = response.json()

    except Exception as e:
        print(f"Tentativa {ntry + 1} falhou: {e}")
        ntry += 1
        if ntry < MAX_RETRIES:
            wait_time = 2**ntry
            print(f"Aguardando {wait_time}s antes de tentar novamente...")
            time.sleep(wait_time)
            return get_data(ts_code, begin, end, ntry)
        else:
            raise e

    return response_json


def get_data_with_strict_range(ts_code: int, begin: str, end: str) -> List:
    """
    Request time series data from the SGS API considering a strict range of dates.

    SGS API default behaviour returns the last stored value when selected date range have no data.

    It is possible to catch this behaviour when the first record date precedes the start date.

    This function enforces an empty data set when the first record date precedes the start date, avoiding records out of selected range.

    :param ts_code: time serie code.
    :param begin: start date (DD/MM/YYYY).
    :param end: end date (DD/MM/YYYY).

    :return: Data in json format or an empty list
    :rtype: list

    """
    data = get_data(ts_code, begin, end)

    first_record_date = to_datetime(data[0]["data"], "pt")
    period_start_date = to_datetime(begin, "pt")

    try:
        is_out_of_range = first_record_date < period_start_date  # type: ignore
        if is_out_of_range:
            raise ValueError
    except TypeError:
        print(
            "ERROR: Serie "
            + str(ts_code)
            + " - Please, use 'DD/MM/YYYY' format for date strings."
        )
        data = []
    except ValueError:
        print(
            "WARNING: Serie "
            + str(ts_code)
            + " - There is no data for the requested period, but there's previous data."
        )
        data = []

    return data
