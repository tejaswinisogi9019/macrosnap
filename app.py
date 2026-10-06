
import time
import smtplib
from email.mime.text import MIMEText

import streamlit as st
from google import genai
from google.genai import types

from prompts import (
    SYSTEM_PROMPT,
    WELCOME_MESSAGE_TEMPLATE,
    SUMMARY_REQUEST_PROMPT,
)


# =========================================================
# SETTINGS
# =========================================================

MODEL_NAME = "gemini-3.1-flash-lite"

st.set_page_config(
    page_title="StudySnap AI",
    page_icon="📚",
    layout="centered",
)


# =========================================================
# SECRETS
# =========================================================

GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
GMAIL_ADDRESS = st.secrets["GMAIL_ADDRESS"]
GMAIL_APP_PASSWORD = st.secrets["GMAIL_APP_PASSWORD"]


# =========================================================
# GEMINI CLIENT
# =========================================================

@st.cache_resource
def get_gemini_client():
    return genai.Client(api_key=GEMINI_API_KEY)


gemini_client = get_gemini_client()


# =========================================================
# MESSAGE FUNCTIONS
# =========================================================

def render_message(message):

    with st.chat_message(message["role"]):

        if message["kind"] == "text":
            st.write(message["content"])

        elif message["kind"] == "image":
            st.image(message["content"])


def add_message(role, kind, content):

    message = {
        "role": role,
        "kind": kind,
        "content": content,
    }

    st.session_state.messages.append(message)

    render_message(message)


# =========================================================
# GEMINI FUNCTION
# =========================================================

def ask_gemini(parts):

    for attempt in range(3):

        try:

            response = st.session_state.chat.send_message(parts)

            return response.text

        except Exception as error:

            error_text = str(error)

            # Gemini temporarily busy
            if "503" in error_text or "UNAVAILABLE" in error_text:

                if attempt < 2:
                    time.sleep(5)
                    continue

                return (
                    "⚠️ Gemini is temporarily busy.\n\n"
                    "Please wait a few seconds and try again."
                )

            # Too many requests
            if "429" in error_text:

                return (
                    "⚠️ Too many requests right now.\n\n"
                    "Please wait a moment and try again."
                )

            # API key problem
            if "401" in error_text or "API key" in error_text:

                return (
                    "⚠️ There is a problem with your Gemini API key.\n\n"
                    "Please check your secrets.toml file."
                )

            # Model problem
            if "404" in error_text:

                return (
                    "⚠️ The Gemini model is not available.\n\n"
                    "Please check the model name."
                )

            # Other error
            return (
                "⚠️ Gemini could not process your request.\n\n"
                f"Error: {error_text}"
            )

    return "⚠️ Please try again."


# =========================================================
# EMAIL FUNCTION
# =========================================================

def send_email(to_address, user_name, summary):

    try:

        message = MIMEText(
            summary,
            "plain",
            "utf-8"
        )

        message["Subject"] = (
            f"📚 StudySnap AI - Study Summary for {user_name}"
        )

        message["From"] = GMAIL_ADDRESS
        message["To"] = to_address

        with smtplib.SMTP_SSL(
            "smtp.gmail.com",
            465
        ) as server:

            server.login(
                GMAIL_ADDRESS,
                GMAIL_APP_PASSWORD
            )

            server.send_message(message)

        return True, "Email sent successfully"

    except Exception as error:

        return False, str(error)


# =========================================================
# ONBOARDING
# =========================================================

