import pytest
from starlette.testclient import TestClient
from unittest.mock import Mock


def test_home_route(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"hello": "world"}


def test_verify_payment(client: TestClient, payment_instance):
    mock_service, mock_instance = payment_instance
    # Successful scenario with query parameters passed.
    mock_instance.instance.verify_payment.return_value = [True, "Successful", {}]
    response = client.get(
        "/verify-payment/ravepay_dev", params={"amount": 4000, "txref": "ADESDESD"}
    )
    mock_service.build_payment_instance.assert_called_with("ravepay_dev")
    mock_instance.instance.verify_payment.assert_called_with(
        "ADESDESD", amount="4000", amount_only=False
    )
    assert response.status_code == 200
    assert response.json() == {"status": True, "msg": "Successful", "data": {}}
    # Failure Scenario 1 with query parameters passed
    mock_instance.instance.verify_payment.return_value = [False, "Failed", {}]
    response = client.get(
        "/verify-payment/ravepay_dev", params={"amount": 4000, "txref": "ADESDESD"}
    )
    assert response.status_code == 200
    assert response.json() == {
        "status": False,
        "msg": "Verification Failed",
    }
    # when corresponding query parameters are not passed
    response = client.get("/verify-payment/ravepay_dev", params={})
    assert response.status_code == 400
    assert response.json() == {
        "status": False,
        "msg": "missing `amount` or `txref` query parameters",
    }


def test_client_payment_object(client: TestClient, payment_instance):
    mock_service, mock_instance = payment_instance
    mock_instance.instance.processor_info.return_value = {"hello": "world"}
    mock_instance.instance.other_payment_info.return_value = {"others": True}
    response = client.post(
        "/build-payment-info/ravepay_dev",
        json={
            "amount": 4000,
            "currency": "NGN",
            "order": "ADESDESD",
            "user": {},
            "processor_info": {},
        },
    )
    assert response.status_code == 200
    assert response.json() == {
        "status": True,
        "data": {
            "processor_button_info": {"others": True},
            "payment_obj": {"hello": "world"},
            "kind": "ravepay",
        },
    }
    mock_instance.instance.processor_info.assert_called_with(
        4000, redirect_url="http://www.google.com"
    )
    mock_instance.instance.other_payment_info.assert_called_with(
        currency="NGN",
        order="ADESDESD",
        callback_url="http://www.google.com",
        amount=4000,
    )

