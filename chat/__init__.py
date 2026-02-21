#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
chat — Chat module

Exports public API for chat utilities.
"""

from .send import send_message, send_failure_to_chat
from .input import wait_for_chat_ready