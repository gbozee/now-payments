import stripe
from typing import List, Dict, Optional, Any, TypedDict
from datetime import datetime


class PlanType(TypedDict):
    id: str
    name: str
    amount: int
    duration: int
    currency: str


class PaymentJSONType(TypedDict):
    amount: int
    currency: str
    order: str
    user: Dict[str, str]
    processor_info: Dict[str, Any]
    success_url: Optional[str]
    cancel_url: Optional[str]
    metadata: Optional[Dict[str, str]]


class StripeProcessor:
    def __init__(self, secret_key: str, id: str, public_key: str):
        self.secret_key = secret_key
        self.public_key = public_key
        self.id = id
        self.plans: List[PlanType] = []
        self.products: List[Dict[str, str]] = []
        stripe.api_key = self.secret_key
        stripe.api_version = "2022-11-15"

    def get_plan(self, name: str) -> Optional[PlanType]:
        return next(
            (plan for plan in self.plans if plan["name"].lower() == name.lower()), None
        )

    def create_product(self, name: str):
        existing_product = next(
            (
                product
                for product in self.products
                if product["name"].lower() == name.lower()
            ),
            None,
        )
        if existing_product:
            return existing_product
        response = stripe.Product.create(name=name)
        return response

    def create_price(self, plan: Dict[str, Any], update: bool = False):
        options = {
            30: {"interval": "day", "interval_count": 30},
            90: {"interval": "day", "interval_count": 90},
            180: {"interval": "day", "interval_count": 180},
            365: {"interval": "day", "interval_count": 365},
        }
        product = self.create_product(plan["name"])
        existing_plan = self.get_plan(plan["name"])
        if existing_plan:
            if update and existing_plan["amount"] != int(plan["amount"] * 100):
                response = stripe.Price.create(
                    currency=plan["currency"].lower(),
                    recurring=options[plan["duration"]],
                    unit_amount=int(plan["amount"] * 100),
                    product=product.id,
                )
                stripe.Product.modify(product.id, default_price=response.id)
                return {
                    "id": response.id,
                    "name": product.name,
                    "amount": response.unit_amount,
                    "duration": self.get_duration(response.recurring),
                    "currency": response.currency,
                }
            return existing_plan
        response = stripe.Price.create(
            currency=plan["currency"].lower(),
            recurring=options[plan["duration"]],
            unit_amount=int(plan["amount"] * 100),
            product=product.id,
        )
        return {
            "id": response.id,
            "name": product.name,
            "amount": response.unit_amount,
            "duration": self.get_duration(response.recurring),
            "currency": response.currency,
        }

    def get_duration(self, recurring: Dict[str, Any]) -> int:
        if recurring["interval"] == "day":
            return recurring["interval_count"]
        if recurring["interval"] == "month":
            return recurring["interval_count"] * 30
        if recurring["interval"] == "year":
            return recurring["interval_count"] * 365
        return 0

    def get_prices(self):
        prices = stripe.Price.list(limit=100)
        products = stripe.Product.list(limit=100)
        self.products = [
            {"id": product.id, "name": product.name} for product in products.data
        ]
        self.plans = [
            {
                "id": price.id,
                "name": next(
                    product["name"]
                    for product in self.products
                    if product["id"] == price.product
                ),
                "amount": price.unit_amount,
                "duration": self.get_duration(price.recurring),
                "currency": price.currency,
            }
            for price in prices.data
            if price.active
            and price.recurring
            and str(price.unit_amount).endswith("00")
        ]
        return self.plans

    def create_prices(self, plans: List[Dict[str, Any]], update: bool = False):
        self.get_prices()
        response = [self.create_price(plan, update) for plan in plans]
        return response

    def build_session_url(
        self, payload: Dict[str, Any], mode: str = "subscription", currency: str = "usd"
    ):
        line_items = []
        if mode == "subscription" and payload.get("plan_id"):
            line_items.append({"price": payload["plan_id"], "quantity": 1})
        else:
            line_items.append(
                {
                    "price_data": {
                        "currency": currency.lower(),
                        "product_data": {"name": payload["description"]},
                        "unit_amount": int(payload["amount"] * 100),
                    },
                    "quantity": 1,
                }
            )
        session = stripe.checkout.Session.create(
            mode=mode,
            payment_method_types=["card"],
            line_items=line_items,
            customer_email=payload["user"]["email"],
            client_reference_id=payload.get("session_id"),
            success_url=payload["success_url"],
            cancel_url=payload["cancel_url"],
            metadata=payload.get("metadata"),
        )
        return {
            "url": session.url,
            "id": session.id,
            "customer": session.customer,
            "subscription": session.subscription,
            "session_id": session.id,
        }

    def build_session_ui_url(self, currency="usd", **payload):
        session = stripe.checkout.Session.create(
            ui_mode="embedded",
            line_items=[
                {
                    # Provide the exact Price ID (for example, pr_1234) of the product you want to sell
                    "price_data": {
                        "currency": currency.lower(),
                        "unit_amount": int(payload["amount"] * 100),
                        "product_data": {"name": payload.get('title') or payload.get('description')},
                    },
                    "quantity": 1,
                },
            ],
            mode="payment",
            return_url=payload["return_url"] + "?session_id={CHECKOUT_SESSION_ID}",
        )
        return {
            "session_secret": session.client_secret,
            "session_id": session.id,
            "key": self.public_key,
        }

    def verify_successful_session(self, payload: Dict[str, str]):
        try:
            session = stripe.checkout.Session.retrieve(payload["session_id"])
        except Exception:
            sessions = stripe.checkout.Session.list(
                limit=100,
                subscription=payload["session_id"],
            )
            completed_sessions = [s for s in sessions.data if s.status == "complete"]
            if completed_sessions:
                session = completed_sessions[0]
            else:
                raise

        subscription = {}
        if session.subscription:
            found_subscription = stripe.Subscription.retrieve(session.subscription)
            subscription = {
                "subscription": found_subscription.id,
                "next_payment_date": datetime.fromtimestamp(
                    found_subscription.current_period_end
                ).isoformat(),
                "start_date": datetime.fromtimestamp(
                    found_subscription.current_period_start
                ).isoformat(),
                "currency": found_subscription.currency,
            }

        return {
            "status": "success" if session.status == "complete" else "failed",
            "authorization": None,
            **subscription,
            "customer": session.customer,
        }

    def build_customer_portal_url(self, payload: Dict[str, str]):
        if payload.get("customer_code"):
            portal_session = stripe.billing_portal.Session.create(
                customer=payload["customer_code"],
                return_url=payload["return_url"],
            )
            return portal_session

        status, customer = self.verify_successful_session(payload)
        if status:
            portal_session = stripe.billing_portal.Session.create(
                customer=customer,
                return_url=payload["return_url"],
            )
            return portal_session

    def construct_event(self, payload: Dict[str, Any]):
        if payload.get("webhook_secret") and payload.get("sig"):
            try:
                event = stripe.Webhook.construct_event(
                    payload["body"], payload["sig"], payload["webhook_secret"]
                )
            except Exception as err:
                raise ValueError(f"Webhook Error: {str(err)}")
            data = event["data"]
            event_type = event["type"]
        else:
            data = payload["body"]["data"]
            event_type = payload["body"]["type"]

        subscription = None
        print("type", event_type)

        if event_type == "checkout.session.completed":
            session = data["object"]
            customer = {}
            if session["customer"]:
                customer = {
                    "id": session["customer"],
                    **session["customer_details"],
                    "customer_code": session["customer"],
                }
            return {
                "event": "charge.success",
                "data": {
                    "id": session["id"],
                    "slug": session["client_reference_id"],
                    "subscription_code": session["subscription"],
                    "customer": customer,
                    "currency": session["currency"],
                    "amount": session["amount_total"] / 100,
                    "kind": session["metadata"].get("kind", "speaking"),
                },
            }
        elif event_type == "invoice.paid":
            invoice = data["object"]
            if invoice["subscription"]:
                rr = stripe.Subscription.retrieve(invoice["subscription"])
                subscription = {
                    "subscription_code": invoice["subscription"],
                    "next_payment_date": datetime.fromtimestamp(
                        rr["current_period_end"]
                    ).isoformat(),
                    "start_date": datetime.fromtimestamp(
                        rr["current_period_start"]
                    ).isoformat(),
                    "status": rr["status"],
                }
            return {
                "event": "invoice.update",
                "data": {
                    "id": invoice["id"],
                    "subscription_code": invoice["subscription"],
                    "customer": {
                        "id": invoice["customer"],
                        "email": invoice["customer_email"],
                        "name": invoice["customer_name"],
                        "phone": invoice["customer_phone"],
                        "customer_code": invoice["customer"],
                    },
                    "transaction": {
                        "reference": invoice["subscription"],
                        "status": (
                            "success" if invoice["status"] == "paid" else "failed"
                        ),
                    },
                    "subscription": subscription,
                    "currency": invoice["currency"],
                    "amount": invoice["amount_paid"],
                },
            }
        elif event_type == "customer.subscription.deleted":
            subscription_deleted = data["object"]
            return {
                "event": "subscription.disable",
                "data": {
                    "subscription_code": subscription_deleted["id"],
                    "customer": {
                        "id": subscription_deleted["customer"],
                        "customer_code": subscription_deleted["customer"],
                    },
                },
            }
        elif event_type == "invoice.payment_failed":
            invoice_failed = data["object"]
            if invoice_failed["subscription"]:
                rr = stripe.Subscription.retrieve(invoice_failed["subscription"])
                subscription = {
                    "subscription_code": invoice_failed["subscription"],
                    "next_payment_date": datetime.fromtimestamp(
                        rr["current_period_end"]
                    ).isoformat(),
                    "start_date": datetime.fromtimestamp(
                        rr["current_period_start"]
                    ).isoformat(),
                    "status": rr["status"],
                }
            return {
                "event": "invoice.payment_failed",
                "data": {
                    "id": invoice_failed["id"],
                    "subscription_code": invoice_failed["subscription"],
                    "customer": {
                        "id": invoice_failed["customer"],
                        "email": invoice_failed["customer_email"],
                        "name": invoice_failed["customer_name"],
                        "phone": invoice_failed["customer_phone"],
                        "customer_code": invoice_failed["customer"],
                    },
                    "subscription": subscription,
                    "currency": invoice_failed["currency"],
                    "next_payment_date": datetime.fromtimestamp(
                        invoice_failed["period_end"]
                    ).isoformat(),
                },
            }
        else:
            return None

    def generate_payment_json(self, payment_request: PaymentJSONType):
        session = self.build_session_url(
            {
                "amount": payment_request["amount"],
                "description": payment_request["processor_info"]["description"],
                "user": {
                    "email": payment_request["user"]["email"],
                    "name": f"{payment_request['user'].get('first_name', '')} {payment_request['user'].get('last_name', '')}",
                    "phone": payment_request["user"]["phone"],
                },
                "session_id": payment_request["order"],
                "success_url": payment_request["success_url"],
                "cancel_url": payment_request["cancel_url"],
                "metadata": payment_request["metadata"],
            },
            mode="payment",
            currency=payment_request["currency"],
        )
        return {
            "processor_info": {"session_id": session["id"]},
            "user_details": {"kind": "stripe", "paymentLink": session["url"]},
        }

    def get_webhook_list(self):
        response = stripe.WebhookEndpoint.list(limit=100)
        return response.data

    def create_webhook(self, url: str):
        webhooks = self.get_webhook_list()
        existing_webhook = next(
            (webhook for webhook in webhooks if webhook.url == url), None
        )
        if existing_webhook:
            return existing_webhook
        response = stripe.WebhookEndpoint.create(
            url=url,
            enabled_events=[
                "charge.failed",
                "charge.succeeded",
                "checkout.session.completed",
                "payment_intent.succeeded",
                "payment_intent.payment_failed",
            ],
        )
        return response


