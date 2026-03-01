#!/usr/bin/env python3

"""
Hugging Face Configuration

This file contains the Hugging Face token for accessing gated models.
"""

# Hugging Face API Token
HF_API_TOKEN = "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"

# You can also set this as an environment variable:
# export HUGGING_FACE_HUB_TOKEN="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"

# Configuration for Hugging Face Hub
HF_CONFIG = {
    "token": HF_API_TOKEN,
    "use_auth_token": True,
    "trust_remote_code": True
}