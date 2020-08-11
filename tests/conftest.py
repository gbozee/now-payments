import asyncio
from starlette.testclient import TestClient
from payments_service.views import app
import pytest
from unittest.mock import Mock

@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def create_future():
    def _create_future(value):
        dd = asyncio.Future()
        dd.set_result(value)
        return dd

    return _create_future


@pytest.fixture
def payment_instance(mocker, create_future):
    class Demo:
        instance = Mock()
        kind = "ravepay"

        def build_redirect_url(self, amount, order_id):
            return "http://www.google.com"

    mock_service = mocker.patch("payments_service.ravepay_views.service")
    mock_instance = Demo()
    mock_service.build_payment_instance.return_value = create_future(mock_instance)
    return mock_service, mock_instance
