"""Rule-based banking chatbot logic (intent + entity detection, multi-turn slots)."""
import re

BANK_NAME = "Sample Bank"

# ---------- INTENT TABLE: intent -> keywords/phrases ----------
INTENT_KEYWORDS = {
    "GREETING":    ["hi", "hello", "hey", "good morning", "good afternoon", "good evening", "namaste"],
    "GOODBYE":     ["bye", "goodbye", "thanks", "thank you", "exit", "quit", "see you", "that is all"],
    "ACCOUNT":     ["account", "balance", "minimum balance", "interest", "interest rate", "open account", "deposit"],
    "CARD":        ["card", "block", "card limit", "credit limit", "annual fee", "apply for card", "lost card"],
    "TRANSACTION": ["transaction", "transfer", "payment", "send money", "pay", "withdraw", "withdrawal",
                    "daily limit", "failed", "refund", "charges"],
    "BRANCH":      ["branch", "ifsc", "nearest", "working hours", "timing", "timings", "location", "visit"],
    "SERVICE":     ["service", "request", "cheque book", "passbook", "statement", "loan",
                    "pin reset", "reset pin", "change address", "update address"],
    "COMPLAINT":   ["complaint", "complain", "unhappy", "worst", "poor service", "not working",
                    "escalate", "fraud", "deducted", "problem", "issue", "angry"],
}

# Priority used when two intents have the same score (left = higher priority)
INTENT_PRIORITY = ["COMPLAINT", "GOODBYE", "GREETING", "CARD", "TRANSACTION",
                   "ACCOUNT", "BRANCH", "SERVICE"]

# ---------- ENTITY TABLE: entity type -> {canonical value: [synonyms]} ----------
ENTITIES = {
    "account_type": {
        "savings":           ["savings", "saving"],
        "current":           ["current"],
        "salary":            ["salary"],
        "fixed deposit":     ["fixed deposit", "fd"],
        "recurring deposit": ["recurring deposit", "rd"],
    },
    "card_type": {
        "debit":   ["debit", "atm card"],
        "credit":  ["credit"],
        "prepaid": ["prepaid", "forex card"],
    },
    "transaction_type": {
        "UPI":            ["upi", "gpay", "phonepe"],
        "NEFT":           ["neft"],
        "RTGS":           ["rtgs"],
        "IMPS":           ["imps"],
        "ATM withdrawal": ["atm withdrawal", "withdraw", "withdrawal", "atm"],
    },
    "branch": {
        "Bengaluru": ["bengaluru", "bangalore"],
        "Mumbai":    ["mumbai", "bombay"],
        "Delhi":     ["delhi"],
        "Chennai":   ["chennai", "madras"],
        "Hyderabad": ["hyderabad"],
    },
    "service": {
        "cheque book":       ["cheque book", "checkbook", "cheque"],
        "passbook":          ["passbook"],
        "account statement": ["statement"],
        "loan enquiry":      ["loan"],
        "PIN reset":         ["pin reset", "reset pin", "forgot pin", "change pin"],
        "address change":    ["change address", "update address", "address change"],
    },
}

# If an intent is not found but an entity is, infer the intent from the entity type
ENTITY_TO_INTENT = {
    "account_type": "ACCOUNT", "card_type": "CARD", "transaction_type": "TRANSACTION",
    "branch": "BRANCH", "service": "SERVICE",
}

# Slot each intent needs before the bot can answer (used for multi-turn follow-ups)
REQUIRED_SLOT = {
    "ACCOUNT": "account_type", "CARD": "card_type", "TRANSACTION": "transaction_type",
    "BRANCH": "branch", "SERVICE": "service",
}

FOLLOW_UP_QUESTION = {
    "ACCOUNT":     "Which account type are you asking about? (savings / current / salary / fixed deposit / recurring deposit)",
    "CARD":        "Which card type do you mean? (debit / credit / prepaid)",
    "TRANSACTION": "Which transaction type? (UPI / NEFT / RTGS / IMPS / ATM withdrawal)",
    "BRANCH":      "Which city's branch are you looking for? (Bengaluru / Mumbai / Delhi / Chennai / Hyderabad)",
    "SERVICE":     "Which service do you need? (cheque book / passbook / account statement / loan enquiry / PIN reset / address change)",
}

