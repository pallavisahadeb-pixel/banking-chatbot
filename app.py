"""Rule-based banking chatbot logic (intent + entity detection, multi-turn slots)."""
import base64
import re

import streamlit as st

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


# =====================================================================
#                          STREAMLIT UI
# =====================================================================
st.set_page_config(page_title=f"{BANK_NAME} Assistant", page_icon="🏦", layout="wide")

WELCOME = "Hello! Ask me about accounts, cards, transactions, branches, services or complaints."

SAMPLE_PROMPTS = [
    "Tell me about savings account",
    "I want to know about a card",
    "What are the branch timings?",
    "My UPI payment failed and money was deducted",
    "How do I block my card?",
    "I need a cheque book",
]

PAGES = ["🏠 Home", "💬 Chat", "⚡ Quick Services", "📝 Complaint Form", "🔬 NLP Playground"]


# ---------- Images: SVGs generated in code, so no image files are needed ----------
def svg_img(svg, radius=14):
    b64 = base64.b64encode(svg.encode("utf-8")).decode()
    return (f'<img src="data:image/svg+xml;base64,{b64}" '
            f'style="width:100%;border-radius:{radius}px;" />')


def hero_svg():
    cols = "".join(f'<rect x="{x}" y="55" width="20" height="85"/>' for x in (16, 58, 100, 142, 184))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 230">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
<stop offset="0" stop-color="#0f3d91"/><stop offset="1" stop-color="#1fa2ff"/></linearGradient></defs>
<rect width="900" height="230" fill="url(#g)"/>
<g fill="#ffffff" opacity="0.92" transform="translate(640,35)">
<polygon points="110,0 220,45 0,45"/>{cols}
<rect x="0" y="145" width="220" height="14"/><rect x="-10" y="159" width="240" height="12"/></g>
<text x="50" y="105" font-family="sans-serif" font-size="44" font-weight="bold" fill="#fff">{BANK_NAME} Assistant</text>
<text x="50" y="145" font-family="sans-serif" font-size="20" fill="#e8f3ff">Ask about accounts, cards, transfers, branches and more</text>
<rect x="50" y="165" width="330" height="34" rx="17" fill="#ffffff" opacity="0.2"/>
<text x="68" y="188" font-family="sans-serif" font-size="16" fill="#fff">Rule-based NLP  |  Multi-turn dialog</text>
</svg>"""


def feature_svg(emoji, title, sub, c1, c2):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 170">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
<stop offset="0" stop-color="{c1}"/><stop offset="1" stop-color="{c2}"/></linearGradient></defs>
<rect width="300" height="170" fill="url(#g)"/>
<circle cx="250" cy="40" r="70" fill="#fff" opacity="0.12"/>
<text x="24" y="85" font-size="52">{emoji}</text>
<text x="24" y="124" font-family="sans-serif" font-size="22" font-weight="bold" fill="#fff">{title}</text>
<text x="24" y="148" font-family="sans-serif" font-size="13" fill="#fff" opacity="0.9">{sub}</text>
</svg>"""


def flow_svg():
    boxes = [
        (20, "1  You type", "any banking question", "#e3f2fd", "#1565c0"),
        (330, "2  NLP analysis", "intent + entities found", "#fff3e0", "#e65100"),
        (640, "3  Smart reply", "answer or follow-up", "#e8f5e9", "#2e7d32"),
    ]
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 200">',
             '<rect width="900" height="200" fill="#f7f9fc"/>']
    for x, t, s, bg, fg in boxes:
        parts.append(f'<rect x="{x}" y="40" width="240" height="120" rx="16" fill="{bg}" stroke="{fg}" stroke-width="2"/>')
        parts.append(f'<text x="{x + 20}" y="90" font-family="sans-serif" font-size="24" font-weight="bold" fill="{fg}">{t}</text>')
        parts.append(f'<text x="{x + 20}" y="124" font-family="sans-serif" font-size="16" fill="#444">{s}</text>')
    for x in (268, 578):
        parts.append(f'<polygon points="{x},85 {x + 40},100 {x},115" fill="#90a4ae"/>')
    parts.append("</svg>")
    return "".join(parts)


# ---------- Session state ----------
def reset_chat():
    st.session_state.messages = [{"role": "assistant", "content": WELCOME}]
    st.session_state.state = new_state()
    st.session_state.last_analysis = None


