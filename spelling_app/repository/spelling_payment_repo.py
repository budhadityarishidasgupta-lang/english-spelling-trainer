from sqlalchemy import text


def payment_exists(db, paypal_payment_id: str) -> bool:
    q = "SELECT 1 FROM spelling_payments WHERE paypal_payment_id = :pid"
    r = db.execute(text(q), {"pid": paypal_payment_id}).fetchone()
    return r is not None


def record_payment(db, user_email: str, paypal_payment_id: str, paypal_button_id: str, status: str = "COMPLETED") -> None:
    q = """
      INSERT INTO spelling_payments (user_email, paypal_payment_id, paypal_button_id, status, paid_at)
      VALUES (:email, :pid, :bid, :status, CURRENT_TIMESTAMP)
    """
    db.execute(text(q), {"email": user_email, "pid": paypal_payment_id, "bid": paypal_button_id, "status": status})
    db.commit()