class WebhookType(TypedDict):
    body: Dict[str, str]
    sig: Optional[str]
    webhook_secret: Optional[str]


class Processor:
    def __init__(self, stripe: Dict[str, str]):
        self.stripe = StripeProcessor(
            stripe["secret_key"], stripe["id"], stripe["public_key"]
        )

    def customer_card_portal(self, payload: Dict[str, str]):
        session = self.stripe.build_customer_portal_url(payload)
        return session

    def generate_payment_json(self, payload: PaymentJSONType):
        return self.stripe.generate_payment_json(payload)

    def get_webhook_list(self):
        return self.stripe.get_webhook_list()

    def processWebhook(self, payload: WebhookType, callback):
        event = self.stripe.construct_event(
            {
                "body": payload["body"],
                "sig": payload["sig"],
                "webhook_secret": payload["webhook_secret"],
            }
        )
        if event and event.get("event") == "checkout.session.completed":
            slug = event["data"].get("slug")
            if slug:
                callback(slug)

        return {"event": event}

    def build_transaction_obj(self, **kwargs):
        return self.stripe.build_session_ui_url(**kwargs)


class StripeAPI:
    def __init__(self, django=True, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
        self.transaction_api = Processor(
            dict(secret_key=self.secret_key, id=self.id, public_key=self.public_key)
        )

    def verify_payment(self, code, **kwargs):
        result = self.transaction_api.stripe.verify_successful_session(
            {
                "session_id": code,
            }
        )
        if result["status"] == "success":
            return True, "Successful"
        return False, "Failed", result, None

    def processor_info(self, amount, redirect_url=None, **kwargs):
        return {
            "amount": amount,
            "js_script": "https://js.stripe.com/v3/",
            "key": self.public_key,
            "redirect_url": redirect_url,
            "session_secret": kwargs.get("session_secret"),
        }

    def other_payment_info(self, **kwargs):
        return self.transaction_api.build_transaction_obj(**kwargs)
