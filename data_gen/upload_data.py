import json 
import os
import random
from mistralai import Mistral
import argparse

api_key = os.environ["MISTRAL_API_KEY"]
client = Mistral(api_key=api_key)


def save_formatted_data(formatted_conversations, output_path: str, use_jsonl=False):
    """
    Save formatted conversations to a JSON or JSONL file.
    
    Args:
        formatted_conversations: List of formatted conversations
        output_path: Path to save the formatted file
        use_jsonl: If True, save as JSONL (one JSON object per line) for Mistral API
    """
    if use_jsonl:
        # Save as JSONL format (one JSON object per line) for Mistral
        with open(output_path, 'w') as f:
            for conversation in formatted_conversations:
                json.dump(conversation, f)
                f.write('\n')
        print(f"✅ Formatted data saved to {output_path} (JSONL format)")
    else:
        # Save as regular JSON format
        with open(output_path, 'w') as f:
            json.dump(formatted_conversations, f, indent=2)
        print(f"✅ Formatted data saved to {output_path} (JSON format)")
    
    return output_path


def upload_to_mistral(train_data_path: str, val_data_path: str = None):
    """
    Upload formatted data files to Mistral for fine-tuning.
    
    Args:
        train_data_path: Path to the training JSONL file
        val_data_path: Optional path to validation JSONL file
        
    Returns:
        Dictionary with file IDs or None if upload failed
    """
    try:
        # Upload training file
        with open(train_data_path, 'rb') as f:
            training_data = client.files.upload(
                file={
                    "file_name": os.path.basename(train_data_path),
                    "content": f,
                }
            )
        
        print(f"📤 Training file uploaded successfully. File ID: {training_data.id}")
        
        # Upload validation file if provided
        validation_data = None
        if val_data_path and os.path.exists(val_data_path):
            with open(val_data_path, 'rb') as f:
                validation_data = client.files.upload(
                    file={
                        "file_name": os.path.basename(val_data_path),
                        "content": f,
                    }
                )
            print(f"📤 Validation file uploaded successfully. File ID: {validation_data.id}")
        
        return {
            'training_file_id': training_data.id,
            'validation_file_id': validation_data.id if validation_data else None,
            'training_file_name': os.path.basename(train_data_path),
            'validation_file_name': os.path.basename(val_data_path) if val_data_path else None
        }
        
    except Exception as e:
        print(f"❌ Error uploading files to Mistral: {e}")
        return None


def format_data(path : str ):
    """
    Format emergency call data for Mistral fine-tuning.
    
    Args:
        path: Path to input JSON file containing emergency call data
        
    Returns:
        List of formatted conversations ready for fine-tuning
    """
    # Load the input data
    with open(path, 'r') as f:
        data = json.load(f)
    
    formatted_conversations = []
    
    for item in data:
        # Handle both string JSON format and direct object format
        if isinstance(item, str):
            # Parse the string as JSON
            try:
                item_data = json.loads(item)
            except json.JSONDecodeError:
                print(f"⚠️  Error parsing JSON string: {item[:50]}...")
                continue
        else:
            # Already a dictionary
            item_data = item
        
        # Extract discussion and scores from the parsed item
        discussion = item_data.get('discussion', [])
        scores = item_data.get('scores', {})
        
        # Build the conversation in the requested format:
        # Single user message with entire discussion, single assistant message with scores
        
        # Combine all discussion exchanges into one user message
        full_discussion = []
        for exchange in discussion:
            if isinstance(exchange, dict):
                role = exchange.get('role', '')
                content = exchange.get('content', '')
                if role and content:
                    full_discussion.append(f"{role.upper()}: {content}")
        
        # Create the user message with the entire discussion
        user_message = {
            "role": "user",
            "content": "\n".join(full_discussion)
        }
        
        # Create the assistant message with the scores
        if scores:
            score_text = f"Scores: anxiety={scores.get('anxiety', 'N/A')}, " \
                        f"severity={scores.get('severity', 'N/A')}, " \
                        f"coherence={scores.get('coherence', 'N/A')}, " \
                        f"seriousness={scores.get('seriousness', 'N/A')}"
            assistant_message = {
                "role": "assistant",
                "content": score_text
            }
        else:
            assistant_message = {
                "role": "assistant",
                "content": "No scores available"
            }
        
        # Create the formatted conversation
        formatted_conversation = {
            "messages": [user_message, assistant_message]
        }
        
        formatted_conversations.append(formatted_conversation)
    
    return formatted_conversations