# ---------- SMALL SAMPLE CATALOGUE (illustrative data only) ----------
ACCOUNT_INFO = {
    "savings":           "Savings account: minimum balance Rs 2,000, interest about 3% p.a., free debit card, zero-balance option for basic variant.",
    "current":           "Current account: built for businesses, minimum balance Rs 10,000, unlimited transactions, no interest.",
    "salary":            "Salary account: zero minimum balance while salary is credited, free debit card, free NEFT/IMPS.",
    "fixed deposit":     "Fixed deposit: lock in money for 7 days to 10 years, interest about 6.5% p.a., minimum deposit Rs 5,000.",
    "recurring deposit": "Recurring deposit: save a fixed amount monthly for 6 months to 10 years, interest about 6.25% p.a.",
}
CARD_INFO = {
    "debit":   "Debit card: linked to your account, daily ATM limit Rs 40,000, annual fee Rs 200, contactless enabled.",
    "credit":  "Credit card: credit limit set after eligibility check, interest-free period up to 45 days, annual fee Rs 500 (waived on Rs 50,000 yearly spend).",
    "prepaid": "Prepaid/forex card: load money in advance, good for travel, no credit risk, reload via net banking.",
}
TRANSACTION_INFO = {
    "UPI":            "UPI: instant 24x7 transfers, usual limit Rs 1,00,000 per day, no charges for normal payments.",
    "NEFT":           "NEFT: available 24x7, settled in batches, no minimum amount, usually free for online transfers.",
    "RTGS":           "RTGS: for high-value transfers (minimum Rs 2,00,000), real-time settlement.",
    "IMPS":           "IMPS: instant transfers 24x7 up to Rs 5,00,000, small service charge may apply.",
    "ATM withdrawal": "ATM withdrawal: 5 free transactions a month at own-bank ATMs, small fee beyond that.",
}
BRANCH_INFO = {
    "Bengaluru": "Bengaluru - MG Road Branch, Mon-Fri 10:00-16:00, Sat 10:00-14:00 (sample IFSC: SAMP0000101).",
    "Mumbai":    "Mumbai - Fort Branch, Mon-Fri 10:00-16:00, Sat 10:00-14:00 (sample IFSC: SAMP0000202).",
    "Delhi":     "Delhi - Connaught Place Branch, Mon-Fri 10:00-16:00, Sat 10:00-14:00 (sample IFSC: SAMP0000303).",
    "Chennai":   "Chennai - Anna Salai Branch, Mon-Fri 10:00-16:00, Sat 10:00-14:00 (sample IFSC: SAMP0000404).",
    "Hyderabad": "Hyderabad - Banjara Hills Branch, Mon-Fri 10:00-16:00, Sat 10:00-14:00 (sample IFSC: SAMP0000505).",
}
SERVICE_INFO = {
    "cheque book":       "Cheque book: request via net banking or branch; delivered in 5-7 working days.",
    "passbook":          "Passbook: collect or update at your home branch, or request a new one with a signed form.",
    "account statement": "Account statement: download from net banking/mobile app, or ask the branch for a printed copy.",
    "loan enquiry":      "Loan enquiry: personal, home and vehicle loans available. Rates depend on eligibility; visit a branch or apply online.",
    "PIN reset":         "PIN reset: use the mobile app (Cards > Set PIN) or any bank ATM. Never share your PIN or OTP with anyone.",
    "address change":    "Address change: submit address proof at the branch or upload through net banking.",
}

SAFETY_NOTE = "(Please do not share PIN, OTP, passwords or card/account numbers in this chat.)"

FALLBACK = ("Sorry, I did not understand that. I can help with accounts, cards, transactions, "
            "branches, service requests and complaints. Try: 'credit card details' or 'branch in Mumbai'.")


