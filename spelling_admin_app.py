import sys, os

# Prevent Python from scanning synonym_legacy when running spelling admin
# (synonym app continues to work normally)
block_path = os.path.join(os.getcwd(), "synonym_legacy")
if block_path in sys.path:
    sys.path.remove(block_path)

import streamlit as st
from spelling_app.admin_ui import render_spelling_admin

def main():
    render_spelling_admin()

if __name__ == "__main__":
    main()
