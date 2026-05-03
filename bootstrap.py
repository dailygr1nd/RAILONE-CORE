# ==============================
# bootstrap.py
# ==============================

from key_manager import bootstrap_institutions
from core_registry import register_core


def bootstrap():

    # external rails
    bootstrap_institutions()

    # core protocol authority
    register_core()