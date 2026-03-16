class ErrorMessages:
    """Standardized and domain-specific error messages."""

    # --- Generic Fallbacks ---
    HTTP_400_BAD_REQUEST = "Bad Request: Invalid syntax or client error."
    HTTP_404_NOT_FOUND = "Not found"
    PAGE_NOT_FOUND = "Page not found"

    # --- Domain: Transactions ---
    class Transaction:
        NOT_FOUND = "Transaction not found"
        USER_NOT_OWNER = "Transaction does not belong to user"
        ALREADY_PROCESSED = "This transaction has already been processed."
        INSUFFICIENT_FUNDS = "Insufficient funds to complete this transaction."

    # --- Domain: Users ---
    class User:
        NOT_FOUND = "User not found"
        USERNAME_EXISTS = "Username already exists"
        EMAIL_OR_PHONE_EXISTS = "email/phone already exists"
        EMAIL_ALREADY_EXISTS = "A user with this email address already exists."
        INVALID_CREDENTIALS = "The username or password provided is incorrect."
        ACCOUNT_LOCKED = (
            "This account has been locked due to too many failed login attempts."
        )
