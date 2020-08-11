import asyncio
import requests
import typing
from payments_service import settings
from ravepay.utils import RavepayAPI
from paystack.utils import PaystackAPI
from ravepay.api import signals
from dispatch import receiver


@receiver(signals.successful_payment_signal)
def payment_signal(sender, **kwargs):
    callback_func = kwargs.pop("callback_func")
    signal = kwargs.pop("signal")
    callback_func(kwargs)


@receiver(signals.event_signal)
def event_signal(sender, **kwargs):
    import pdb

    pdb.set_trace()
    callback_func = kwargs.pop("callback_func")
    signal = kwargs.pop("signal")
    callback_func(kwargs)


async def loop_helper(callback):
    loop = asyncio.get_event_loop()
    future = loop.run_in_executor(None, callback)
    return await future


class PaymentInstance:
    def __init__(self, post_params):
        self.post_params = post_params

    @property
    def identifier(self):
        return self.post_params["id"]

    @property
    def kind(self):
        return self.post_params["type"]

    @property
    def instance(self):
        if self.post_params["type"] == "ravepay":
            is_dev = self.post_params["test"] == "TRUE"
            return RavepayAPI(
                public_key=self.post_params["public_key"],
                secret_key=self.post_params["secret_key"],
                test=is_dev,
                django=False,
                webhook_hash=self.post_params["id"],
            )
        if self.post_params["type"] == "paystack":
            return PaystackAPI(
                public_key=self.post_params["public_key"],
                secret_key=self.post_params["secret_key"],
                django=False,
            )

    @property
    def callback_url(self):
        return self.post_params["webhook_url"]

    def build_redirect_url(self, amount, order_id):
        return f"{settings.HOST_URL}/verify-payment/{self.identifier}?amount={amount}&txref={order_id}&amount_only=true"

    def webhook_callback_func(self, params):
        if self.callback_url:
            print(self.callback_url)
            result = requests.post(self.callback_url, json=params)
            print(result.status_code)


async def post(_id):
    def fetch():
        result = requests.post(
            settings.NOW_SHEET_SERVICE + "/read-single",
            json={
                "link": settings.PAYMENT_SHEET,
                "key": "id",
                "sheet": "Sheet1",
                "value": _id,
            },
        )
        if result.status_code < 400:
            return result.json()["data"]
        return None

    return await loop_helper(fetch)


async def build_payment_instance(_id) -> typing.Optional[PaymentInstance]:
    result = await post(_id)
    if result:
        return PaymentInstance(result)