def init_session():
    st.session_state.setdefault("tickets", [])
    if "messages" not in st.session_state:
        reset_chat()


def analyze(text):
    cleaned = clean_text(text)
    intent, score = detect_intent(cleaned)
    return {"cleaned": cleaned, "intent": intent or "NONE", "score": score,
            "entities": extract_entities(cleaned)}


def send_message(user_text):
    analysis = analyze(user_text)
    reply = get_reply(user_text, st.session_state.state)
    name = st.session_state.get("user_name", "").strip()
    if name and analysis["intent"] == "GREETING" and reply.startswith("Hello!"):
        reply = reply.replace("Hello!", f"Hello {name}!", 1)
    st.session_state.messages.append({"role": "user", "content": user_text})
    st.session_state.messages.append({"role": "assistant", "content": reply, "meta": analysis})
    st.session_state.last_analysis = analysis


def show_analysis(a):
    c1, c2, c3 = st.columns(3)
    c1.metric("Intent", a["intent"])
    c2.metric("Keyword score", a["score"])
    c3.metric("Entities found", len(a["entities"]))
    st.caption(f"Cleaned text: `{a['cleaned']}`")
    if a["entities"]:
        st.json(a["entities"])
    else:
        st.caption("No entities found in this message.")


# ---------- Pages ----------
def page_home():
    st.markdown(svg_img(hero_svg(), 18), unsafe_allow_html=True)
    st.write("")
    n_user = sum(1 for m in st.session_state.messages if m["role"] == "user")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Intents understood", len(INTENT_KEYWORDS))
    m2.metric("Entity types", len(ENTITIES))
    m3.metric("Messages you sent", n_user)
    m4.metric("Complaints logged", len(st.session_state.tickets))

    st.subheader("What can this assistant do?")
    cards = [
        ("🏦", "Accounts", "Savings, current, FD, RD", "#0f3d91", "#1fa2ff"),
        ("💳", "Cards", "Debit, credit, prepaid, block", "#6a1b9a", "#ab47bc"),
        ("🔁", "Transfers", "UPI, NEFT, RTGS, IMPS", "#00695c", "#26a69a"),
        ("📍", "Branches", "Timings and IFSC by city", "#e65100", "#ffa726"),
        ("🧾", "Services", "Cheque book, passbook, loans", "#283593", "#5c6bc0"),
        ("🛠️", "Complaints", "Get a reference number", "#b71c1c", "#ef5350"),
    ]
    for row in (cards[:3], cards[3:]):
        cols = st.columns(3)
        for col, (e, t, s, c1, c2) in zip(cols, row):
            col.markdown(svg_img(feature_svg(e, t, s, c1, c2)), unsafe_allow_html=True)
        st.write("")

    st.subheader("How it works")
    st.markdown(svg_img(flow_svg()), unsafe_allow_html=True)
    st.info("Use the sidebar to open the **Chat**, try the **Quick Services** input boxes, "
            "file a **Complaint**, or poke at the NLP in the **Playground**.")


def page_chat():
    st.subheader("💬 Chat with the assistant")
    st.caption("Please do not share PIN, OTP, passwords or card/account numbers in this chat.")

    cols = st.columns(3)
    for i, p in enumerate(SAMPLE_PROMPTS):
        if cols[i % 3].button(p, key=f"sample_{i}", use_container_width=True):
            st.session_state.queued = p

    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
            if m.get("meta"):
                with st.expander("🔍 NLP analysis of the previous message"):
                    show_analysis(m["meta"])

    pending = st.session_state.state["pending"]
    if pending:
        st.info(f"The bot is waiting for: **{REQUIRED_SLOT[pending]}** "
                "(type 'never mind' to cancel).")

    user_input = st.chat_input("Type your message...")
    if "queued" in st.session_state:
        user_input = st.session_state.pop("queued")
    if user_input:
        send_message(user_input)
        st.rerun()


def info_picker(label, table):
    choice = st.selectbox(label, list(table.keys()), key=f"pick_{label}")
    st.success(table[choice])


