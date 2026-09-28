from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import sqlite3
import secrets
import hashlib
import smtplib
from email.message import EmailMessage
from urllib.parse import quote


app = FastAPI(title="FAISU AI LAB")


# ---------- CORS ----------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- PATHS ----------

BASE_DIR = Path(__file__).resolve().parent
DB = BASE_DIR / "users.db"


# ---------- EMAIL CONFIG ----------

SMTP_EMAIL = "efizanali@gmail.com"

# Yahan apna NEW Gmail App Password paste karo
SMTP_PASSWORD = "srurbjjxcvpbwnib"

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465


# ---------- DATABASE ----------

def db():
    connection = sqlite3.connect(DB)
    connection.row_factory = sqlite3.Row
    return connection


def setup_database():

    connection = db()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            verified INTEGER DEFAULT 0,
            confirmation_token TEXT,
            token_expiry INTEGER
        )
    """)

    # Purani database ho to missing columns automatically add kar do
    cursor.execute("PRAGMA table_info(users)")
    columns = [row["name"] for row in cursor.fetchall()]

    if "verified" not in columns:
        cursor.execute(
            "ALTER TABLE users ADD COLUMN verified INTEGER DEFAULT 0"
        )

    if "confirmation_token" not in columns:
        cursor.execute(
            "ALTER TABLE users ADD COLUMN confirmation_token TEXT"
        )

    if "token_expiry" not in columns:
        cursor.execute(
            "ALTER TABLE users ADD COLUMN token_expiry INTEGER"
        )

    connection.commit()
    connection.close()


setup_database()


# ---------- PASSWORD ----------

def hash_password(password):

    return hashlib.sha256(
        password.encode("utf-8")
    ).hexdigest()


def verify_password(password, stored_hash):

    return hash_password(password) == stored_hash


# ---------- EMAIL ----------

def send_confirmation_email(email, name, token):

    confirmation_link = (
        "http://127.0.0.1:8000/confirm-email?token="
        + quote(token)
    )

    message = EmailMessage()

    message["Subject"] = "Confirm your FAISU AI LAB account"
    message["From"] = SMTP_EMAIL
    message["To"] = email

    message.set_content(
        f"""
Hello {name},

Welcome to FAISU AI LAB.

Please confirm your email address by clicking the link below:

{confirmation_link}

After confirming your email, you can log in to your FAISU AI LAB account.

If you did not create this account, you can ignore this email.