def split_train_test(formatted_conversations, test_size=0.2, random_seed=None):
    """
    Split formatted conversations into training and test sets.
    
    Args:
        formatted_conversations: List of formatted conversations
        test_size: Proportion of data to use for testing (0.0 to 1.0)
        random_seed: Random seed for reproducible splits
        
    Returns:
        Tuple of (train_set, test_set)
    """
    if random_seed is not None:
        random.seed(random_seed)
    
    # Shuffle the conversations
    shuffled_data = formatted_conversations.copy()
    random.shuffle(shuffled_data)
    
    # Calculate split point
    test_count = int(len(shuffled_data) * test_size)
    
    # Split into train and test
    train_set = shuffled_data[test_count:]
    test_set = shuffled_data[:test_count]
    
    print(f"📊 Dataset split: {len(train_set)} train, {len(test_set)} test samples")
    return train_set, test_set


if __name__ == "__main__":
    # Set up command line argument parsing
    parser = argparse.ArgumentParser(description='Format and upload emergency call data for Mistral fine-tuning')
    parser.add_argument('--input', type=str, required=True, help='Input JSON file path')
    parser.add_argument('--output', type=str, default='formatted_data.json', help='Output formatted JSON file path')
    parser.add_argument('--upload', action='store_true', help='Upload to Mistral after formatting')
    parser.add_argument('--test-size', type=float, default=0.2, help='Proportion of data to use for testing (0.0 to 1.0)')
    parser.add_argument('--random-seed', type=int, default=42, help='Random seed for reproducible splits')
    parser.add_argument('--split', action='store_true', help='Split into train/test sets')
    
    args = parser.parse_args()
    
    print(f'🔄 Formatting data from {args.input}...')
    
    # Format the data
    formatted_conversations = format_data(args.input)
    
    if args.split:
        # Split into train and test sets
        train_set, test_set = split_train_test(
            formatted_conversations,
            test_size=args.test_size,
            random_seed=args.random_seed
        )
        
        # Save both sets (use JSONL if uploading to Mistral)
        use_jsonl_format = args.upload
        
        if args.output.endswith('.json'):
            train_output = args.output.replace('.json', '_train.jsonl' if use_jsonl_format else '_train.json')
            test_output = args.output.replace('.json', '_test.jsonl' if use_jsonl_format else '_test.json')
        else:
            train_output = f"{args.output}_train.jsonl" if use_jsonl_format else f"{args.output}_train.json"
            test_output = f"{args.output}_test.jsonl" if use_jsonl_format else f"{args.output}_test.json"
        
        save_formatted_data(train_set, train_output, use_jsonl_format)
        save_formatted_data(test_set, test_output, use_jsonl_format)
        
        print(f"📁 Saved training set to {train_output}")
        print(f"📁 Saved test set to {test_output}")
        
        # Upload to Mistral if requested
        if args.upload:
            print('📤 Uploading to Mistral...')
            upload_result = upload_to_mistral(train_output, test_output)
            
            if upload_result:
                print(f"🎉 Upload complete!")
                print(f"   Training File ID: {upload_result['training_file_id']}")
                if upload_result['validation_file_id']:
                    print(f"   Validation File ID: {upload_result['validation_file_id']}")
                print(f"   You can now manually create a fine-tuning job using these file IDs")
    else:
        # Save formatted data
        save_formatted_data(formatted_conversations, args.output)
        
        # Upload to Mistral if requested
        if args.upload:
            print('📤 Uploading to Mistral...')
            upload_result = upload_to_mistral(args.output)
            
            if upload_result:
                print(f"🎉 Upload complete!")
                print(f"   Training File ID: {upload_result['training_file_id']}")
                print(f"   You can now manually create a fine-tuning job using this file ID")