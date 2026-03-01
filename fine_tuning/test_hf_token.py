#!/usr/bin/env python3

"""
Test Hugging Face Token

Simple script to test if the HF token can access the model.
"""

import os
from transformers import AutoTokenizer


def test_hf_token():
    """Test Hugging Face token by loading the tokenizer"""
    print("🧪 Testing Hugging Face Token")
    print("=" * 40)
    
    try:
        # Try to import and use the token
        from hf_config import HF_API_TOKEN
        print("✅ Hugging Face token loaded from config")
        
        # Test with a small model first
        print("🔑 Testing token with model access...")
        tokenizer = AutoTokenizer.from_pretrained(
            "mistralai/Mistral-Small-3.1-24B-Base-2503",
            token=HF_API_TOKEN,
            trust_remote_code=True
        )
        
        print("✅ Token is valid and working!")
        print(f"   Tokenizer loaded: {tokenizer.name_or_path}")
        print(f"   Vocab size: {tokenizer.vocab_size}")
        
        # Test tokenization
        test_text = "Hello, world!"
        encoded = tokenizer(test_text)
        print(f"   Test encoding: {encoded}")
        print(f"   Decoded: {tokenizer.decode(encoded['input_ids'])}")
        
        return True
        
    except ImportError:
        print("⚠️  HF config not found, trying environment variable...")
        try:
            tokenizer = AutoTokenizer.from_pretrained(
                "mistralai/Mistral-Small-3.1-24B-Base-2503",
                trust_remote_code=True
            )
            print("✅ Token works via environment variable!")
            return True
        except Exception as e:
            print(f"❌ Token test failed: {e}")
            return False
    except Exception as e:
        print(f"❌ Token test failed: {e}")
        return False


if __name__ == "__main__":
    success = test_hf_token()
    if success:
        print("\n🎉 Hugging Face token is working!")
        print("   You can now run the full fine-tuning script.")
    else:
        print("\n⚠️  Hugging Face token failed.")
        print("   Check your token and try again.")
        print("   You can also set HUGGING_FACE_HUB_TOKEN environment variable.")