#!/usr/bin/env python3

"""
Test with a Smaller Model

This script tests the pipeline with a smaller model that works on CPU.
"""

import os
import json
from transformers import AutoModelForCausalLM, AutoTokenizer


def test_small_model():
    """Test with a small model to verify the pipeline works"""
    
    print("🧪 Testing with a smaller model")
    print("=" * 40)
    
    try:
        # Use a smaller model that works well on CPU
        model_name = "mistralai/Mistral-7B-Instruct-v0.1"
        
        print(f"🔍 Testing model: {model_name}")
        
        # Load tokenizer first (fast)
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        print(f"✅ Tokenizer loaded: {tokenizer.name_or_path}")
        
        # Test tokenization
        test_text = "Hello, world!"
        encoded = tokenizer(test_text)
        print(f"✅ Tokenization works: {encoded}")
        
        # Load model (this may take time on first run)
        print("🔄 Loading model (this may take a few minutes)...")
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            device_map="auto",
            torch_dtype="auto",
            trust_remote_code=True
        )
        
        print(f"✅ Model loaded: {model.config._name_or_path}")
        print(f"   Memory usage: {model.get_memory_footprint() / 1e6:.1f} MB")
        
        # Test inference
        print("🧠 Testing inference...")
        inputs = tokenizer("What is the capital of France?", return_tensors="pt")
        outputs = model.generate(**inputs, max_new_tokens=20)
        answer = tokenizer.decode(outputs[0], skip_special_tokens=True)
        print(f"✅ Inference works!")
        print(f"   Question: What is the capital of France?")
        print(f"   Answer: {answer}")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        print("\n💡 If this fails:")
        print("   - Check your internet connection")
        print("   - Try a different model name")
        print("   - Ensure you have enough RAM (8GB+ recommended)")
        return False


if __name__ == "__main__":
    success = test_small_model()
    if success:
        print("\n🎉 Small model test passed!")
        print("   Your environment is working correctly.")
        print("   You can now try the full Mistral-Small model on a GPU system.")
    else:
        print("\n⚠️  Small model test failed.")
        print("   Check the error message above for details.")