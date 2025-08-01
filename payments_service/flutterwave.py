import requests
import logging
import json

from ravepay.api.base import BaseClass
from ravepay.api.webhook import Webhook as RavepayWebhook
from ravepay.api import signals


def charge_data(raw_data, full_auth=False, full=False):
    if full:
        return raw_data
    return {
        "amount": raw_data["amount"],
        "currency": raw_data["currency"],
        "status": raw_data["status"],
        "reference": raw_data["tx_ref"],
        "customer": raw_data["customer"],
        "card": raw_data.get("card"),
    }


def transfer_data(raw_data, full=False):
    if full:
        return raw_data
    result = {
        "amount": raw_data["amount"],
        'account_number': raw_data["account_number"],
        'bank_name': raw_data["bank_name"],
        'currency': raw_data["currency"],
        'status': raw_data["status"],
        "created_at": raw_data["created_at"],
    }
    return result


class Webhook(RavepayWebhook):

    def verify(
        self,
        unique_code,
        request_body,
        use_default=False,
        full_auth=False,
        full=False,
        **kwargs,
    ):
        if unique_code == self.webhook_has:
            payload = json.loads(request_body)
            if payload["event"] in ["charge.completed"]:
                kwargs["data"] = charge_data(
                    payload["data"], full_auth=full_auth, full=full
                )
            elif payload["event"] in ["transfer.completed"]:
                kwargs["data"] = transfer_data(payload["data"], full=full)
                kwargs["transfer_code"] = payload["data"]["transfer_code"]
            else:
                kwargs = {"event": payload["event"], "data": payload["data"]}
            if use_default:
                signal_func = signals.event_signal
            else:
                options = {
                    "charge.completed": signals.successful_payment_signal,
                    "transfer.completed": signals.successful_transfer_signal,
                }
                try:
                    signal_func = options[payload["event"]]
                except KeyError:
                    signal_func = signals.event_signal
            signal_func.send(sender=self, **kwargs)
            return payload["event"], kwargs


class Transaction(BaseClass):

    def verify_result(self, response, **kwargs):
        if response.status_code == 200:
            result = response.json()
            data = result["data"]
            amount = kwargs.get("amount")
            if amount:
                if float(data["amount"]) == float(float(amount)):
                    return True, result["message"]
                return False, data["amount"]
            return True, result["message"], data

        if response.status_code >= 400:
            return False, "Could not verify transaction"

    def verify_payment(self, code, amount_only=True, **kwargs):
        path = "/transactions/{}/verify".format(code)
        response = self.make_request("GET", path)
        
        if amount_only:
            return self.verify_result(response, **kwargs)
        # add test for this scenario
        return self.result_format(response)

    def build_transaction_obj(self, currency="ngn", **kwargs):
        payment_options = {
            'ngn': 'card, banktransfer, account',
            'usd': 'card, account, googlepay, applepay',
            'eur': 'card, account, googlepay, applepay',
            'gbp': 'card, account, googlepay, applepay',
            'ghs': 'card, ghanamobilemoney',
            'xaf': 'card, mobilemoneyfranco',
            'xof': 'card, mobilemoneyfranco',
            'zar': 'card, account, lvoucher, googlepay, applepay',
            'mwk': 'card, mobilemoneymalawi',
            'kes': 'card, mpesa',
            'ugx': 'card, mobilemoneyuganda',
            'rwf': 'card, mobilemoneyrwanda',
            'tzs': 'card, mobilemoneytanzania',
        }
        _currency = currency
        if _currency == 'usd':
            _currency = 'us'
        json_data = {
            "public_key": self.public_key,
            "tx_ref": kwargs.get("reference") or kwargs.get("order"),
            "amount": int(kwargs["amount"]),
            "currency": _currency.upper(),
            "payment_options": payment_options.get(currency.lower()) or kwargs.get("payment_options"),
            "meta": kwargs.get("meta") or {},
            "customer": {
                "email": kwargs.get("email"),
                "phone_number": kwargs.get("phone_number",''),
                "name": kwargs.get("name",''),
            },
            "customizations": {
                "title": kwargs.get("title",''),
                "description": kwargs.get("description",''),
                "logo": kwargs.get("logo",''),
            },
        }
        if kwargs.get("fist_name") and kwargs.get("last_name"):
            json_data["customer"][
                "name"
            ] = f'{kwargs.get("first_name")} {kwargs.get("last_name")}'
        return json_data


class FlutterwaveAPI:
    base_url = ""

    def __init__(self, django=True, **kwargs):

        for key, value in kwargs.items():
            setattr(self, key, value)
        self.transaction_api = Transaction(
            self.make_request, secret_key=self.secret_key, public_key=self.public_key
        )
        # self.transfer_api = api.Transfer(
        #     self.make_request, secret_key=self.secret_key, public_key=self.public_key
        # )
        self.webhook_api = Webhook(self.secret_key, self.webhook_hash)

    def make_request(self, method, path, **kwargs):
        options = {
            "GET": requests.get,
            "POST": requests.post,
            "PUT": requests.put,
            "DELETE": requests.delete,
        }
        url = "{}{}".format(self.base_url, path)
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer {}".format(self.secret_key),
        }
        return options[method](url, headers=headers, **kwargs)

    async def async_make_request(self, method, path, session, **kwargs):
        options = {
            "GET": session.get,
            "POST": session.post,
            "PUT": session.put,
            "DELETE": session.delete,
        }
        url = "{}{}".format(self.base_url, path)
        headers = {
            "Authorization": "Bearer {}".format(self.secret_key),
            "Content-Type": "application/json",
        }
        return await options[method](url, headers=headers, **kwargs)

    def verify_result(self, response, **kwargs):
        return self.transaction_api.verify_result(response, **kwargs)

    def verify_payment(self, code, **kwargs):
        return self.transaction_api.verify_payment(code, **kwargs)

    def generate_digest(self, data):
        return self.webhook_hash

    def processor_info(self, amount, redirect_url=None,**kwargs):
        return {
            "amount": float("%.2f" % amount),
            "js_script": get_js_script(),
            "key": self.public_key,
            "redirect_url": redirect_url,
        }

    def other_payment_info(self, **kwargs):
        return self.transaction_api.build_transaction_obj(**kwargs)


def get_js_script():
    return "https://checkout.flutterwave.com/v3.js"
