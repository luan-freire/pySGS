import functools
from typing import Union, List, Dict
import time
from datetime import datetime, timedelta

import pandas as pd
import requests
from retrying import retry

from .common import LRU_CACHE_SIZE, MAX_ATTEMPT_NUMBER, to_datetime

MAX_RETRIES = 5


# @retry(stop_max_attempt_number=MAX_ATTEMPT_NUMBER)
@functools.lru_cache(maxsize=LRU_CACHE_SIZE)
def get_data(ts_code: int, begin: str, end: str, ntry: int = 0) -> List:
    """
    Requests time series data from the SGS API in json format,
    ensuring the date range does not exceed 10 years.
    """

    def parse_date(date_str: str) -> datetime:
        return datetime.strptime(date_str, "%d/%m/%Y")

    def format_date(date_obj: datetime) -> str:
        return date_obj.strftime("%d/%m/%Y")

    begin_date = parse_date(begin)
    end_date = parse_date(end)
    max_interval = timedelta(days=365 * 10)
    results = []

    current_start = begin_date
    while current_start <= end_date:
        current_end = min(current_start + max_interval, end_date)
        request_url = (
            f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{ts_code}"
            f"/dados?formato=json&dataInicial={format_date(current_start)}&dataFinal={format_date(current_end)}"
        )
        try:
            response = requests.get(request_url, timeout=30)
            response.raise_for_status()
            response_json = response.json()
            results.extend(response_json)
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

        current_start = current_end + timedelta(days=1)

    return results


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
