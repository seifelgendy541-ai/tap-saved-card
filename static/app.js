const config = JSON.parse(document.getElementById("tap-config").textContent);
const payButton = document.getElementById("pay-button");
const message = document.getElementById("message");

const { renderTapCard, tokenize, Theme, Locale, Edges, Direction } = window.CardSDK;

// runs once Tap has turned the card into a token
async function sendToken(token) {
  payButton.disabled = true;
  message.textContent = "Processing...";

  try {
    const response = await fetch("/pay", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token: token.id }),
    });
    const result = await response.json();

    if (result.url) {
      // go to Tap's 3DS page
      window.location.href = result.url;
      return;
    }
    message.textContent = result.error;
  } catch (error) {
    message.textContent = "Could not reach the server, please try again.";
  }
  payButton.disabled = false;
}

renderTapCard("card-sdk-id", {
  publicKey: config.publicKey,
  merchant: { id: config.merchantId },
  transaction: { amount: config.amount, currency: config.currency },
  acceptance: { supportedBrands: ["VISA", "MASTERCARD"], supportedCards: "ALL" },
  fields: { cardHolder: true },
  addons: { loader: true, saveCard: false, displayPaymentBrands: true },
  // docs say optional, but the form crashes without it
  interface: {
    locale: Locale.EN,
    theme: Theme.LIGHT,
    edges: Edges.CURVED,
    direction: Direction.LTR,
  },
  onError: (error) => {
    console.error(error);
    message.textContent = "Please check your card details.";
  },
  onSuccess: sendToken,
});

payButton.addEventListener("click", () => tokenize());