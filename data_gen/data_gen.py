import json
import random
from mistralai import Mistral
from typing import Dict, List, Optional
import os
from tqdm import tqdm


class EmergencyCallDataGenerator():
    """
    Generates synthetic emergency call datasets with scoring on 4 criteria:
    - anxiety (0-10): caller's anxiety level
    - severity (0-10): situation severity
    - coherence (0-10): caller's speech coherence
    - seriousness (0-10): call legitimacy (0=prank, 10=real emergency)
    """

    def __init__(self, 
                 client,
                 model: str = "mistral-vibe-cli-with-tools",
                 max_tokens: int = 2048, 
                 temperature: float = 0.7,
                 response_format: Dict = {"type": "json_object"},
                 config_file: str = "prompt_config.json"):
        self.client = client
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.response_format = response_format
        self.scenario_types = [
            "medical", "fire", "police", "accident", 
            "mental_health", "natural_disaster", "prank"
        ]
        # Fix path for config file
        if not os.path.isabs(config_file):
            config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), config_file)
        self.config = self._load_config(config_file)

    def _load_config(self, config_file: str) -> Dict:
        """Load prompt configuration from JSON file"""
        try:
            with open(config_file, 'r') as f:
                print(f"Config file {config_file} found ! \n")
                return json.load(f)
        except FileNotFoundError:
            print(f"Warning: Config file {config_file} not found, using default configuration")
            return {
                "default_prompt": {
                    "template": "Generate a realistic emergency call scenario about {scenario_type}.",
                    "instructions": [
                        "Caller's dialogue (3-5 exchanges with operator)",
                        "Situation description",
                        "Score each criteria (0-10):",
                        "   - anxiety: caller's anxiety level",
                        "   - severity: actual danger level",
                        "   - coherence: how clear/coherent the caller is",
                        "   - seriousness: 0 if prank/joke, 10 if real emergency"
                    ],
                    "output_format": "Return as JSON with keys: transcript, situation, scores"
                },
                "scenario_specific": {},
                "output_structure": {}
            }

    def generate_call_scenario(self, scenario_type: Optional[str] = None) -> Dict:
        """
        Generate a single emergency call scenario with criteria scoring
        
        Args:
            scenario_type: Specific type of emergency or None for random
            
        Returns:
            Dictionary containing call transcript and scores
        """
        if scenario_type is None:
            scenario_type = random.choice(self.scenario_types)
        
        # Build prompt from configuration
        default_config = self.config["default_prompt"]
        template = default_config["template"]
        instructions = default_config["instructions"]
        output_format = default_config["output_format"]
        
        # Add scenario-specific instructions if available
        scenario_specific = self.config["scenario_specific"].get(scenario_type, {})
        additional_instructions = scenario_specific.get("additional_instructions", [])
        
        prompt = template.format(scenario_type=scenario_type)
        prompt += "\n" + "\n".join(["Include:"] + instructions)
        
        if additional_instructions:
            prompt += "\n" + "\n".join(["Additionally:"] + additional_instructions)
            
        prompt += f"\n\n{output_format}"
        
        response = self.client.chat.complete(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            response_format=self.response_format
        )
        
        return response.choices[0].message.content

    def generate_dataset(self, num_samples: int = 100, 
                       output_file: str = "emergency_calls.json",
                       force_diversity: bool = True) -> List[Dict]:
        """
        Generate a complete dataset of emergency calls
        
        Args:
            num_samples: Number of call scenarios to generate
            output_file: Path to save JSON dataset
            force_diversity: If True, ensure diverse score ranges
            
        Returns:
            List of generated call scenarios
        """
        dataset = []
        
        # If forcing diversity, cycle through different scenario types
        # and include more prank/low-severity examples
        if force_diversity:
            # Ensure we get a mix of high, medium, and low severity scenarios
            scenario_pattern = [
                "prank", "mental_health", "accident", 
                "medical", "fire", "police", "natural_disaster"
            ]
            
            # Use tqdm for progress bar if available
            try:
                progress_bar = tqdm(range(num_samples), desc='Generating diverse samples', unit='sample')
            except ImportError:
                progress_bar = range(num_samples)
                print(f'🔄 Generating {num_samples} samples with diversity...')
            
            for i in progress_bar:
                scenario_type = scenario_pattern[i % len(scenario_pattern)]
                call_data = self.generate_call_scenario(scenario_type)
                dataset.append(call_data)
                
                # Update tqdm description if available
                if hasattr(progress_bar, 'set_postfix'):
                    progress_bar.set_postfix({'generated': i+1, 'total': num_samples})
                
                # Write to file after each sample (incremental save)
                with open(output_file, 'w') as f:
                    json.dump(dataset, f, indent=2)
        else:
            # Use tqdm for progress bar if available
            try:
                progress_bar = tqdm(range(num_samples), desc='Generating random samples', unit='sample')
            except ImportError:
                progress_bar = range(num_samples)
                print(f'🔄 Generating {num_samples} random samples...')
            
            for i in progress_bar:
                scenario_type = random.choice(self.scenario_types)
                call_data = self.generate_call_scenario(scenario_type)
                dataset.append(call_data)
                
                # Update tqdm description if available
                if hasattr(progress_bar, 'set_postfix'):
                    progress_bar.set_postfix({'generated': i+1, 'total': num_samples})
                
                # Write to file after each sample (incremental save)
                with open(output_file, 'w') as f:
                    json.dump(dataset, f, indent=2)
        
        # Final save (already saved incrementally)
        print(f"✅ Dataset generation complete - {output_file}")
        return dataset


