import asyncio
from paystack.api.transaction import Transaction
import requests
import typing
from payments_service import settings
from ravepay.utils import RavepayAPI
from paystack.utils import PaystackAPI
from ravepay.api import signals
from dispatch import receiver
from .flutterwave import FlutterwaveAPI
from .stripe_payment import StripeAPI


@receiver(signals.successful_payment_signal)
def payment_signal(sender, **kwargs):
    callback_func = kwargs.pop("callback_func")
    signal = kwargs.pop("signal")
    callback_func(kwargs)


@receiver(signals.event_signal)
def event_signal(sender, **kwargs):
    callback_func = kwargs.pop("callback_func")
    signal = kwargs.pop("signal")
    callback_func(kwargs)


async def loop_helper(callback):
    loop = asyncio.get_event_loop()
    future = loop.run_in_executor(None, callback)
    return await future


class NewTransaction(Transaction):
    def verify_result(self, response, **kwargs):
        if response.status_code == 200:
            result = response.json()
            data = result["data"]
            amount = kwargs.get("amount")
            if amount:
                if float("%.0f" % data["amount"]) == float("%.0f" % float(amount)):
                    return True, result["message"]
                return False, data["amount"]
            return True, result["message"], data

        if response.status_code >= 400:
            return False, "Could not verify transaction"


class NewPaystackAPI(PaystackAPI):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.transaction_api = NewTransaction(
            self.make_request, secret_key=self.secret_key, public_key=self.public_key
        )
        
    def processor_info(self, *args, **kwargs):
        kwargs.pop('session_secret',None)
        result = super().processor_info(*args, **kwargs)
        result['p_amount'] = result['amount'] * 100
        return result
        
    def other_payment_info(self, **kwargs):
        result = super().other_payment_info(**kwargs)
        result['amount'] = result['amount'] * 100
        return result


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
            return NewPaystackAPI(
                public_key=self.post_params["public_key"],
                secret_key=self.post_params["secret_key"],
                django=False,
                base_url="https://api.paystack.co",
            )
        if self.post_params['type'] == 'flutterwave':
            return FlutterwaveAPI(
                public_key=self.post_params["public_key"],
                secret_key=self.post_params["secret_key"],
                django=False,
                base_url='https://api.flutterwave.com/v3',
                webhook_hash=self.post_params["id"],
            )
        if self.post_params['type'] == 'stripe':
            return StripeAPI(
                public_key=self.post_params["public_key"],
                secret_key=self.post_params["secret_key"],
                django=False,
                id=self.post_params["id"],
            )

    @property
    def callback_url(self):
        return self.post_params["webhook_url"]

    def build_redirect_url(self, amount, order_id):
        if self.kind == "paystack":
            amount = amount * 100
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
        print("result", result)
        if result.status_code < 400:
            return result.json()["data"]
        return None

    return await loop_helper(fetch)


async def build_payment_instance(_id) -> typing.Optional[PaymentInstance]:
    result = await post(_id)
    if result:
        return PaymentInstance(result)
