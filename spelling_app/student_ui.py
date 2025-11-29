import streamlit as st

from spelling_app.services.help_service import get_help_text
from spelling_app.repository.registration_repo import create_pending_registration


def render_spelling_student_page():
    """
    Spelling Student landing page.

    Left column: login + change password (stubbed for now).
    Right column: intro, instructions, registration info, PayPal info, and a simple
    registration form (no backend wiring yet – that will be a later patch).
    """
    st.title("Spelling Trainer")

    col_left, col_right = st.columns([1, 2])

    # -----------------------------------
    # LEFT: Login + Change Password stub
    # -----------------------------------
    with col_left:
        st.header("Sign in")

        login_email = st.text_input("Email", key="spell_login_email")
        login_password = st.text_input(
            "Password", type="password", key="spell_login_password"
        )

        if st.button("Login", key="spell_login_button"):
            # TODO: hook into existing authentication logic in a later patch
            st.info("Login handling will be connected to the main auth system later.")

        st.markdown("---")
        st.subheader("Change Password")

        current_pw = st.text_input(
            "Current Password", type="password", key="spell_current_pw"
        )
        new_pw = st.text_input(
            "New Password", type="password", key="spell_new_pw"
        )
        confirm_pw = st.text_input(
            "Confirm New Password", type="password", key="spell_confirm_pw"
        )

        if st.button("Update Password", key="spell_update_pw"):
            # TODO: wire to password change endpoint later
            st.info("Password change flow will be implemented in a later patch.")

    # -----------------------------------
    # RIGHT: Intro, instructions, registration, PayPal
    # -----------------------------------
    with col_right:
        # Intro section (hero text)
        intro_text = get_help_text("spelling_intro")
        if intro_text:
            st.markdown(intro_text)

        st.markdown("### Instructions")
        instructions = get_help_text("spelling_instructions")
        if instructions:
            st.markdown(instructions)

        st.markdown("### New registration")
        reg_text = get_help_text("spelling_registration")
        if reg_text:
            st.markdown(reg_text)

        st.markdown("### PayPal / payment details")
        paypal_text = get_help_text("spelling_paypal")
        if paypal_text:
            st.markdown(paypal_text)

        st.markdown("---")
        st.markdown("### Registration form")

        reg_name = st.text_input("Student Name", key="spell_reg_name")
        reg_email = st.text_input("Parent / Contact Email", key="spell_reg_email")

        if st.button("Submit registration", key="spell_reg_submit"):
            if not reg_name or not reg_email:
                st.error("Please enter both name and email.")
            else:
                create_pending_registration(reg_name, reg_email)
                st.success(
                    "Thank you! Your registration has been received. "
                    "The teacher will contact you after verifying payment."
                )
