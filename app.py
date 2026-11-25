import os

from dotenv import load_dotenv
from flask import Flask, render_template

# keys come from .env here, and from the dashboard on the host
load_dotenv()

app = Flask(__name__)

@app.get("/")
def index():
    return render_template("index.html", merchant_id=os.getenv("TAP_MERCHANT_ID"))

if __name__ == "__main__":
    # debug stays off online, its error page can run code
    app.run(port=int(os.getenv("PORT", "5000")), debug=os.getenv("FLASK_DEBUG") == "1")