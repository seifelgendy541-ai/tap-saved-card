import os
import json

from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request
import tap_client
import webhook

# keys come from .env here, and from the dashboard on the host
load_dotenv()

app = Flask(__name__)
# the price lives on the server so the browser can't change it
AMOUNT = 10.00
CURRENCY = "KWD"
BASE_URL = os.getenv("BASE_URL")

# demo customer; a real shop would use the logged-in user's details
CUSTOMER = {
    "first_name": "Test",
    "last_name": "Customer",
    "email": "test.customer@example.com",
    "phone": {"country_code": 20, "number": 1000000000},
}

# a small file instead of a database, demo only
def load_data():
    try:
        with open("data.json") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}


def save_data(data):
    with open("data.json", "w") as file:
        json.dump(data, file, indent=2)

# paid only if Tap says CAPTURED, for the amount we asked for
def is_paid(charge):
    return (
        charge.get("status") == "CAPTURED"
        and charge.get("amount") == AMOUNT
        and charge.get("currency") == CURRENCY
    )


# plain words for the customer, plus Tap's code for support
def failure_message(charge):
    reply = charge.get("response", {})
    return (
        f"Payment failed, please try another card. "
        f"Status {charge.get('status')}, Tap code {reply.get('code')}: {reply.get('message')}"
    )

@app.get("/")
def index():
    # public values only, never the secret key
    tap_config = {
        "publicKey": os.getenv("TAP_PUBLIC_KEY"),
        "merchantId": os.getenv("TAP_MERCHANT_ID"),
        "amount": AMOUNT,
        "currency": CURRENCY,
    }
    data = load_data()
    message = data.pop("message", None)  # show a result only once
    save_data(data)
    return render_template(
        "index.html",
        tap_config=tap_config,
        message=message,
        card=data.get("card"),
        cit_charge_id=data.get("cit_charge_id"),
        mit_charge_id=data.get("mit_charge_id"),
    )

@app.post("/pay")
def pay():
    data = request.get_json(silent=True) or {}
    token_id = str(data.get("token", ""))

    if not token_id.startswith("tok_"):
        return jsonify(error="Missing card token"), 400

    try:
        charge = tap_client.create_charge(
            token_id, AMOUNT, CURRENCY, CUSTOMER, BASE_URL + "/redirect"
        )
    except tap_client.TapError as error:
        return jsonify(error=str(error)), 502

    print("Charge created:", charge.get("id"), charge.get("status"))

    url = charge.get("transaction", {}).get("url")
    if not url:
        return jsonify(error=failure_message(charge)), 402

    # remember which charge we created, so /redirect accepts only this one
    data = load_data()
    data["pending_charge_id"] = charge["id"]
    save_data(data)

    return jsonify(url=url)

@app.get("/redirect")
def redirect_page():
    charge_id = request.args.get("tap_id", "")
    data = load_data()

    # only accept the charge this server created
    if not charge_id or charge_id != data.get("pending_charge_id"):
        return "Unknown charge", 400

    try:
        # landing here proves nothing, so ask Tap for the real status
        charge = tap_client.retrieve_charge(charge_id)
    except tap_client.TapError as error:
        data["message"] = str(error)
        save_data(data)
        return redirect("/")

    if not is_paid(charge):
        data["message"] = failure_message(charge)
    else:
        card = charge.get("card", {})
        saved = {
            "customer_id": charge.get("customer", {}).get("id"),
            "card_id": card.get("id"),
            "agreement_id": charge.get("payment_agreement", {}).get("id"),
            "brand": card.get("brand"),
            "last_four": card.get("last_four"),
        }
        data["cit_charge_id"] = charge_id
        data.pop("mit_charge_id", None)  # it belonged to the previous card

        if saved["customer_id"] and saved["card_id"] and saved["agreement_id"]:
            data["card"] = saved
            data["message"] = "Payment captured and card saved."
        else:
            data["message"] = "Payment captured, but Tap did not return all saved card IDs."

    save_data(data)
    return redirect("/")

@app.post("/pay-saved")
def pay_saved():
    data = load_data()
    card = data.get("card")

    # the browser only picks a card, every ID we send comes from our own file
    if not card or request.form.get("card_id") != card["card_id"]:
        return "Unknown card", 400

    try:
        token = tap_client.create_saved_card_token(card["card_id"], card["customer_id"])
        charge = tap_client.create_mit_charge(
            token["id"], AMOUNT, CURRENCY, card, BASE_URL + "/redirect"
        )
        # confirm with Tap before calling it paid
        charge = tap_client.retrieve_charge(charge["id"])
    except tap_client.TapError as error:
        data["message"] = str(error)
    else:
        print("MIT:", charge["id"], charge.get("status"), "3DS:", charge.get("threeDSecure"))
        if is_paid(charge):
            data["mit_charge_id"] = charge["id"]
            data["message"] = "Recurring payment captured, without 3DS."
        else:
            data["message"] = failure_message(charge)

    save_data(data)
    return redirect("/")

@app.post("/webhook")
def tap_webhook():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return "Bad payload", 400

    valid = webhook.is_valid(payload, request.headers.get("hashstring", ""))

    # log what Tap sends: the file, plus the host's log viewer
    with open("webhooks.log", "a") as file:
        file.write(json.dumps({"hash_valid": valid, "payload": payload}) + "\n")
    print("Webhook:", payload.get("id"), payload.get("status"), "hash valid:", valid)
    print(json.dumps(payload))

    if not valid:
        return "Invalid hashstring", 401
    return "OK", 200

if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG") == "1"
    # debug stays private to this computer; without debug, accept outside connections
    host = "127.0.0.1" if debug else "0.0.0.0"
    app.run(host=host, port=int(os.getenv("PORT", "5000")), debug=debug)