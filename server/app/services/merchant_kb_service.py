"""
Merchant Knowledge Base Service

This service provides merchant pattern matching using the merchant_kb.json file.
It supports exact matching, regex patterns, and confidence scoring.

Features:
- Load merchant patterns from JSON file
- Exact pattern matching with confidence scores
- Regular expression pattern matching
- Category mapping with confidence levels
- Auto-reload on file changes (optional)
"""

import json
import re
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, NamedTuple
from datetime import datetime
import os

logger = logging.getLogger(__name__)


class MerchantMatch(NamedTuple):
    """Merchant match result"""
    merchant: str
    category: str
    confidence: float
    match_type: str  # 'exact', 'regex', 'fallback'
    pattern: str


class MerchantKBService:
    """Service for merchant knowledge base operations"""

    def __init__(self, kb_file_path: Optional[str] = None):
        if kb_file_path:
            self.kb_file = Path(kb_file_path)
        else:
            # Default path relative to this file
            self.kb_file = Path(__file__).parent / "merchant_kb.json"

        self.kb_data: Dict = {}
        self.patterns_index: Dict[str, Dict] = {}
        self.regex_patterns: List[Dict] = []
        self.last_modified: Optional[float] = None
        self._loaded = False

    def load_kb(self, force_reload: bool = False) -> bool:
        """
        Load merchant knowledge base from JSON file

        Args:
            force_reload: Force reload even if already loaded

        Returns:
            True if loaded successfully, False otherwise
        """
        try:
            # Check if file exists
            if not self.kb_file.exists():
                logger.error(f"Merchant KB file not found: {self.kb_file}")
                return False

            # Check if reload is needed
            current_modified = self.kb_file.stat().st_mtime
            if not force_reload and self._loaded and current_modified == self.last_modified:
                return True

            # Load JSON data
            with open(self.kb_file, 'r', encoding='utf-8') as f:
                self.kb_data = json.load(f)

            # Build patterns index for fast lookup
            self._build_patterns_index()

            # Extract regex patterns
            self._load_regex_patterns()

            self.last_modified = current_modified
            self._loaded = True

            total_patterns = len(self.patterns_index)
            total_regex = len(self.regex_patterns)

            logger.info(f"✅ Merchant KB loaded: {total_patterns} exact patterns, {total_regex} regex patterns")
            return True

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in merchant KB: {e}")
            return False
        except Exception as e:
            logger.error(f"Error loading merchant KB: {e}")
            return False

    def _build_patterns_index(self):
        """Build a flat index of all merchant patterns for fast lookup"""
        self.patterns_index = {}

        merchant_patterns = self.kb_data.get('merchant_patterns', {})
        for category_group, patterns in merchant_patterns.items():
            for pattern, info in patterns.items():
                # Store pattern in uppercase for case-insensitive matching
                self.patterns_index[pattern.upper()] = {
                    'name': info.get('name', pattern),
                    'category': info.get('category', 'other'),
                    'confidence': float(info.get('confidence', 0.5)),
                    'group': category_group,
                    'pattern': pattern
                }

    def _load_regex_patterns(self):
        """Load and compile regex patterns"""
        self.regex_patterns = []

        regex_data = self.kb_data.get('regex_patterns', {})
        patterns = regex_data.get('patterns', [])

        for pattern_info in patterns:
            try:
                compiled_pattern = re.compile(pattern_info['pattern'], re.IGNORECASE)
                self.regex_patterns.append({
                    'pattern': compiled_pattern,
                    'raw_pattern': pattern_info['pattern'],
                    'merchant': pattern_info.get('merchant', 'Unknown'),
                    'category': pattern_info.get('category', 'other'),
                    'confidence': float(pattern_info.get('confidence', 0.5))
                })
            except re.error as e:
                logger.warning(f"Invalid regex pattern '{pattern_info['pattern']}': {e}")

    def match_merchant(self, transaction_desc: str) -> Optional[MerchantMatch]:
        """
        Match transaction description against merchant patterns

        Args:
            transaction_desc: Transaction description text

        Returns:
            MerchantMatch if found, None otherwise
        """
        if not self._loaded:
            if not self.load_kb():
                return None

        # Normalize input
        desc_upper = transaction_desc.upper().strip()

        # Step 1: Try exact pattern matching (highest priority)
        exact_match = self._match_exact_patterns(desc_upper)
        if exact_match:
            return exact_match

        # Step 2: Try regex pattern matching
        regex_match = self._match_regex_patterns(transaction_desc)
        if regex_match:
            return regex_match

        return None

    def _match_exact_patterns(self, desc_upper: str) -> Optional[MerchantMatch]:
        """Match against exact patterns"""
        best_match = None
        best_confidence = 0.0

        # Try to find pattern matches, prioritizing longer/more specific patterns
        for pattern, info in self.patterns_index.items():
            if pattern in desc_upper:
                confidence = info['confidence']

                # Prefer longer patterns (more specific)
                pattern_specificity = len(pattern) / 100.0  # Small bonus for longer patterns
                adjusted_confidence = confidence + pattern_specificity

                if adjusted_confidence > best_confidence:
                    best_confidence = adjusted_confidence
                    best_match = MerchantMatch(
                        merchant=info['name'],
                        category=info['category'],
                        confidence=confidence,  # Return original confidence, not adjusted
                        match_type='exact',
                        pattern=pattern
                    )

        return best_match

    def _match_regex_patterns(self, transaction_desc: str) -> Optional[MerchantMatch]:
        """Match against regex patterns"""
        for pattern_info in self.regex_patterns:
            if pattern_info['pattern'].search(transaction_desc):
                return MerchantMatch(
                    merchant=pattern_info['merchant'],
                    category=pattern_info['category'],
                    confidence=pattern_info['confidence'],
                    match_type='regex',
                    pattern=pattern_info['raw_pattern']
                )

        return None

    def get_stats(self) -> Dict:
        """Get statistics about the loaded knowledge base"""
        if not self._loaded:
            return {'loaded': False}

        metadata = self.kb_data.get('metadata', {})

        # Count patterns by category
        category_counts = {}
        for info in self.patterns_index.values():
            category = info['category']
            category_counts[category] = category_counts.get(category, 0) + 1

        return {
            'loaded': True,
            'file_path': str(self.kb_file),
            'last_modified': datetime.fromtimestamp(self.last_modified) if self.last_modified else None,
            'version': metadata.get('version', 'unknown'),
            'total_exact_patterns': len(self.patterns_index),
            'total_regex_patterns': len(self.regex_patterns),
            'categories': list(category_counts.keys()),
            'category_counts': category_counts,
            'coverage': metadata.get('categories_covered', [])
        }


# Global instance
merchant_kb = MerchantKBService()