import requests

from app.errors import UpstreamUnavailable

STATUS_URL = "http://localhost:1/status"


def load_retry_policy():
    import backoff

    return backoff.expo


def fetch_status():
    try:
        return requests.get(STATUS_URL, timeout=2).json()
    except requests.exceptions.ConnectionError as e:
        raise UpstreamUnavailable("status service is unreachable") from e


def fetch_status_unchained():
    try:
        return requests.get(STATUS_URL, timeout=2).json()
    except requests.exceptions.ConnectionError:
        raise UpstreamUnavailable("status service is unreachable")
