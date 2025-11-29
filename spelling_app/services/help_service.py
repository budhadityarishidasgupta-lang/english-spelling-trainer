"""
Helper service for Spelling front page help / marketing copy.

For now this returns static defaults.
In a later patch, this will be wired to a DB-backed table
so admins can edit the content from the console.
"""

from textwrap import dedent


DEFAULT_SECTIONS = {
    "spelling_intro": dedent(
        """
        Turn 11+ preparation into an engaging learning journey!  
        Our Spelling Trainer helps learners practise tricky words, build confidence,
        and track progress over time – in short, focused sessions.
        """
    ).strip(),
    "spelling_instructions": dedent(
        """
        **Sign in or Register to get started:**

        1. Sign in with your registered email and password on the left.
        2. After login, you’ll see your available spelling courses and lessons.
        3. Practise the spelling lists, review mistakes, and repeat hard words.
        4. Aim to complete at least one spelling lesson a day for best results.
        """
    ).strip(),
    "spelling_registration": dedent(
        """
        To register as a new student:

        - Complete the PayPal payment as instructed below.
        - Enter your **Name** and **Email address** in the form.
        - Your account will be created and activated by the teacher.
        - You’ll receive an email once your login is ready.
        """
    ).strip(),
    "spelling_paypal": dedent(
        """
        **Payment instructions (example – to be edited later):**

        - Registration fee: **£14.99** (one-time access).
        - Send the payment via PayPal to **barktuitions@gmail.com**.
        - Use your child's name in the payment reference.
        - After payment, submit the registration form on this page.

        These details will be fully editable later from the Admin Console.
        """
    ).strip(),
}


def get_help_text(section_key: str) -> str:
    """
    Return the help / marketing copy for a given section.

    For now this is static content, backed by DEFAULT_SECTIONS.
    In a later patch we will override this to pull from a DB table
    (e.g. portal_content or help_content) that admins can edit.
    """
    return DEFAULT_SECTIONS.get(section_key, "")
