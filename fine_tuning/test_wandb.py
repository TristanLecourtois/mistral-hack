#!/usr/bin/env python3

"""
Test W&B Configuration

Simple script to test if W&B is properly configured.
"""

import wandb
from wandb_config import WANDB_API_KEY, WANDB_PROJECT, WANDB_CONFIG


def test_wandb():
    """Test W&B configuration"""
    print("🧪 Testing W&B Configuration")
    print("=" * 40)
    
    try:
        # Login to W&B
        print("🔑 Logging in to W&B...")
        wandb.login(key=WANDB_API_KEY)
        print("✅ Login successful!")
        
        # Test initialization
        print("🚀 Initializing W&B run...")
        run = wandb.init(
            project=WANDB_PROJECT,
            config=WANDB_CONFIG,
            entity=WANDB_CONFIG.get('entity')
        )
        
        print("✅ W&B run initialized successfully!")
        print(f"   Project: {WANDB_PROJECT}")
        print(f"   Run ID: {run.id}")
        print(f"   Run name: {run.name}")
        print(f"   Config: {dict(run.config)}")
        
        # Log a test metric
        print("📊 Logging test metric...")
        wandb.log({"test_metric": 0.95, "test_loss": 0.05})
        
        # Finish the run
        run.finish()
        print("✅ W&B test completed successfully!")
        
        return True
        
    except Exception as e:
        print(f"❌ W&B test failed: {e}")
        return False


if __name__ == "__main__":
    success = test_wandb()
    if success:
        print("\n🎉 W&B is properly configured!")
        print("   You can now run the full fine-tuning script.")
    else:
        print("\n⚠️  W&B configuration failed.")
        print("   Check your API key and internet connection.")