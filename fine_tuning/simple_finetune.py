#!/usr/bin/env python3

"""
Simple Mistral Fine-Tuning Script

This script provides a minimal, working example for creating fine-tuning jobs.
It handles API errors gracefully and provides clear feedback.
"""

import os
from mistralai import Mistral


def create_finetune_job():
    """Create a fine-tuning job with proper error handling"""
    
    # Initialize client
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        print("❌ Please set MISTRAL_API_KEY environment variable")
        return None
    
    client = Mistral(api_key=api_key)
    
    # File IDs from our successful uploads
    training_file_id = "a6ad64b9-5986-4c9e-8be6-f1349ad69a65"
    validation_file_id = "95e554b1-acce-4b0e-b99f-88e743f9ea05"
    
    print("🚀 Creating fine-tuning job...")
    print(f"   Training file: {training_file_id}")
    print(f"   Validation file: {validation_file_id}")
    
    # Try different models that might work for completion fine-tuning
    models_to_try = [
        "open-mistral-7b",
        "mistral-small-latest",
        "open-mistral-nemo"
    ]
    
    for model in models_to_try:
        print(f"\n🔍 Trying model: {model}")
        
        try:
            # Create the job with minimal parameters
            created_job = client.fine_tuning.jobs.create(
                model=model,
                training_files=[training_file_id],
                validation_files=[validation_file_id],
                hyperparameters={
                    "training_steps": 10,
                    "learning_rate": 0.0001
                },
                auto_start=False
            )
            
            print(f"🎉 Success! Job created with model {model}")
            print(f"   Job ID: {created_job.id}")
            print(f"   Status: {created_job.status}")
            
            # Save job info
            import json
            job_info = {
                'job_id': created_job.id,
                'model': model,
                'training_file': training_file_id,
                'validation_file': validation_file_id,
                'status': created_job.status
            }
            
            with open('job_info.json', 'w') as f:
                json.dump(job_info, f, indent=2)
            
            print(f"✅ Job info saved to job_info.json")
            return created_job
            
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Failed with {model}: {error_msg}")
            
            # Check if it's a model availability error
            if "not available for this type of fine-tuning" in error_msg:
                print(f"   This model doesn't support completion fine-tuning")
            continue
    
    print(f"\n⚠️  All models failed. This might indicate:")
    print(f"   1. Your account doesn't have access to completion fine-tuning")
    print(f"   2. The API has changed and requires a different approach")
    print(f"   3. You need to use chat fine-tuning instead of completion")
    
    print(f"\n💡 Alternative approaches:")
    print(f"   1. Try chat fine-tuning with different parameters")
    print(f"   2. Contact Mistral support for account-specific guidance")
    print(f"   3. Use the uploaded files with Mistral's web interface")
    
    return None


def check_job_status(job_id: str):
    """Check the status of a fine-tuning job"""
    
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        print("❌ Please set MISTRAL_API_KEY environment variable")
        return None
    
    client = Mistral(api_key=api_key)
    
    try:
        status = client.fine_tuning.jobs.get(job_id=job_id)
        print(f"📊 Job {job_id} status: {status.status}")
        return status
    except Exception as e:
        print(f"❌ Error getting job status: {e}")
        return None


if __name__ == "__main__":
    # Try to create the job
    job = create_finetune_job()
    
    if job:
        print(f"\n🎯 Next steps:")
        print(f"   1. Wait for validation (check status periodically)")
        print(f"   2. When status is 'VALIDATED', start the job")
        print(f"   3. Monitor training progress")
        print(f"\n   Commands:")
        print(f"   mistral jobs get {job.id}")
        print(f"   mistral jobs start {job.id}")
        print(f"   mistral jobs monitor {job.id}")
    else:
        print(f"\n📚 Need help?")
        print(f"   - Check Mistral documentation for supported models")
        print(f"   - Try the web interface at https://mistral.ai")
        print(f"   - Contact support if you believe this is an error")