FAISU AI LAB
"""
    )

    with smtplib.SMTP_SSL(
        SMTP_HOST,
        SMTP_PORT,
        timeout=30
    ) as server:

        server.login(
            SMTP_EMAIL,
            SMTP_PASSWORD
        )

        server.send_message(message)


# ---------- HOME ----------

@app.get("/", response_class=HTMLResponse)
def home():

    index_file = BASE_DIR / "index.html"

    if not index_file.exists():

        return """
        <h1>FAISU AI LAB</h1>
        <p>index.html not found.</p>
        """

    return index_file.read_text(
        encoding="utf-8"
    )


# ---------- HEALTH ----------

@app.get("/health")
def health():

    return {
        "status": "ok",
        "app": "FAISU AI LAB"
    }


# ---------- SIGNUP ----------

@app.post("/signup")
def signup(
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...)
):

    name = name.strip()
    email = email.strip().lower()

    if not name:

        return {
            "error": "Please enter your name."
        }

    if len(password) < 6:

        return {
            "error": "Password must be at least 6 characters."
        }

    if "@" not in email:

        return {
            "error": "Please enter a valid email address."
        }

    connection = db()
    cursor = connection.cursor()

    cursor.execute(
        "SELECT * FROM users WHERE email = ?",
        (email,)
    )

    existing_user = cursor.fetchone()

    # Agar account pehle se verified hai
    if existing_user and existing_user["verified"] == 1:

        connection.close()

        return {
            "error": "An account with this email already exists."
        }

    # New confirmation token
    token = secrets.token_urlsafe(32)

    # Token 15 minutes ke liye valid
    import time

    token_expiry = int(time.time()) + (15 * 60)

    password_hash = hash_password(password)

    try:

        if existing_user:

            cursor.execute(
                """
                UPDATE users
                SET name = ?,
                    password = ?,
                    verified = 0,
                    confirmation_token = ?,
                    token_expiry = ?
                WHERE email = ?
                """,
                (
                    name,
                    password_hash,
                    token,
                    token_expiry,
                    email
                )
            )

        else:

            cursor.execute(
                """
                INSERT INTO users
                (
                    name,
                    email,
                    password,
                    verified,
                    confirmation_token,
                    token_expiry
                )
                VALUES (?, ?, ?, 0, ?, ?)
                """,
                (
                    name,
                    email,
                    password_hash,
                    token,
                    token_expiry
                )
            )

        connection.commit()

    except sqlite3.IntegrityError:

        connection.close()

        return {
            "error": "This email is already registered."
        }

    connection.close()

   # Confirmation email bhejo
    try:
        send_confirmation_email(
            email,
            name,
            token
        )
    except Exception as error:
        print("EMAIL ERROR:", repr(error))
        return {
            "error": f"EMAIL ERROR: {repr(error)}"
        }

    return {
        "success": True,
        "message": "Confirmation link your Gmail par bhej diya gaya."
    }

# ---------- CONFIRM EMAIL ----------

@app.get("/confirm-email")
def confirm_email(token: str):

    import time

    connection = db()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT * FROM users
        WHERE confirmation_token = ?
        """,
        (token,)
    )

    user = cursor.fetchone()

    if not user:

        connection.close()

        return HTMLResponse(
            """
            <!DOCTYPE html>
            <html>
            <head>
                <title>FAISU AI LAB</title>
                <style>
                    body{
                        background:#05070d;
                        color:white;
                        font-family:Arial,sans-serif;
                        display:flex;
                        align-items:center;
                        justify-content:center;
                        min-height:100vh;
                        text-align:center;
                    }

                    .box{
                        background:#101522;
                        padding:40px;
                        border-radius:18px;
                        max-width:450px;
                    }

                    h1{
                        color:#7c5cff;
                    }
                </style>
            </head>

            <body>

                <div class="box">

                    <h1>Invalid Link</h1>

                    <p>
                        This confirmation link is invalid.
                    </p>

                </div>

            </body>
            </html>
            """
        )

    if user["token_expiry"] is None or int(user["token_expiry"]) < int(time.time()):

        connection.close()

        return HTMLResponse(
            """
            <!DOCTYPE html>
            <html>
            <head>
                <title>FAISU AI LAB</title>
                <style>
                    body{
                        background:#05070d;
                        color:white;
                        font-family:Arial,sans-serif;
                        display:flex;
                        align-items:center;
                        justify-content:center;
                        min-height:100vh;
                        text-align:center;
                    }

                    .box{
                        background:#101522;
                        padding:40px;
                        border-radius:18px;
                        max-width:450px;
                    }

                    h1{
                        color:#ff6b6b;
                    }
                </style>
            </head>

            <body>

                <div class="box">

                    <h1>Link Expired</h1>

                    <p>
                        This confirmation link has expired.
                        Please signup again.
                    </p>

                </div>

            </body>
            </html>
            """
        )

    cursor.execute(
        """
        UPDATE users
        SET verified = 1,
            confirmation_token = NULL,
            token_expiry = NULL
        WHERE id = ?
        """,
        (user["id"],)
    )

    connection.commit()
    connection.close()

    # Confirmation ke baad website par wapas
    return RedirectResponse(
        url="/?verified=1",
        status_code=303
    )


# ---------- LOGIN ----------

@app.post("/login")
def login(
    email: str = Form(...),
    password: str = Form(...)
):

    email = email.strip().lower()

    connection = db()
    cursor = connection.cursor()

    cursor.execute(
        "SELECT * FROM users WHERE email = ?",
        (email,)
    )

    user = cursor.fetchone()

    connection.close()

    if not user:

        return {
            "error": "Invalid email or password."
        }

    if not verify_password(
        password,
        user["password"]
    ):

        return {
            "error": "Invalid email or password."
        }

    if user["verified"] != 1:

        return {
            "error": "Please confirm your email before login."
        }

    return {
        "success": True,
        "message": "Login successful.",
        "name": user["name"],
        "email": user["email"]
    }