def generate_n_samples(n_samples=10, output_dir="output", force_diversity=True):
    """
    Generate n samples of emergency call discussions
    
    Args:
        n_samples: Number of samples to generate
        output_dir: Directory to save output files
        force_diversity: Ensure diverse score ranges
        
    Returns:
        Dictionary with generated dataset and file path
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Initialize generator
    api_key = os.environ["MISTRAL_API_KEY"]
    client = Mistral(api_key=api_key)
    generator = EmergencyCallDataGenerator(client, model="mistral-large-latest")
    
    # Generate dataset
    dataset = generator.generate_dataset(
        num_samples=n_samples, 
        output_file=os.path.join(output_dir, f"{n_samples}_sample_dataset.json"),
        force_diversity=force_diversity
    )
    
    # Parse and save raw dataset
    raw_dataset = []
    
    # Import tqdm for progress bar
    try:
        progress_bar = tqdm(dataset, desc='Processing examples', unit='example')
    except ImportError:
        progress_bar = dataset
        print('⚠️  tqdm not installed, using basic progress reporting')
    
    for i, example_str in enumerate(progress_bar):
        try:
            example = json.loads(example_str)
            raw_dataset.append(example)
            
            # Update progress bar description if tqdm available
            if hasattr(progress_bar, 'set_postfix'):
                progress_bar.set_postfix({'processed': i+1, 'total': len(dataset)})
            
            # Print the conversation as it's being generated
            if 'transcript' in example:
                print(f"\n📝 Generated conversation {i+1}/{len(dataset)}:")
                print("-" * 50)
                for exchange in example['transcript']:
                    if isinstance(exchange, dict):
                        if 'operator' in exchange and 'caller' in exchange:
                            print(f"Operator: {exchange['operator']}")
                            print(f"Caller: {exchange['caller']}")
                        elif 'operator' in exchange:
                            print(f"Operator: {exchange['operator']}")
                        elif 'caller' in exchange:
                            print(f"Caller: {exchange['caller']}")
                    else:
                        print(exchange)
                print("-" * 50)
                if 'scores' in example:
                    print(f"Scores: {example['scores']}")
                print()
        except Exception as e:
            error_msg = f'⚠️  Error processing example {i+1}: {e}'
            if hasattr(progress_bar, 'write'):
                progress_bar.write(error_msg)
            else:
                print(error_msg)
    
    # Save raw dataset
    raw_file = os.path.join(output_dir, f"{n_samples}_samples_raw.json")
    with open(raw_file, 'w') as f:
        json.dump(raw_dataset, f, indent=2)
    
    return {
        'raw_dataset': raw_dataset,
        'raw_file': raw_file,
        'n_samples': len(raw_dataset)
    }

if __name__ == "__main__":
    import argparse
    
    # Set up command line argument parsing
    parser = argparse.ArgumentParser(description='Generate emergency call datasets for Mistral fine-tuning')
    parser.add_argument('--samples', type=int, default=10, help='Number of samples to generate')
    parser.add_argument('--output', type=str, default='output', help='Output directory')
    parser.add_argument('--diversity', action='store_true', help='Force diverse score ranges')
    
    args = parser.parse_args()
    
    print(f'🔄 Generating {args.samples} emergency call samples...')
    
    # Generate datasets
    results = generate_n_samples(
        n_samples=args.samples,
        output_dir=args.output,
        force_diversity=args.diversity
    )
    
    # Analyze results
    if results['raw_dataset']:
        scores = []
        for example in results['raw_dataset']:
            if 'scores' in example:
                scores.append(example['scores'])
        
        if scores:
            severities = [s['severity'] for s in scores]
            seriousness = [s['seriousness'] for s in scores]
            
            print(f'\n📊 Dataset Statistics:')
            print(f'- Generated: {results["n_samples"]} samples')
            print(f'- Severity range: {min(severities)} to {max(severities)}')
            print(f'- Seriousness range: {min(seriousness)} to {max(seriousness)}')
            print(f'- Low severity: {sum(1 for s in severities if s < 5)}')
            print(f'- High severity: {sum(1 for s in severities if s >= 8)}')
    
    print(f'\n📁 Files saved to: {os.path.abspath(args.output)}/')
    print(f'- Raw dataset: {os.path.basename(results["raw_file"])}')
    print(f'\n🎉 Dataset generation complete!')