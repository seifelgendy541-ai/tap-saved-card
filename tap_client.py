import os
import uuid

import requests


class TapError(Exception):
    pass


# every call to Tap goes through here, so the secret key is used in one place
def call_tap(method, path, payload=None):
    try:
        response = requests.request(
            method,
            os.getenv("TAP_BASE_URL") + path,
            json=payload,
            headers={"Authorization": "Bearer " + os.getenv("TAP_SECRET_KEY")},
            timeout=30,
        )
        data = response.json()
    except requests.RequestException:
        raise TapError("Could not reach Tap, please try again.")

    if not response.ok or "errors" in data:
        error = (data.get("errors") or [{}])[0]
        raise TapError(f"Tap error {error.get('code')}: {error.get('description')}")
    return data


def create_charge(token_id, amount, currency, customer, redirect_url):
    # must be new each time, Tap rejects reused references (error 1202)
    ref = uuid.uuid4().hex[:16]

    return call_tap("POST", "/charges", {
        "amount": amount,
        "currency": currency,
        "customer": customer,
        "source": {"id": token_id},
        "redirect": {"url": redirect_url},
        "merchant": {"id": os.getenv("TAP_MERCHANT_ID")},
        "save_card": True,
        "customer_initiated": True,
        "threeDSecure": True,
        "reference": {"transaction": "txn_" + ref, "order": "ord_" + ref},
        "description": "First payment (CIT), saves the card",
    })

def retrieve_charge(charge_id):
    return call_tap("GET", "/charges/" + charge_id)

def create_saved_card_token(card_id, customer_id):
    # a saved card ID can't be charged directly, it needs a fresh token
    return call_tap("POST", "/tokens", {
        "saved_card": {"card_id": card_id, "customer_id": customer_id},
    })


def create_mit_charge(token_id, amount, currency, card, redirect_url):
    ref = uuid.uuid4().hex[:16]

    return call_tap("POST", "/charges", {
        "amount": amount,
        "currency": currency,
        "customer": {"id": card["customer_id"]},
        "source": {"id": token_id},
        "payment_agreement": {"id": card["agreement_id"]},
        "customer_initiated": False,
        "threeDSecure": False,
        "save_card": False,
        "merchant": {"id": os.getenv("TAP_MERCHANT_ID")},
        "redirect": {"url": redirect_url},  # required by the API, even without 3DS
        "reference": {"transaction": "txn_" + ref, "order": "ord_" + ref},
        "description": "Recurring payment (MIT), saved card, no 3DS",
    })