if "onboarded" not in st.session_state:

    st.title("📚 StudySnap AI")

    st.caption(
        "Snap it. Understand it. Learn it."
    )

    st.markdown(
        """
        ### Welcome to StudySnap AI 👋

        Upload your:

        📖 Textbook page  
        📝 Handwritten notes  
        📐 Diagram  
        🧮 Math problem  
        💻 Programming question  
        📄 Assignment  
        🖼️ Any photo

        StudySnap AI will understand the image
        and answer your questions.
        """
    )

    with st.form("onboarding_form"):

        name = st.text_input(
            "Your name",
            placeholder="Enter your name"
        )

        email_address = st.text_input(
            "Your Gmail address",
            placeholder="example@gmail.com"
        )

        submitted = st.form_submit_button(
            "Start Learning 🚀"
        )

    if submitted:

        if not name.strip():

            st.warning("Please enter your name.")

        elif not email_address.strip():

            st.warning("Please enter your Gmail address.")

        else:

            st.session_state.name = name.strip()

            st.session_state.email_address = (
                email_address.strip()
            )

            st.session_state.chat = (
                gemini_client.chats.create(
                    model=MODEL_NAME,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT
                    ),
                )
            )

            st.session_state.messages = []

            st.session_state.onboarded = True

            st.rerun()

    st.stop()


# =========================================================
# HEADER
# =========================================================

header_col, button_col = st.columns(
    [5, 2],
    vertical_alignment="center"
)


with header_col:

    st.title("📚 StudySnap AI")


with button_col:

    send_disabled = (
        len(st.session_state.messages) <= 1
    )

    if st.button(
        "📧 Send Summary",
        disabled=send_disabled,
        use_container_width=True
    ):

        with st.spinner(
            "Preparing your study summary..."
        ):

            summary = ask_gemini(
                [SUMMARY_REQUEST_PROMPT]
            )

        success, info = send_email(
            st.session_state.email_address,
            st.session_state.name,
            summary
        )

        if success:

            st.success(
                "Summary sent! Check your email 📧"
            )

        else:

            st.error(
                f"Couldn't send the email: {info}"
            )


# =========================================================
# USER INFORMATION
# =========================================================

st.caption(
    f"Logged in as {st.session_state.name} "
    f"• Summary: {st.session_state.email_address}"
)


# =========================================================
# WELCOME MESSAGE
# =========================================================

if not st.session_state.messages:

    add_message(
        "assistant",
        "text",
        WELCOME_MESSAGE_TEMPLATE.format(
            name=st.session_state.name
        )
    )

else:

    for message in st.session_state.messages:

        render_message(message)


# =========================================================
# CHAT INPUT
# =========================================================

user_input = st.chat_input(
    "Ask a question or upload a photo",
    accept_file=True,
    file_type=[
        "jpg",
        "jpeg",
        "png"
    ]
)


# =========================================================
# PROCESS INPUT
# =========================================================

if user_input:

    photo = None

    if user_input.files:

        photo = user_input.files[0]

    text = user_input.text

    parts = []


    # =====================================================
    # IMAGE
    # =====================================================

    if photo is not None:

        photo_bytes = photo.getvalue()

        add_message(
            "user",
            "image",
            photo_bytes
        )

        parts.append(
            types.Part.from_bytes(
                data=photo_bytes,
                mime_type=photo.type
            )
        )


    # =====================================================
    # TEXT
    # =====================================================

    if text:

        add_message(
            "user",
            "text",
            text
        )

        parts.append(text)


    # =====================================================
    # IMAGE WITHOUT TEXT
    # =====================================================

    elif photo is not None:

        parts.append(
            """
            Analyze this image carefully.

            Tell me what is visible in the image.

            If there are objects:
            - List the main objects.

            If there are people:
            - Describe them generally.

            If there is text:
            - Read and explain the important text.

            If there is a diagram:
            - Identify the diagram and its parts.

            If it is a textbook or notes:
            - Identify the topic and explain it.

            If it is a math problem:
            - Solve it step by step.

            If it is programming code:
            - Explain the code.

            Do not guess.
            If something is unclear, say that it is unclear.

            Keep the answer simple and clear.
            """
        )


    # =====================================================
    # SEND TO GEMINI
    # =====================================================

    if parts:

        with st.spinner(
            "🧠 StudySnap is understanding..."
        ):

            answer = ask_gemini(parts)


        # =================================================
        # SHOW ANSWER
        # =================================================

        add_message(
            "assistant",
            "text",
            answer
        )