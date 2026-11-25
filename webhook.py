import hashlib
import hmac
import os

# these currencies use 3 decimals, and the hash must match exactly
THREE_DECIMALS = ("BHD", "KWD", "OMR", "JOD")


def format_amount(amount, currency):
    decimals = 3 if currency in THREE_DECIMALS else 2
    return f"{float(amount):.{decimals}f}"


# field order comes from Tap's docs, with no separators
def build_charge_string(charge):
    reference = charge.get("reference", {})
    return (
        f"x_id{charge.get('id', '')}"
        f"x_amount{format_amount(charge.get('amount', 0), charge.get('currency'))}"
        f"x_currency{charge.get('currency', '')}"
        f"x_gateway_reference{reference.get('gateway') or ''}"
        f"x_payment_reference{reference.get('payment') or ''}"
        f"x_status{charge.get('status', '')}"
        f"x_created{charge.get('transaction', {}).get('created', '')}"
    )


def is_valid(charge, received_hash):
    expected = hmac.new(
        os.getenv("TAP_SECRET_KEY").encode(),
        build_charge_string(charge).encode(),
        hashlib.sha256,
    ).hexdigest()
    # constant-time compare, so response timing doesn't leak the hash
    return hmac.compare_digest(expected.encode(), received_hash.encode())