#!/usr/bin/env python3
"""
Merchant Knowledge Base Management Utility

This script helps manage the merchant_kb.json file with various utilities:
- Add new merchants
- Validate JSON structure
- Import from CSV
- Export statistics
- Test pattern matching

Usage:
    python manage_merchant_kb.py --help
    python manage_merchant_kb.py add --pattern "NEWSTORE" --name "New Store" --category "shopping"
    python manage_merchant_kb.py validate
    python manage_merchant_kb.py stats
"""

import json
import csv
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import re

# Path to the merchant KB file
KB_FILE = Path(__file__).parent.parent / "app" / "services" / "merchant_kb.json"

class MerchantKBManager:
    def __init__(self, kb_file: Path = KB_FILE):
        self.kb_file = kb_file
        self.kb_data = self.load_kb()

    def load_kb(self) -> Dict:
        """Load the merchant knowledge base from JSON file"""
        try:
            with open(self.kb_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"❌ Merchant KB file not found: {self.kb_file}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in merchant KB: {e}")
            sys.exit(1)

    def save_kb(self) -> bool:
        """Save the merchant knowledge base to JSON file"""
        try:
            # Create backup first
            backup_file = self.kb_file.with_suffix(f'.backup.{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(self.kb_data, f, indent=2, ensure_ascii=False)

            # Update metadata
            self.kb_data['metadata']['last_updated'] = datetime.now().isoformat() + 'Z'

            # Save main file
            with open(self.kb_file, 'w', encoding='utf-8') as f:
                json.dump(self.kb_data, f, indent=2, ensure_ascii=False)

            print(f"✅ Merchant KB saved successfully")
            print(f"📁 Backup created: {backup_file}")
            return True
        except Exception as e:
            print(f"❌ Failed to save merchant KB: {e}")
            return False

    def validate(self) -> bool:
        """Validate the merchant KB structure and data"""
        errors = []

        # Check required top-level keys
        required_keys = ['metadata', 'merchant_patterns', 'regex_patterns', 'admin_instructions']
        for key in required_keys:
            if key not in self.kb_data:
                errors.append(f"Missing required key: {key}")

        # Validate merchant patterns
        if 'merchant_patterns' in self.kb_data:
            total_patterns = 0
            for category, patterns in self.kb_data['merchant_patterns'].items():
                for pattern, info in patterns.items():
                    total_patterns += 1

                    # Check required fields
                    required_fields = ['name', 'category', 'confidence']
                    for field in required_fields:
                        if field not in info:
                            errors.append(f"Pattern '{pattern}' missing field: {field}")

                    # Validate confidence score
                    if 'confidence' in info:
                        confidence = info['confidence']
                        if not isinstance(confidence, (int, float)) or not (0 <= confidence <= 1):
                            errors.append(f"Pattern '{pattern}' has invalid confidence: {confidence}")

            # Update total count in metadata
            if 'metadata' in self.kb_data:
                self.kb_data['metadata']['total_patterns'] = total_patterns

        # Validate regex patterns
        if 'regex_patterns' in self.kb_data and 'patterns' in self.kb_data['regex_patterns']:
            for i, regex_pattern in enumerate(self.kb_data['regex_patterns']['patterns']):
                try:
                    re.compile(regex_pattern['pattern'])
                except re.error as e:
                    errors.append(f"Invalid regex pattern {i}: {e}")

        if errors:
            print("❌ Validation failed:")
            for error in errors:
                print(f"  - {error}")
            return False
        else:
            print("✅ Merchant KB validation passed")
            return True

    def add_merchant(self, pattern: str, name: str, category: str, confidence: float = 0.80) -> bool:
        """Add a new merchant pattern"""
        # Find appropriate category group
        category_mapping = {
            'food': 'food_and_dining',
            'shopping': 'e_commerce_shopping',
            'transport': 'transportation',
            'entertainment': 'entertainment_subscriptions',
            'bills': 'bills_utilities',
            'healthcare': 'healthcare',
            'education': 'education',
            'other': 'payment_platforms'
        }

        category_group = category_mapping.get(category, 'payment_platforms')

        # Ensure category group exists
        if category_group not in self.kb_data['merchant_patterns']:
            self.kb_data['merchant_patterns'][category_group] = {}

        # Check if pattern already exists
        for group in self.kb_data['merchant_patterns'].values():
            if pattern.upper() in group:
                print(f"⚠️  Pattern '{pattern}' already exists")
                return False

        # Add new pattern
        self.kb_data['merchant_patterns'][category_group][pattern.upper()] = {
            'name': name,
            'category': category,
            'confidence': confidence
        }

        print(f"✅ Added merchant pattern: {pattern.upper()} -> {name} ({category})")
        return True

    def get_stats(self) -> Dict:
        """Get statistics about the merchant KB"""
        stats = {
            'total_patterns': 0,
            'categories': {},
            'confidence_distribution': {'high': 0, 'medium': 0, 'low': 0},
            'category_groups': len(self.kb_data.get('merchant_patterns', {})),
            'regex_patterns': len(self.kb_data.get('regex_patterns', {}).get('patterns', []))
        }

        for category_group, patterns in self.kb_data.get('merchant_patterns', {}).items():
            for pattern, info in patterns.items():
                stats['total_patterns'] += 1

                # Count by category
                cat = info.get('category', 'unknown')
                stats['categories'][cat] = stats['categories'].get(cat, 0) + 1

                # Count by confidence
                confidence = info.get('confidence', 0)
                if confidence >= 0.9:
                    stats['confidence_distribution']['high'] += 1
                elif confidence >= 0.7:
                    stats['confidence_distribution']['medium'] += 1
                else:
                    stats['confidence_distribution']['low'] += 1

        return stats

    def print_stats(self):
        """Print formatted statistics"""
        stats = self.get_stats()

        print("📊 Merchant Knowledge Base Statistics")
        print("=" * 40)
        print(f"Total Patterns: {stats['total_patterns']}")
        print(f"Category Groups: {stats['category_groups']}")
        print(f"Regex Patterns: {stats['regex_patterns']}")
        print()

        print("📈 By Category:")
        for category, count in sorted(stats['categories'].items()):
            print(f"  {category:12}: {count:3d}")
        print()

        print("🎯 Confidence Distribution:")
        print(f"  High (0.9+)  : {stats['confidence_distribution']['high']:3d}")
        print(f"  Medium (0.7+): {stats['confidence_distribution']['medium']:3d}")
        print(f"  Low (<0.7)   : {stats['confidence_distribution']['low']:3d}")

def main():
    parser = argparse.ArgumentParser(description='Merchant Knowledge Base Management Utility')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Add merchant command
    add_parser = subparsers.add_parser('add', help='Add new merchant pattern')
    add_parser.add_argument('--pattern', required=True, help='Merchant pattern (e.g., NEWSTORE)')
    add_parser.add_argument('--name', required=True, help='Merchant display name')
    add_parser.add_argument('--category', required=True, choices=[
        'food', 'shopping', 'transport', 'entertainment', 'bills', 
        'healthcare', 'education', 'salary', 'investment', 'other'
    ], help='Merchant category')
    add_parser.add_argument('--confidence', type=float, default=0.80, help='Confidence score (0.0-1.0)')

    # Validate command
    subparsers.add_parser('validate', help='Validate merchant KB structure')

    # Stats command
    subparsers.add_parser('stats', help='Show merchant KB statistics')

    # Parse arguments
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Initialize manager
    manager = MerchantKBManager()

    # Execute command
    if args.command == 'add':
        if manager.add_merchant(args.pattern, args.name, args.category, args.confidence):
            manager.save_kb()

    elif args.command == 'validate':
        if manager.validate():
            manager.save_kb()  # Save any metadata updates

    elif args.command == 'stats':
        manager.print_stats()

if __name__ == '__main__':
    main()