# ---------- NLP helpers ----------
def clean_text(text):
    """Lowercase and remove punctuation so matching is easier."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text)


def contains(text, phrase):
    """True if the whole word/phrase appears in the text."""
    return re.search(r"\b" + re.escape(phrase) + r"\b", text) is not None


def extract_entities(text):
    """Return a dict like {'card_type': 'credit'} for every entity found."""
    found = {}
    for entity_type, values in ENTITIES.items():
        for canonical, synonyms in values.items():
            if any(contains(text, s) for s in synonyms):
                found[entity_type] = canonical
                break
    return found


def detect_intent(text):
    """Score each intent by matched keywords; return (intent, score) or (None, 0)."""
    scores = {}
    for intent, keywords in INTENT_KEYWORDS.items():
        score = sum(1 for k in keywords if contains(text, k))
        if intent == "COMPLAINT":
            score *= 2  # complaints get extra weight so they are never missed
        if score > 0:
            scores[intent] = score
    if not scores:
        return None, 0
    best = max(scores.values())
    tied = [i for i in scores if scores[i] == best]
    for intent in INTENT_PRIORITY:  # break ties using priority order
        if intent in tied:
            return intent, best
    return None, 0


# ---------- Dialog manager ----------
def new_state():
    """Conversation memory: what we are waiting for, retries, and complaint ticket counter.

    The ticket counter lives in the per-user state (not a global) so each
    Streamlit session gets its own numbering.
    """
    return {"pending": None, "retries": 0, "ticket": 1000}


def build_answer(intent, entities):
    """Create the final answer once we have the needed entity."""
    if intent == "ACCOUNT":
        return ACCOUNT_INFO[entities["account_type"]]
    if intent == "CARD":
        return CARD_INFO[entities["card_type"]]
    if intent == "TRANSACTION":
        return TRANSACTION_INFO[entities["transaction_type"]]
    if intent == "BRANCH":
        return BRANCH_INFO[entities["branch"]]
    if intent == "SERVICE":
        return SERVICE_INFO[entities["service"]]


def get_reply(message, state):
    text = clean_text(message)
    entities = extract_entities(text)
    intent, _ = detect_intent(text)

    # Allow the user to cancel a pending question
    if state["pending"] and contains(text, "never mind"):
        state["pending"], state["retries"] = None, 0
        return "No problem. What else can I help you with?"

    # ---- MULTI-TURN: we are waiting for an answer to our follow-up question ----
    if state["pending"]:
        pending_intent = state["pending"]
        slot = REQUIRED_SLOT[pending_intent]
        if slot in entities:  # user answered the follow-up
            state["pending"], state["retries"] = None, 0
            return build_answer(pending_intent, entities)
        if intent in (None, pending_intent):  # answer not understood
            state["retries"] += 1
            if state["retries"] >= 2:
                state["pending"], state["retries"] = None, 0
                return "I could not get that. Let's start over - " + FALLBACK
            return "Sorry, I did not catch that. " + FOLLOW_UP_QUESTION[pending_intent]
        state["pending"], state["retries"] = None, 0  # user changed topic -> continue below

    # Infer the intent from an entity when no keyword was found (e.g. just "UPI")
    if intent is None and entities:
        intent = ENTITY_TO_INTENT[next(iter(entities))]

    # ---- Single-turn intents ----
    if intent is None:
        return FALLBACK
    if intent == "GREETING":
        return f"Hello! Welcome to {BANK_NAME}. How can I help you today?"
    if intent == "GOODBYE":
        return "Thank you for banking with us. Have a great day! Goodbye."
    if intent == "COMPLAINT":
        state["ticket"] += 1
        ref = f"CMP{state['ticket']}"
        return (f"I am sorry for the trouble. Your sample complaint reference is {ref}. "
                f"A support officer will contact you within 2 working days. {SAFETY_NOTE}")

    # Special case: blocking a card does not need the card type
    if intent == "CARD" and contains(text, "block"):
        return ("To block a card: use the mobile app (Cards > Block) or call the 24x7 helpline "
                "(sample: 1800-000-000). " + SAFETY_NOTE)

    # ---- Intents that need an entity ----
    slot = REQUIRED_SLOT[intent]
    if slot in entities:
        return build_answer(intent, entities)
    state["pending"] = intent  # ask a follow-up question
    return FOLLOW_UP_QUESTION[intent]