def emi_calculator():
    c1, c2, c3 = st.columns(3)
    amount = c1.number_input("Loan amount (Rs)", min_value=10000, max_value=50000000,
                             value=500000, step=10000)
    rate = c2.number_input("Interest rate (% p.a.)", min_value=0.0, max_value=30.0,
                           value=9.5, step=0.1)
    years = c3.slider("Tenure (years)", 1, 30, 5)
    n = years * 12
    r = rate / 12 / 100
    emi = amount / n if r == 0 else amount * r * (1 + r) ** n / ((1 + r) ** n - 1)
    total = emi * n
    k1, k2, k3 = st.columns(3)
    k1.metric("Monthly EMI", f"Rs {emi:,.0f}")
    k2.metric("Total interest", f"Rs {total - amount:,.0f}")
    k3.metric("Total payable", f"Rs {total:,.0f}")
    import pandas as pd
    st.bar_chart(pd.DataFrame({"Rs": [amount, total - amount]}, index=["Principal", "Interest"]))
    st.caption("Illustrative calculation only, not a loan offer.")


def page_quick():
    st.subheader("⚡ Quick Services")
    st.caption("Pick an option from the input boxes instead of typing. All data is sample data.")
    tabs = st.tabs(["🏦 Accounts", "💳 Cards", "🔁 Transfers", "📍 Branches", "🧾 Services", "🧮 Loan EMI"])
    with tabs[0]:
        info_picker("Account type", ACCOUNT_INFO)
    with tabs[1]:
        info_picker("Card type", CARD_INFO)
    with tabs[2]:
        info_picker("Transfer type", TRANSACTION_INFO)
    with tabs[3]:
        info_picker("City", BRANCH_INFO)
    with tabs[4]:
        info_picker("Service", SERVICE_INFO)
    with tabs[5]:
        emi_calculator()


def page_complaint():
    st.subheader("📝 Complaint Form")
    st.warning(SAFETY_NOTE)
    with st.form("complaint_form", clear_on_submit=True):
        name = st.text_input("Your name", value=st.session_state.get("user_name", ""))
        category = st.selectbox("Category", ["Account", "Card", "Transaction", "Branch", "Service", "Other"])
        severity = st.select_slider("How urgent is it?", ["Low", "Medium", "High"], value="Medium")
        details = st.text_area("Describe the problem", placeholder="e.g. UPI payment failed but money was deducted")
        submitted = st.form_submit_button("Submit complaint")

    if submitted:
        if not name.strip() or not details.strip():
            st.error("Please enter your name and describe the problem.")
        else:
            st.session_state.state["ticket"] += 1
            ref = f"CMP{st.session_state.state['ticket']}"
            st.session_state.tickets.append(
                {"Reference": ref, "Name": name.strip(), "Category": category,
                 "Urgency": severity, "Details": details.strip()})
            st.success(f"Complaint registered. Your sample reference is **{ref}**. "
                       "A support officer will contact you within 2 working days.")

    if st.session_state.tickets:
        st.markdown("#### Complaints logged in this session")
        st.dataframe(st.session_state.tickets, use_container_width=True, hide_index=True)


def page_playground():
    st.subheader("🔬 NLP Playground")
    st.caption("Type any sentence and see the intent and entities the bot detects, live.")
    text = st.text_input("Your sentence", value="I want a credit card from the Mumbai branch",
                         key="playground_text")
    if text.strip():
        show_analysis(analyze(text))
        cleaned = clean_text(text)
        hits = {i: [k for k in kws if contains(cleaned, k)] for i, kws in INTENT_KEYWORDS.items()}
        hits = {i: k for i, k in hits.items() if k}
        if hits:
            st.markdown("**Matched keywords per intent**")
            st.json(hits)


# ---------- Sidebar + routing ----------
init_session()

with st.sidebar:
    st.title("🏦 " + BANK_NAME)
    page = st.radio("Go to", PAGES, key="page")
    st.text_input("Your name (optional)", key="user_name", placeholder="e.g. Pallavi")
    st.divider()
    if st.button("🔄 Reset conversation", use_container_width=True):
        reset_chat()
        st.rerun()
    la = st.session_state.last_analysis
    if la:
        st.markdown("**Last message analysis**")
        st.write(f"Intent: `{la['intent']}`")
        st.write(f"Entities: `{la['entities'] or 'none'}`")
    st.caption("Sample data only. Not a real bank.")

if page == PAGES[0]:
    page_home()
elif page == PAGES[1]:
    page_chat()
elif page == PAGES[2]:
    page_quick()
elif page == PAGES[3]:
    page_complaint()
else:
    page_playground()
