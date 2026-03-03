#!/usr/bin/env python3

"""
Hugging Face Configuration

This file contains the Hugging Face token for accessing gated models.
"""


# Configuration for Hugging Face Hub
HF_CONFIG = {
    "token": HF_API_TOKEN,
    "use_auth_token": True,
    "trust_remote_code": True
}