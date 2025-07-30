#! /usr/bin/env python3.6

"""
server.py
Stripe Sample.
Python 3.6 or newer required.
"""
import os
from flask import Flask, jsonify, redirect, request

import stripe

# This test secret API key is a placeholder. Don't include personal details in requests with this key.
# To see your test secret API key embedded in code samples, sign in to your Stripe account.
# You can also find your test secret API key at https://dashboard.stripe.com/test/apikeys.
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

app = Flask(__name__, static_url_path="", static_folder="public")

YOUR_DOMAIN = "http://localhost:4242"


@app.route("/create-checkout-session", methods=["POST"])
def create_checkout_session():
    try:
        session = stripe.checkout.Session.create(
            ui_mode="embedded",
            line_items=[
                {
                    # Provide the exact Price ID (for example, pr_1234) of the product you want to sell
                    "price_data":{
                        "currency": "usd",
                        "unit_amount": 2000,
                        "product_data": {
                            "name": "T-shirt",
                        },
                    },
                    "quantity": 1,
                },
            ],
            mode="payment",
            return_url=YOUR_DOMAIN + "/return.html?session_id={CHECKOUT_SESSION_ID}",
        )
    except Exception as e:
        return str(e)

    return jsonify(clientSecret=session.client_secret)


@app.route("/session-status", methods=["GET"])
def session_status():
    session = stripe.checkout.Session.retrieve(request.args.get("session_id"))

    return jsonify(status=session.status, customer_email=session.customer_details.email)


if __name__ == "__main__":
    app.run(port=4242)
