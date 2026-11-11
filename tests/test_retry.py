from unittest.mock import Mock

import pytest
from sqlalchemy.exc import OperationalError

from app.utils.retry import retry

exc = OperationalError("stmt", {}, Exception("boom"))


def test_retry_successful():
    expected_result = object()
    mock = Mock(side_effect=[exc, exc, expected_result])
    sleep = Mock()
    result = retry(mock, sleep=sleep)
    assert result is expected_result
    assert mock.call_count == 3


def test_retry_unsuccessful():
    mock = Mock(side_effect=exc)
    sleep = Mock()

    with pytest.raises(OperationalError) as excinfo:
        retry(mock, sleep=sleep)

    assert excinfo.value is exc
    assert sleep.call_count == 4
    assert mock.call_count == 5
