import requests
import time


def get_with_retry(url, *, attempts=4, **kwargs):
    kwargs.setdefault("timeout", 30)
    for attempt in range(attempts):
        try:
            r = requests.get(url, **kwargs)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            status = getattr(e.response, "status_code", None)
            if (
                status is not None and 400 <= status < 500 and status != 429
            ):  # 400s except 429 (too many requests) should be ignored
                raise
            if attempt == attempts - 1:
                raise
            time.sleep(2**attempt)
