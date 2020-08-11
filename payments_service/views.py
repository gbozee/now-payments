import typing

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route, Mount
from starlette.requests import Request
from starlette.middleware import Middleware
from starlette.background import BackgroundTask
from starlette.middleware.cors import CORSMiddleware
from payments_service import service
from payments_service import ravepay_views


def home(request: Request):
    return JSONResponse({"hello": "world"})


middlewares = [
    Middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_headers=["*"],
        allow_methods=["*"],
        allow_credentials=True,
    )
]

routes = [
    Route("/", home),
    # Route("/credentials", payment_credentials),
    Route("/webhook", ravepay_views.webhook_callback, methods=["POST"]),
    Route("/verify-payment/{identifier}", ravepay_views.verify_payment),
    Route(
        "/generate-account-no/{identifier}",
        ravepay_views.generate_payment_account_no,
        methods=["POST"],
    ),
    Route(
        "/build-payment-info/{identifier}",
        ravepay_views.client_payment_object,
        methods=["POST"],
    ),
    Mount("/ravepay", routes=ravepay_views.routes),
]

app = Starlette(middleware=middlewares, routes=routes)
