"""
Advanced Grouping Logic for CSV Processing Dashboard
Handles intelligent product grouping with main groups, sub groups, and structured plans
Supports chunked processing for large datasets
"""

import pandas as pd
import json
import re
import os
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import uuid
from collections import defaultdict, Counter
import openai
from difflib import SequenceMatcher
try:
    import numpy as np
except ImportError:
    # Fallback if numpy is not available
    class numpy_fallback:
        @staticmethod
        def mean(values):
            return sum(values) / len(values) if values else 0
    np = numpy_fallback()

class ProductGroupingEngine:
    """Advanced product grouping engine with AI-powered insights and chunked processing"""
    
    def __init__(self, openai_api_key: str):
        self.openai_api_key = openai_api_key
        openai.api_key = openai_api_key
        
        # Processing configuration
        self.chunk_size = 1000  # Process 1000 rows at a time
        self.sample_size_per_chunk = 100  # Sample from each chunk for analysis
        
        # Enhanced core product type keywords for intelligent grouping
        self.core_product_keywords = {
            'electronics': {
                'primary': ['laptop', 'computer', 'phone', 'tablet', 'monitor', 'screen', 'display'],
                'secondary': ['keyboard', 'mouse', 'speaker', 'headphone', 'earphone', 'camera', 'printer', 'scanner', 'router', 'modem']
            },
            'furniture': {
                'primary': ['chair', 'desk', 'table', 'sofa', 'couch', 'bed', 'mattress'],
                'secondary': ['cabinet', 'shelf', 'bookshelf', 'wardrobe', 'drawer', 'dresser', 'nightstand']
            },
            'office_supplies': {
                'primary': ['pen', 'pencil', 'paper', 'notebook', 'stapler', 'clip'],
                'secondary': ['folder', 'binder', 'marker', 'eraser', 'tape', 'glue', 'scissors']
            },
            'food_beverages': {
                'primary': ['rice', 'flour', 'sugar', 'salt', 'oil', 'pasta', 'cereal', 'bread'],
                'secondary': ['milk', 'cheese', 'butter', 'yogurt', 'juice', 'coffee', 'tea', 'water']
            },
            'clothing': {
                'primary': ['shirt', 'pants', 'dress', 'shoes', 'jacket', 'sweater'],
                'secondary': ['jeans', 'socks', 'hat', 'gloves', 'belt', 'tie', 'scarf']
            },
            'tools_hardware': {
                'primary': ['hammer', 'screwdriver', 'drill', 'saw', 'wrench', 'pliers'],
                'secondary': ['measuring', 'level', 'knife', 'blade', 'bit', 'nail', 'screw', 'bolt']
            },
            'cleaning_hygiene': {
                'primary': ['detergent', 'soap', 'cleaner', 'disinfectant', 'bleach'],
                'secondary': ['sponge', 'brush', 'vacuum', 'mop', 'tissue', 'towel', 'shampoo', 'toothpaste']
            },
            'automotive': {
                'primary': ['tire', 'battery', 'oil', 'filter', 'brake'],
                'secondary': ['light', 'mirror', 'seat', 'engine', 'wire', 'fluid']
            }
        }
        
        # Enhanced patterns for normalization
        self.size_weight_patterns = [
            r'\b\d+\.?\d*\s*(kg|g|lb|oz|pound|gram|kilogram|ton)\b',
            r'\b\d+\.?\d*\s*(ml|l|liter|litre|fl\s*oz|gallon|cup|pint|quart)\b',
            r'\b\d+\.?\d*\s*(mm|cm|m|meter|metre|inch|in|ft|foot|feet|yard)\b',
            r'\b\d+\.?\d*\s*(pack|pcs|pieces|count|ct|box|bottle|can|bag)\b',
            r'\b(small|medium|large|xl|xxl|xs|mini|micro|mega|super|extra)\b',
            r'\b\d+["\']?\s*x\s*\d+["\']?\s*x?\s*\d*["\']?\b',  # dimensions
            r'\b\d+\s*(size|count|piece)\b'
        ]
        
        # Brand and model patterns to remove
        self.brand_model_patterns = [
            r'\b(apple|samsung|dell|hp|lenovo|asus|acer|sony|lg|canon|epson|nike|adidas|microsoft|google|intel|amd)\b',
            r'\b(inc\.?|corp\.?|ltd\.?|llc|co\.?|company)\b',
            r'\bmodel\s*[a-z0-9\-]+\b',
            r'\b[a-z]*\d{3,}\b',  # Model numbers like ABC123, X1000, etc.
            r'\bv\d+(\.\d+)?\b',  # Version numbers
            r'\b(gen|generation)\s*\d+\b'
        ]
        
        # Color patterns to remove
        self.color_patterns = [
            r'\b(red|blue|green|yellow|orange|purple|pink|black|white|grey|gray|brown|silver|gold|bronze)\b',
            r'\b(dark|light|bright)\s+(red|blue|green|yellow|orange|purple|pink|black|white|grey|gray|brown)\b'
        ]
        
        # Material patterns to normalize
        self.material_patterns = [
            r'\b(plastic|metal|steel|aluminum|wood|wooden|glass|ceramic|cotton|polyester|leather)\b'
        ]

    def normalize_product_name(self, product_name: str) -> str:
        """Enhanced normalization focusing on core product identity"""
        if not isinstance(product_name, str):
            return str(product_name).lower()
            
        normalized = product_name.lower().strip()
        
        # Remove brand patterns first
        for pattern in self.brand_model_patterns:
            normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE)
        
        # Remove color patterns (unless it's part of the core product)
        for pattern in self.color_patterns:
            normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE)
        
        # Remove size/weight patterns
        for pattern in self.size_weight_patterns:
            normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE)
        
        # Clean up special characters and extra spaces
        normalized = re.sub(r'[^\w\s]', ' ', normalized)
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized

    def extract_core_product_type(self, product_name: str) -> Tuple[str, str, float]:
        """Extract the core product type with confidence score"""
        normalized_name = self.normalize_product_name(product_name)
        words = normalized_name.split()
        
        best_category = 'other'
        best_subcategory = 'general'
        best_score = 0.0
        
        # Check against primary keywords first (higher weight)
        for category, keyword_groups in self.core_product_keywords.items():
            for keyword in keyword_groups['primary']:
                for word in words:
                    if keyword in word or word in keyword:
                        score = len(keyword) / max(len(word), len(keyword))
                        if score > best_score:
                            best_score = score
                            best_category = category
                            best_subcategory = 'primary'
        
        # Check secondary keywords if no primary match found
        if best_score < 0.8:
            for category, keyword_groups in self.core_product_keywords.items():
                for keyword in keyword_groups['secondary']:
                    for word in words:
                        if keyword in word or word in keyword:
                            score = (len(keyword) / max(len(word), len(keyword))) * 0.7  # Lower weight
                            if score > best_score:
                                best_score = score
                                best_category = category
                                best_subcategory = 'secondary'
        
        # If still no good match, use the longest meaningful word
        if best_score < 0.5 and words:
            meaningful_words = [w for w in words if len(w) > 2]
            if meaningful_words:
                best_subcategory = meaningful_words[0]
        
        return best_category, best_subcategory, best_score

    def calculate_product_similarity(self, item1: Dict, item2: Dict) -> float:
        """Calculate similarity between two products based on multiple factors"""
        name1 = self.normalize_product_name(item1.get('name', ''))
        name2 = self.normalize_product_name(item2.get('name', ''))
        
        # Core type similarity
        type1, subtype1, score1 = self.extract_core_product_type(item1.get('name', ''))
        type2, subtype2, score2 = self.extract_core_product_type(item2.get('name', ''))
        
        type_similarity = 1.0 if type1 == type2 and type1 != 'other' else 0.0
        
        # String similarity
        string_similarity = SequenceMatcher(None, name1, name2).ratio()
        
        # Word overlap similarity
        words1 = set(name1.split())
        words2 = set(name2.split())
        if words1 and words2:
            word_overlap = len(words1.intersection(words2)) / len(words1.union(words2))
            else:
            word_overlap = 0.0
        
        # Category similarity (if available)
        cat1 = str(item1.get('category', '')).lower()
        cat2 = str(item2.get('category', '')).lower()
        category_similarity = 1.0 if cat1 == cat2 and cat1 != 'unknown' else 0.0
        
        # Weighted combination
        final_similarity = (
            type_similarity * 0.4 +
            string_similarity * 0.3 +
            word_overlap * 0.2 +
            category_similarity * 0.1
        )
        
        return final_similarity

    def process_chunk_data(self, chunk_df: pd.DataFrame, chunk_index: int) -> Dict[str, Any]:
        """Process a single chunk of data and extract patterns"""
        
        print(f"Processing chunk {chunk_index + 1} with {len(chunk_df)} rows...")
        
        # Sample from chunk if it's too large
        if len(chunk_df) > self.sample_size_per_chunk:
            sample_df = chunk_df.sample(n=self.sample_size_per_chunk, random_state=42)
        else:
            sample_df = chunk_df
        
        # Convert chunk to items
        items = []
        for index, row in sample_df.iterrows():
            try:
                item = {
                    "id": str(index),
                    "name": self.safe_str(row.iloc[0] if len(row) > 0 else None, f"Item_{index}"),
                    "price": self.safe_float(row.iloc[1] if len(row) > 1 else None),
                    "category": self.safe_str(row.iloc[2] if len(row) > 2 else None, "Unknown"),
                    "quantity": self.safe_int(row.iloc[3] if len(row) > 3 else None),
                    "row_data": {str(k): str(v) for k, v in row.to_dict().items()},  # Ensure serializable
                    "chunk_index": chunk_index
                }
                items.append(item)
            except Exception as e:
                print(f"Error processing row {index}: {e}")
                # Create a minimal item
                items.append({
                    "id": str(index),
                    "name": f"Item_{index}",
                    "price": 0.0,
                    "category": "Unknown",
                    "quantity": 1,
                    "row_data": {},
                    "chunk_index": chunk_index
                })
        
        # Analyze product types in this chunk
        type_analysis = defaultdict(list)
        for item in items:
            core_type, sub_type, confidence = self.extract_core_product_type(item['name'])
            if confidence > 0.3:  # Lower threshold for chunk analysis
                type_analysis[core_type].append({
                    'item': item,
                    'confidence': confidence,
                    'sub_type': sub_type
                })
        
        # Extract common patterns
        normalized_names = [self.normalize_product_name(item['name']) for item in items]
        all_words = []
        for name in normalized_names:
            all_words.extend(name.split())
        
        word_frequency = Counter(all_words)
        common_patterns = [word for word, count in word_frequency.most_common(20) if len(word) > 2]
        
        return {
            'chunk_index': chunk_index,
            'items': items,
            'type_analysis': dict(type_analysis),
            'common_patterns': common_patterns,
            'total_items': len(items),
            'chunk_size': len(chunk_df)
        }

    def merge_chunk_analyses(self, chunk_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Merge analysis results from all chunks to determine final grouping strategy"""
        
        print(f"Merging analysis from {len(chunk_results)} chunks...")
        
        # Combine all items
        all_items = []
        for chunk_result in chunk_results:
            all_items.extend(chunk_result['items'])
        
        # Combine type analysis
        combined_type_analysis = defaultdict(list)
        for chunk_result in chunk_results:
            for type_name, type_items in chunk_result['type_analysis'].items():
                combined_type_analysis[type_name].extend(type_items)
        
        # Combine common patterns
        all_patterns = []
        for chunk_result in chunk_results:
            all_patterns.extend(chunk_result['common_patterns'])
        
        pattern_frequency = Counter(all_patterns)
        global_patterns = [word for word, count in pattern_frequency.most_common(30) if count >= 2]
        
        # Determine final main groups based on frequency and size
        main_group_candidates = {}
        for type_name, type_items in combined_type_analysis.items():
            if len(type_items) >= 3:  # Need at least 3 items to form a group
                avg_confidence = np.mean([item['confidence'] for item in type_items])
                main_group_candidates[type_name] = {
                    'items': type_items,
                    'count': len(type_items),
                    'avg_confidence': avg_confidence
                }
        
        # Sort by count and confidence
        sorted_groups = sorted(main_group_candidates.items(), 
                             key=lambda x: (x[1]['count'], x[1]['avg_confidence']), 
                             reverse=True)
        
        return {
            'all_items': all_items,
            'main_groups': dict(sorted_groups),
            'global_patterns': global_patterns,
            'total_items_processed': len(all_items),
            'total_chunks': len(chunk_results)
        }

    def create_final_groups_from_analysis(self, merged_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Create final group structure from merged analysis"""
        
        print("Creating final group structure...")
        
        main_groups = {}
        ungrouped_items = []
        
        # Create main groups from analysis
        for group_name, group_data in merged_analysis['main_groups'].items():
            group_id = str(uuid.uuid4())
            display_name = group_name.replace('_', ' ').title()
            
            # Extract items from analysis structure
            group_items = [item_data['item'] for item_data in group_data['items']]
            
            # Create sub groups within this main group
            sub_groups = self.create_sub_groups_from_items(group_items)
            
            main_groups[group_id] = {
                "id": group_id,
                "name": display_name,
                "enabled": True,
                "sub_groups": sub_groups,
                "total_items": len(group_items),
                "estimated_savings": self.calculate_estimated_savings(group_items)
            }
        
        # Handle items that didn't fit into any group
        grouped_item_ids = set()
        for group_data in merged_analysis['main_groups'].values():
            for item_data in group_data['items']:
                grouped_item_ids.add(item_data['item']['id'])
        
        for item in merged_analysis['all_items']:
            if item['id'] not in grouped_item_ids:
                ungrouped_items.append(item)
        
        return {
            "main_groups": main_groups,
            "ungrouped_items": ungrouped_items,
            "metadata": {
                "total_items": merged_analysis['total_items_processed'],
                "total_groups": len(main_groups),
                "total_chunks_processed": merged_analysis['total_chunks'],
                "grouping_method": "chunked_intelligent_analysis",
                "created_at": datetime.now().isoformat()
            }
        }

    def create_sub_groups_from_items(self, items: List[Dict], similarity_threshold: float = 0.7) -> Dict[str, Any]:
        """Create sub groups from a list of items"""
        if len(items) <= 3:
            # Small groups don't need sub-grouping
            return {
                        "default": {
                            "id": str(uuid.uuid4()),
                            "name": "Default",
                    "items": items
                }
            }
        
        # Use clustering approach for sub-grouping
        sub_groups = {}
        assigned_items = set()
        
        # Start with first item as first sub-group
        remaining_items = items.copy()
        
        while remaining_items:
            # Take first unassigned item as seed for new sub-group
            seed_item = remaining_items.pop(0)
            if seed_item['id'] in assigned_items:
                continue
                
            # Find all items similar to this seed
            sub_group_items = [seed_item]
            assigned_items.add(seed_item['id'])
            
            items_to_remove = []
            for item in remaining_items:
                if item['id'] in assigned_items:
                    continue
                    
                similarity = self.calculate_product_similarity(seed_item, item)
                if similarity >= similarity_threshold:
                    sub_group_items.append(item)
                    assigned_items.add(item['id'])
                    items_to_remove.append(item)
            
            # Remove assigned items from remaining
            for item in items_to_remove:
                if item in remaining_items:
                    remaining_items.remove(item)
            
            # Create sub-group if it has enough items
            if len(sub_group_items) >= 1:  # Allow single-item sub-groups
                sub_group_id = str(uuid.uuid4())
                # Generate meaningful sub-group name
                sub_group_name = self.generate_sub_group_name(sub_group_items)
                
                sub_groups[sub_group_id] = {
                    "id": sub_group_id,
                    "name": sub_group_name,
                    "items": sub_group_items
                }
        
        # Ensure we have at least a default sub-group
        if not sub_groups:
            sub_groups["default"] = {
                "id": str(uuid.uuid4()),
                "name": "Default",
                "items": items
            }
        
        return sub_groups

    def generate_sub_group_name(self, items: List[Dict]) -> str:
        """Generate meaningful sub-group name based on items"""
        if not items:
            return "Empty Group"
        
        if len(items) == 1:
            return self.clean_group_name(items[0]['name'])
        
        # Find common words
        names = [self.normalize_product_name(item.get('name', '')) for item in items]
        
        # Get most common meaningful words
        all_words = []
        for name in names:
            all_words.extend(name.split())
        
        # Count word frequency
        word_counts = Counter(all_words)
        common_words = [word for word, count in word_counts.most_common(3) 
                       if len(word) > 2 and count > 1]
        
        if common_words:
            return ' '.join(common_words[:2]).title()
            else:
            # Fallback to first item's key word
            first_name = names[0]
            words = [w for w in first_name.split() if len(w) > 2]
            if words:
                return words[0].title()
            else:
                return f"Group {len(items)} items"

    def generate_intelligent_groups(self, df: pd.DataFrame, max_items: int = None) -> Dict[str, Any]:
        """Main entry point for generating intelligent groups with chunked processing"""
        
        # Basic validation
        if df is None or df.empty:
            raise ValueError("DataFrame is empty or None")
        
        if len(df.columns) == 0:
            raise ValueError("DataFrame has no columns")
        
        total_rows = len(df)
        print(f"Starting intelligent grouping for {total_rows} rows with {len(df.columns)} columns...")
        
        # Detect column types once for the entire dataset
        price_col = self.detect_price_column(df)
        category_col = self.detect_category_column(df)
        quantity_col = self.detect_quantity_column(df)
        
        print(f"Detected columns - Price: {price_col}, Category: {category_col}, Quantity: {quantity_col}")
        
        # Process data in chunks
        chunk_results = []
        total_chunks = (total_rows + self.chunk_size - 1) // self.chunk_size
        
        for chunk_index in range(0, total_rows, self.chunk_size):
            # Get chunk
            chunk_end = min(chunk_index + self.chunk_size, total_rows)
            chunk_df = df.iloc[chunk_index:chunk_end].copy()
            chunk_number = chunk_index // self.chunk_size
            
            # Process chunk
            try:
                print(f"Processing chunk {chunk_number + 1}/{total_chunks} (rows {chunk_index}-{chunk_end-1})")
                chunk_result = self.process_chunk_data(chunk_df, chunk_number)
                chunk_results.append(chunk_result)
                print(f"Chunk {chunk_number + 1} completed successfully")
            except Exception as e:
                print(f"Error processing chunk {chunk_number + 1}: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        if not chunk_results:
            raise Exception("No chunks were processed successfully")
        
        # Merge all chunk analyses
        merged_analysis = self.merge_chunk_analyses(chunk_results)
        
        # Create final group structure
        final_groups = self.create_final_groups_from_analysis(merged_analysis)
        
        print(f"Grouping completed: {len(final_groups['main_groups'])} groups, {len(final_groups['ungrouped_items'])} ungrouped items")
        
        return final_groups

    def detect_price_column(self, df: pd.DataFrame) -> Optional[int]:
        """Detect price column intelligently"""
        columns = df.columns.tolist()
        
        # First try by column names
        for i, col in enumerate(columns):
            col_lower = str(col).lower()
            if any(keyword in col_lower for keyword in ['price', 'cost', 'amount', 'value', 'rate']):
                return i
        
        # Then try by data patterns
        for i in range(1, min(len(columns), 5)):
            try:
                sample_values = df.iloc[:min(100, len(df)), i].dropna()
                if len(sample_values) > 0:
                    numeric_count = 0
                    for val in sample_values:
                        try:
                            float(str(val).replace(',', '').replace('$', '').strip())
                            numeric_count += 1
                        except:
                            pass
                    
                    if numeric_count / len(sample_values) > 0.7:
                        return i
            except:
                pass
        
        return None

    def detect_category_column(self, df: pd.DataFrame) -> Optional[int]:
        """Detect category column intelligently"""
        columns = df.columns.tolist()
        
        for i, col in enumerate(columns):
            col_lower = str(col).lower()
            if any(keyword in col_lower for keyword in ['category', 'type', 'class', 'group', 'dept']):
                return i
        
        # Look for mostly text columns
        for i in range(1, min(len(columns), 5)):
            try:
                sample_values = df.iloc[:min(100, len(df)), i].dropna()
                if len(sample_values) > 0:
                    text_count = 0
                    for val in sample_values:
                        if isinstance(val, str) and not val.replace('.', '').isdigit():
                            text_count += 1
                    
                    if text_count / len(sample_values) > 0.7:
                        return i
            except:
                pass
        
        return None

    def detect_quantity_column(self, df: pd.DataFrame) -> Optional[int]:
        """Detect quantity column intelligently"""
        columns = df.columns.tolist()
        
        for i, col in enumerate(columns):
            col_lower = str(col).lower()
            if any(keyword in col_lower for keyword in ['quantity', 'qty', 'count', 'number', 'stock']):
                return i
        
        return None

    def safe_float(self, value, default=0.0):
        """Safely convert value to float"""
        try:
            if pd.isna(value) or value == '':
                return default
            # Handle numpy types
            if hasattr(value, 'item'):
                value = value.item()
            return float(str(value).replace(',', '').replace('$', '').strip())
        except (ValueError, TypeError):
            return default

    def safe_int(self, value, default=1):
        """Safely convert value to int"""
        try:
            if pd.isna(value) or value == '':
                return default
            # Handle numpy types
            if hasattr(value, 'item'):
                value = value.item()
            return int(float(str(value).replace(',', '').strip()))
        except (ValueError, TypeError):
            return default

    def safe_str(self, value, default="Unknown"):
        """Safely convert value to string"""
        try:
            if pd.isna(value) or value == '':
                return default
            # Handle numpy types
            if hasattr(value, 'item'):
                value = value.item()
            return str(value).strip()
        except:
            return default

    def calculate_estimated_savings(self, items: List[Dict]) -> str:
        """Calculate estimated bulk procurement savings"""
        total_value = sum(item.get('price', 0) * item.get('quantity', 1) for item in items)
        item_count = len(items)
        
        # Savings estimation based on quantity and total value
        if item_count >= 10:
            savings_percent = min(25, 10 + (item_count - 10) * 0.5)
        elif item_count >= 5:
            savings_percent = min(15, 5 + (item_count - 5) * 1)
        else:
            savings_percent = max(5, item_count * 2)
        
        return f"{savings_percent:.0f}%"

    def create_structured_plan(self, groups_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a structured plan from groups data"""
        plan = {
            "id": str(uuid.uuid4()),
            "name": f"Structured Plan {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "created_at": datetime.now().isoformat(),
            "version": "1.0",
            "grouping_rules": [],
            "main_groups": {},
            "metadata": groups_data.get("metadata", {})
        }
        
        # Extract grouping rules from main groups
        for group_name, group_data in groups_data.get("main_groups", {}).items():
            # Create grouping rules based on the items in each group
            grouping_rule = {
                "group_name": group_name,
                "core_keywords": self.extract_keywords_from_items(group_data),
                "similarity_threshold": 0.6,
                "enabled": group_data.get("enabled", True)
            }
            plan["grouping_rules"].append(grouping_rule)
            
            # Store group structure
            plan["main_groups"][group_name] = {
                "name": group_data.get("name", group_name),
                "enabled": group_data.get("enabled", True),
                "sub_groups": {
                    sg_name: {
                        "name": sg_data.get("name", sg_name),
                        "keywords": self.extract_keywords_from_items({"items": sg_data.get("items", [])})
                    }
                    for sg_name, sg_data in group_data.get("sub_groups", {}).items()
                }
            }
        
        return plan

    def extract_keywords_from_items(self, group_data: Dict) -> List[str]:
        """Extract relevant keywords from group items"""
        items = group_data.get("items", [])
        if not items:
            return []
        
        # Get normalized names and extract common keywords
        normalized_names = [self.normalize_product_name(item.get("name", "")) for item in items]
        
        # Find common words across items
        all_words = []
        for name in normalized_names:
            all_words.extend(name.split())
        
        # Count word frequency and get most common
        word_counts = Counter(all_words)
        
        # Return top keywords (excluding very short words)
        keywords = [word for word, count in word_counts.most_common(5) if len(word) > 2]
        return keywords

    def apply_structured_plan(self, df: pd.DataFrame, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Apply a structured plan to a new dataset"""
        
        # Convert DataFrame to items
        items = []
        for index, row in df.iterrows():
            item = {
                "id": str(index),
                "name": str(row.iloc[0]) if len(row) > 0 else f"Item_{index}",
                "price": float(row.iloc[1]) if len(row) > 1 and pd.notnull(row.iloc[1]) else 0.0,
                "category": str(row.iloc[2]) if len(row) > 2 else "Unknown",
                "quantity": int(row.iloc[3]) if len(row) > 3 and pd.notnull(row.iloc[3]) else 1,
                "row_data": row.to_dict()
            }
            items.append(item)
        
        # Initialize result structure
        result = {
            "main_groups": {},
            "ungrouped_items": [],
            "metadata": {
                "total_items": len(items),
                "plan_applied": plan.get("name", "Unknown Plan"),
                "applied_at": datetime.now().isoformat()
            }
        }
        
        # Create groups based on plan structure
        for group_name, group_config in plan.get("main_groups", {}).items():
            if not group_config.get("enabled", True):
                continue
                
            result["main_groups"][group_name] = {
                "id": str(uuid.uuid4()),
                "name": group_config.get("name", group_name),
                "enabled": True,
                "sub_groups": {},
                "total_items": 0,
                "estimated_savings": "0%"
            }
            
            # Initialize sub groups
            for sg_name, sg_config in group_config.get("sub_groups", {}).items():
                result["main_groups"][group_name]["sub_groups"][sg_name] = {
                    "id": str(uuid.uuid4()),
                    "name": sg_config.get("name", sg_name),
                    "items": []
                }
        
        # Assign items to groups based on plan rules
        assigned_items = set()
        
        for rule in plan.get("grouping_rules", []):
            if not rule.get("enabled", True):
                continue
                
            group_name = rule["group_name"]
            keywords = rule.get("core_keywords", [])
            threshold = rule.get("similarity_threshold", 0.6)
            
            if group_name not in result["main_groups"]:
                continue
            
            # Find items that match this rule
            for item in items:
                if item["id"] in assigned_items:
                    continue
                    
                item_name = self.normalize_product_name(item["name"])
                
                # Check keyword matches
                keyword_matches = sum(1 for keyword in keywords if keyword in item_name)
                keyword_score = keyword_matches / max(len(keywords), 1) if keywords else 0
                
                # Check similarity with group name
                similarity_score = self.calculate_product_similarity(item, {"name": group_name})
                
                # Combined scoring
                total_score = max(keyword_score, similarity_score)
                
                if total_score >= threshold:
                    # Assign to default sub group or best matching sub group
                    best_subgroup = "default"
                    if group_name in result["main_groups"]:
                        for sg_name, sg_config in plan["main_groups"][group_name]["sub_groups"].items():
                            sg_keywords = sg_config.get("keywords", [])
                            sg_score = sum(1 for kw in sg_keywords if kw in item_name) / max(len(sg_keywords), 1)
                            if sg_score > 0.5:
                                best_subgroup = sg_name
                                break
                    
                    # Add item to sub group
                    if best_subgroup in result["main_groups"][group_name]["sub_groups"]:
                        result["main_groups"][group_name]["sub_groups"][best_subgroup]["items"].append(item)
                        assigned_items.add(item["id"])
        
        # Add unassigned items to ungrouped
        for item in items:
            if item["id"] not in assigned_items:
                result["ungrouped_items"].append(item)
        
        # Update group statistics
        for group_name, group_data in result["main_groups"].items():
            total_items = sum(len(sg["items"]) for sg in group_data["sub_groups"].values())
            group_data["total_items"] = total_items
            
            # Calculate estimated savings
            all_items = []
            for sg in group_data["sub_groups"].values():
                all_items.extend(sg["items"])
            group_data["estimated_savings"] = self.calculate_estimated_savings(all_items)
        
        return result

    def validate_structured_plan(self, plan: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate a structured plan for completeness and correctness"""
        errors = []
        
        # Check required fields
        required_fields = ["id", "name", "created_at", "grouping_rules", "main_groups"]
        for field in required_fields:
            if field not in plan:
                errors.append(f"Missing required field: {field}")
        
        # Validate grouping rules
        if "grouping_rules" in plan:
            for i, rule in enumerate(plan["grouping_rules"]):
                if "group_name" not in rule:
                    errors.append(f"Grouping rule {i}: missing group_name")
                if "core_keywords" not in rule:
                    errors.append(f"Grouping rule {i}: missing core_keywords")
        
        # Validate main groups structure
        if "main_groups" in plan:
            for group_name, group_data in plan["main_groups"].items():
                if "name" not in group_data:
                    errors.append(f"Main group '{group_name}': missing name")
                if "sub_groups" not in group_data:
                    errors.append(f"Main group '{group_name}': missing sub_groups")
        
        return len(errors) == 0, errors

    def generate_groups_with_config(self, df: pd.DataFrame, use_main_groups=True, main_group_column=None, sub_group_column=None):
        """Generate groups using user-specified column configuration - ALWAYS process ALL records"""
        try:
            print(f"\n=== Starting User-Configured Group Generation ===")
            print(f"Dataset size: {len(df)} rows")
            print(f"Configuration: use_main_groups={use_main_groups}, main_column={main_group_column}, sub_column={sub_group_column}")
            print(f"PROCESSING ALL RECORDS (no chunking or sampling)")
            
            # Always process directly - NO chunked processing for user-configured groups
            # This ensures every unique value in the selected column becomes a group
            if use_main_groups and main_group_column:
                groups = self.create_groups_from_columns(df, main_group_column, sub_group_column)
            else:
                groups = self.create_groups_from_single_column(df, sub_group_column)
            
            # Calculate statistics from actual data
            grouped_count = 0
            for group in groups:
                grouped_count += group.get('count', 0)
            
            ungrouped_count = len(df) - grouped_count
            
            # Validate and add counts to all groups
            validation_results = self.validate_and_count_groups(groups, len(df))
            
            # Create list of ungrouped items (should be empty since we process all records)
            ungrouped_items = []
            
            # If there are ungrouped records according to validation, find them
            if validation_results['counts']['ungrouped_records'] > 0:
                print(f"Warning: {validation_results['counts']['ungrouped_records']} records appear to be ungrouped")
                # This should rarely happen with the new logic, but we handle it
                grouped_indices = set()
                for group in groups:
                    for sub_group in group.get('sub_groups', []):
                        for item in sub_group.get('items', []):
                            if isinstance(item, dict) and 'original_index' in item:
                                grouped_indices.add(item['original_index'])
                
                # Add any missed rows to ungrouped
                for index, row in df.iterrows():
                    if index not in grouped_indices:
                        ungrouped_item = row.to_dict()
                        ungrouped_item['count'] = ungrouped_item.get('quantity', 1)
                        ungrouped_item['id'] = str(index)
                        ungrouped_item['original_index'] = index
                        ungrouped_items.append(ungrouped_item)
            
            # Add counts to ungrouped items
            ungrouped_items = self.add_counts_to_ungrouped_items(ungrouped_items)
            
            result = {
                'groups': groups,
                'ungrouped_items': ungrouped_items,
                'validation': validation_results,
                'total_items': validation_results['counts']['total_rows'],
                'grouped_items': validation_results['counts']['grouped_records'],
                'ungrouped_count': validation_results['counts']['ungrouped_records'],
                'total_groups': validation_results['counts']['main_groups'],
                'total_sub_groups': validation_results['counts']['total_sub_groups'],
                'estimated_time_saved': self.calculate_estimated_savings(df.to_dict('records')),
                'is_valid': validation_results['is_valid'],
                'processing_method': 'all_records_processed'
            }
            
            print(f"\n=== Group Generation Complete ===")
            print(f"Total groups: {len(groups)}")
            print(f"Items grouped: {validation_results['counts']['grouped_records']}/{len(df)}")
            print(f"Validation: {validation_results['is_valid']}")
            
            return result
            
        except Exception as e:
            print(f"Error in user-configured group generation: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def generate_groups_chunked_with_config(self, df: pd.DataFrame, use_main_groups=True, main_group_column=None, sub_group_column=None):
        """Process large datasets in chunks using user configuration"""
        try:
            print(f"\n=== Starting Chunked User-Configured Processing ===")
            total_rows = len(df)
            
            print(f"Total rows: {total_rows}")
            print(f"Chunk size: {self.chunk_size}")
            print(f"Sample size per chunk: {self.sample_size_per_chunk}")
            
            # Collect samples from each chunk for analysis
            all_samples = []
            for i in range(0, total_rows, self.chunk_size):
                chunk = df.iloc[i:i+self.chunk_size]
                sample = chunk.sample(n=min(self.sample_size_per_chunk, len(chunk)), random_state=42)
                all_samples.append(sample)
                print(f"Processed chunk {i//self.chunk_size + 1}/{(total_rows-1)//self.chunk_size + 1}")
            
            # Combine all samples
            combined_samples = pd.concat(all_samples, ignore_index=True)
            print(f"Combined {len(combined_samples)} samples for analysis")
            
            # Analyze samples to create intelligent group patterns
            if use_main_groups and main_group_column:
                sample_groups = self.create_groups_from_columns(combined_samples, main_group_column, sub_group_column)
            else:
                sample_groups = self.create_groups_from_single_column(combined_samples, sub_group_column)
            
            print(f"Created {len(sample_groups)} intelligent group patterns from samples")
            
            # Assign remaining items to groups based on intelligent patterns
            remaining_items = df[~df.index.isin(combined_samples.index)]
            
            print(f"Assigning {len(remaining_items)} remaining items to groups using intelligent matching")
            for _, item in remaining_items.iterrows():
                item_dict = item.to_dict()
                self.assign_item_to_intelligent_group(item_dict, sample_groups, main_group_column, sub_group_column)
            
            # Calculate final statistics
            grouped_count = 0
            for group in sample_groups:
                grouped_count += len(group.get('items', []))
                for sub_group in group.get('sub_groups', []):
                    grouped_count += len(sub_group.get('items', []))
            
            ungrouped_count = total_rows - grouped_count
            
            # Validate and add counts to all groups
            validation_results = self.validate_and_count_groups(sample_groups, total_rows)
            
            # Get proper ungrouped items
            ungrouped_items = []
            if validation_results['counts']['ungrouped_records'] > 0:
                # Find rows that weren't grouped
                grouped_indices = set()
                for group in sample_groups:
                    for item in group.get('items', []):
                        if isinstance(item, dict) and 'row_data' in item:
                            original_index = item['row_data'].get('index', item.get('id'))
                            if original_index is not None:
                                grouped_indices.add(str(original_index))
                    for sub_group in group.get('sub_groups', []):
                        for item in sub_group.get('items', []):
                            if isinstance(item, dict) and 'row_data' in item:
                                original_index = item['row_data'].get('index', item.get('id'))
                                if original_index is not None:
                                    grouped_indices.add(str(original_index))
                
                # Add ungrouped rows
                for index, row in df.iterrows():
                    if str(index) not in grouped_indices:
                        ungrouped_item = row.to_dict()
                        ungrouped_item['count'] = ungrouped_item.get('quantity', 1)
                        ungrouped_item['index'] = index
                        ungrouped_items.append(ungrouped_item)
            
            # Add counts to ungrouped items
            ungrouped_items = self.add_counts_to_ungrouped_items(ungrouped_items)
            
            result = {
                'groups': sample_groups,
                'ungrouped_items': ungrouped_items[:100],  # Limit for performance
                'validation': validation_results,
                'total_items': validation_results['counts']['total_rows'],
                'grouped_items': validation_results['counts']['grouped_records'],
                'ungrouped_count': validation_results['counts']['ungrouped_records'],
                'total_groups': validation_results['counts']['main_groups'],
                'total_sub_groups': validation_results['counts']['total_sub_groups'],
                'estimated_time_saved': self.calculate_estimated_savings(df.to_dict('records')),
                'is_valid': validation_results['is_valid']
            }
            
            print(f"=== Chunked Processing Complete ===")
            print(f"Total groups: {len(sample_groups)}")
            print(f"Items grouped: {validation_results['counts']['grouped_records']}/{total_rows}")
            print(f"Validation: {validation_results['is_valid']}")
            
            return result
            
        except Exception as e:
            print(f"Error in chunked user-configured processing: {str(e)}")
            return None

    def create_groups_from_columns(self, df: pd.DataFrame, main_column: str, sub_column: str = None):
        """Create groups based on user-specified columns - process ALL records"""
        groups = []
        
        print(f"Creating groups from columns: main='{main_column}', sub='{sub_column}'")
        print(f"Processing ALL {len(df)} records (no sampling)")
        
        # Group by main column - EVERY unique value becomes a main group
        if main_column and main_column in df.columns:
            main_groups = df.groupby(main_column)
            
            print(f"Found {len(main_groups)} unique values in column '{main_column}'")
            
            for main_value, main_group_df in main_groups:
                # Skip null/empty values
                if pd.isna(main_value) or str(main_value).strip() == '':
                    print(f"Skipping empty/null main group value")
                    continue
                
                main_group_name = self.clean_group_name(str(main_value))
                print(f"Creating main group: '{main_group_name}' with {len(main_group_df)} records")
                
                group = {
                    'id': self.generate_group_id(),
                    'name': main_group_name,
                    'type': 'main',
                    'enabled': True,
                    'sub_groups': [],
                    'items': [],  # Direct items in main group
                    'count': len(main_group_df),
                    'item_count': len(main_group_df)
                }
                
                # Create sub-groups within this main group
                if sub_column and sub_column in df.columns:
                    # Group by sub-column within this main group
                    sub_groups = main_group_df.groupby(sub_column)
                    
                    print(f"  Creating sub-groups by column '{sub_column}': {len(sub_groups)} unique values")
                    
                    # Track items that don't fit into named sub-groups
                    ungrouped_items = []
                    
                    for sub_value, sub_group_df in sub_groups:
                        # Skip null/empty sub-group values - they go to ungrouped
                        if pd.isna(sub_value) or str(sub_value).strip() == '':
                            ungrouped_items.extend(sub_group_df.to_dict('records'))
                            continue
                        
                        sub_group_name = self.clean_group_name(str(sub_value))
                        sub_group_items = []
                        
                        # Convert each row to an item
                        for index, row in sub_group_df.iterrows():
                            item = {
                                'id': str(index),
                                'name': str(row.get(sub_column, f'Item_{index}')),
                                'price': self.safe_float(row.get('price', row.get('Price', 0))),
                                'category': str(main_value),  # Main group becomes category
                                'quantity': self.safe_int(row.get('quantity', row.get('Quantity', 1))),
                                'count': 1,
                                'row_data': {str(k): str(v) for k, v in row.to_dict().items()},
                                'original_index': index
                            }
                            sub_group_items.append(item)
                        
                        # Create sub-group
                        sub_group = {
                            'id': self.generate_group_id(),
                            'name': sub_group_name,
                            'items': sub_group_items,
                            'count': len(sub_group_items),
                            'is_ungrouped_subgroup': False
                        }
                        
                        group['sub_groups'].append(sub_group)
                        print(f"    Sub-group '{sub_group_name}': {len(sub_group_items)} records")
                    
                    # Create "Ungrouped Items" sub-group for items without valid sub-group values
                    if ungrouped_items:
                        ungrouped_sub_group_items = []
                        for row_dict in ungrouped_items:
                            item = {
                                'id': str(row_dict.get('index', f"ungrouped_{len(ungrouped_sub_group_items)}")),
                                'name': str(row_dict.get(sub_column, f'Ungrouped_Item_{len(ungrouped_sub_group_items)}')),
                                'price': self.safe_float(row_dict.get('price', row_dict.get('Price', 0))),
                                'category': str(main_value),
                                'quantity': self.safe_int(row_dict.get('quantity', row_dict.get('Quantity', 1))),
                                'count': 1,
                                'row_data': {str(k): str(v) for k, v in row_dict.items()},
                                'original_index': row_dict.get('index', f"ungrouped_{len(ungrouped_sub_group_items)}")
                            }
                            ungrouped_sub_group_items.append(item)
                        
                        ungrouped_sub_group = {
                            'id': self.generate_group_id(),
                            'name': 'Ungrouped Items',
                            'items': ungrouped_sub_group_items,
                            'count': len(ungrouped_sub_group_items),
                            'is_ungrouped_subgroup': True
                        }
                        group['sub_groups'].append(ungrouped_sub_group)
                        print(f"    Ungrouped Items sub-group: {len(ungrouped_sub_group_items)} records")
                
                else:
                    # No sub-column specified, put all items directly in main group
                    main_group_items = []
                    for index, row in main_group_df.iterrows():
                        item = {
                            'id': str(index),
                            'name': str(row.iloc[0] if len(row) > 0 else f'Item_{index}'),  # First column as name
                            'price': self.safe_float(row.get('price', row.get('Price', 0))),
                            'category': str(main_value),
                            'quantity': self.safe_int(row.get('quantity', row.get('Quantity', 1))),
                            'count': 1,
                            'row_data': {str(k): str(v) for k, v in row.to_dict().items()},
                            'original_index': index
                        }
                        main_group_items.append(item)
                    
                    # Create a default sub-group to maintain structure
                    default_sub_group = {
                        'id': self.generate_group_id(),
                        'name': 'All Items',
                        'items': main_group_items,
                        'count': len(main_group_items),
                        'is_ungrouped_subgroup': False
                    }
                    group['sub_groups'].append(default_sub_group)
                    print(f"    Default sub-group 'All Items': {len(main_group_items)} records")
                
                # Update group total count
                total_items_in_group = sum(sg['count'] for sg in group['sub_groups'])
                group['count'] = total_items_in_group
                group['item_count'] = total_items_in_group
                group['estimated_savings'] = self.calculate_estimated_savings(
                    [item for sg in group['sub_groups'] for item in sg['items']]
                )
                
                groups.append(group)
                print(f"Main group '{main_group_name}' completed: {total_items_in_group} total records in {len(group['sub_groups'])} sub-groups")
        
        print(f"Created {len(groups)} main groups from ALL {len(df)} records")
        return groups

    def create_groups_from_single_column(self, df: pd.DataFrame, column: str):
        """Create groups from a single column - process ALL records"""
        print(f"\nCreating groups from single column: '{column}'")
        print(f"Processing ALL {len(df)} records (no sampling)")
        
        if column not in df.columns:
            print(f"Column '{column}' not found in dataset")
            return []
        
        # Group by the specified column - EVERY unique value becomes a group
        column_groups = df.groupby(column)
        groups = []
        
        print(f"Found {len(column_groups)} unique values in column '{column}'")
        
        for value, group_df in column_groups:
            # Skip null/empty values
            if pd.isna(value) or str(value).strip() == '':
                print(f"Skipping empty/null group value")
                continue
            
            group_name = self.clean_group_name(str(value))
            print(f"Creating group: '{group_name}' with {len(group_df)} records")
            
            # Convert all rows in this group to items
            group_items = []
            for index, row in group_df.iterrows():
                item = {
                    'id': str(index),
                    'name': str(row.get(column, f'Item_{index}')),  # Use the column value as item name
                    'price': self.safe_float(row.get('price', row.get('Price', 0))),
                    'category': str(value),  # Group value becomes category
                    'quantity': self.safe_int(row.get('quantity', row.get('Quantity', 1))),
                    'count': 1,
                    'row_data': {str(k): str(v) for k, v in row.to_dict().items()},
                    'original_index': index
                }
                group_items.append(item)
            
            # Create a single sub-group containing all items
            sub_group = {
                'id': self.generate_group_id(),
                'name': 'All Items',
                'items': group_items,
                'count': len(group_items),
                'is_ungrouped_subgroup': False
            }
            
            group = {
                'id': self.generate_group_id(),
                'name': group_name,
                'type': 'main',
                'enabled': True,
                'sub_groups': [sub_group],
                'items': [],  # All items are in sub-groups
                'count': len(group_items),
                'item_count': len(group_items),
                'estimated_savings': self.calculate_estimated_savings(group_items)
            }
            
            groups.append(group)
            print(f"Group '{group_name}' created: {len(group_items)} records")
        
        print(f"Created {len(groups)} groups from ALL {len(df)} records in column '{column}'")
        return groups

    def assign_item_to_intelligent_group(self, item: Dict, groups: List[Dict], main_column: str, sub_column: str):
        """Assign an item to a group using intelligent product matching"""
        try:
            # Create a product item for analysis
            product_name = str(item.get(sub_column, '')) if sub_column and sub_column in item else str(item.get(main_column, ''))
            
            if not product_name.strip():
                return False
            
            product_item = {
                "id": str(item.get('id', len(item))),
                "name": product_name,
                "original_name": product_name,
                "price": self.safe_float(item.get('price', 0)),
                "category": str(item.get('category', 'Unknown')),
                "quantity": self.safe_int(item.get('quantity', 1)),
                "row_data": item
            }
            
            # Analyze the item
            normalized_name = self.normalize_product_name(product_item['name'])
            core_type, sub_type, confidence = self.extract_core_product_type(product_item['name'])
            
            product_item.update({
                'normalized_name': normalized_name,
                'core_type': core_type,
                'sub_type': sub_type,
                'confidence': confidence,
                'key_words': normalized_name.split()
            })
            
            best_match = None
            best_similarity = 0.0
            
            for group in groups:
                # For main groups mode
                if main_column and main_column in item:
                    main_value = self.clean_group_name(str(item.get(main_column, '')))
                    if main_value == group['name']:
                        # Found the right main group, now find best sub-group
                        if group.get('sub_groups'):
                            for sub_group in group['sub_groups']:
                                if sub_group['items']:
                                    # Calculate similarity with items in this sub-group
                                    avg_similarity = self.calculate_average_similarity_to_group(product_item, sub_group['items'])
                                    if avg_similarity > best_similarity and avg_similarity > 0.5:
                                        best_similarity = avg_similarity
                                        best_match = ('sub_group', group, sub_group)
                            
                            # If no good sub-group match, add to main group
                            if not best_match:
                                best_match = ('main_group', group, None)
                        else:
                            # No sub-groups, add to main group
                            best_match = ('main_group', group, None)
                        break
                
                # For single-column mode or if no main group match
                else:
                    if group['items']:
                        avg_similarity = self.calculate_average_similarity_to_group(product_item, group['items'])
                        if avg_similarity > best_similarity and avg_similarity > 0.4:
                            best_similarity = avg_similarity
                            best_match = ('main_group', group, None)
            
            # Assign to best match
            if best_match:
                match_type, group, sub_group = best_match
                if match_type == 'sub_group' and sub_group:
                    sub_group['items'].append(item)
                else:
                    group['items'].append(item)
                return True
                        
        except Exception as e:
            print(f"Error assigning item to intelligent group: {str(e)}")
        
        return False

    def calculate_average_similarity_to_group(self, item: Dict, group_items: List[Dict]) -> float:
        """Calculate average similarity of an item to items in a group"""
        if not group_items:
            return 0.0
        
        similarities = []
        for group_item in group_items[:5]:  # Check against max 5 items for performance
            similarity = self.calculate_product_similarity(item, group_item)
            similarities.append(similarity)
        
        return sum(similarities) / len(similarities) if similarities else 0.0

    def assign_item_to_group_by_pattern(self, item: Dict, groups: List[Dict], main_column: str, sub_column: str):
        """Legacy function - kept for compatibility. Use assign_item_to_intelligent_group instead."""
        return self.assign_item_to_intelligent_group(item, groups, main_column, sub_column)

    def clean_group_name(self, name: str) -> str:
        """Clean and normalize group names"""
        if not name or pd.isna(name):
            return "Ungrouped"
        
        # Convert to string and clean
        clean_name = str(name).strip()
        
        # Remove extra whitespace
        clean_name = ' '.join(clean_name.split())
        
        # Capitalize first letter of each word
        clean_name = clean_name.title()
        
        return clean_name if clean_name else "Ungrouped"

    def generate_group_id(self) -> str:
        """Generate a unique group ID"""
        return str(uuid.uuid4())[:8]

    def create_intelligent_sub_groups_from_column(self, df: pd.DataFrame, column: str):
        """
        Create intelligent sub-groups from a column using advanced product matching logic.
        
        Groups by Core Product Type: Focus on what the product fundamentally is
        Ignores Superficial Differences: Brands, colors, sizes, packaging variations
        Handles Size/Weight Variations: Groups different sizes of same product
        Recognizes Synonyms: Groups similar product names
        """
        print(f"Starting intelligent sub-group creation from column: {column}")
        
        # Convert DataFrame to items for processing
        items = []
        for index, row in df.iterrows():
            # Use the specified column as the product name for analysis
            product_name = str(row.get(column, '')) if pd.notna(row.get(column)) else ''
            
            if not product_name.strip():
                continue
                
            row_dict = row.to_dict()
            row_dict['index'] = index  # Store original index for tracking
            
            item = {
                "id": str(index),
                "name": product_name,
                "original_name": product_name,
                "price": self.safe_float(row.iloc[1] if len(row) > 1 else 0),
                "category": str(row.iloc[2] if len(row) > 2 else "Unknown"),
                "quantity": self.safe_int(row.iloc[3] if len(row) > 3 else 1),
                "count": self.safe_int(row.iloc[3] if len(row) > 3 else 1),  # Initialize count
                "row_data": row_dict,
                "column_value": product_name,  # Store the original column value
                "original_index": index  # Direct index reference
            }
            items.append(item)
        
        print(f"Processing {len(items)} items for intelligent grouping")
        
        # Apply intelligent grouping using core product type analysis
        grouped_items = self.group_items_by_core_product_type(items)
        
        # Convert to sub-groups format
        sub_groups = []
        ungrouped_items = []
        
        for group_info in grouped_items:
            if len(group_info['items']) >= 2:  # Only create groups with 2+ items
                sub_group = {
                    'id': self.generate_group_id(),
                    'name': group_info['name'],
                    'items': group_info['items'],
                    'enabled': True,
                    'core_type': group_info.get('core_type', 'unknown'),
                    'keywords': group_info.get('keywords', [])
                }
                sub_groups.append(sub_group)
            else:
                # Single items go to ungrouped
                ungrouped_items.extend(group_info['items'])
        
        print(f"Created {len(sub_groups)} intelligent sub-groups with {len(ungrouped_items)} ungrouped items")
        
        return {
            'sub_groups': sub_groups,
            'ungrouped_items': ungrouped_items
        }

    def group_items_by_core_product_type(self, items: List[Dict]) -> List[Dict]:
        """
        Group items by their core product type using advanced analysis.
        
        This implements the logic:
        - Group by Core Product Type: Focus on what the product fundamentally is
        - Ignore Superficial Differences: Brands, colors, sizes, packaging
        - Handle Size/Weight Variations: Different sizes of same product
        - Recognize Synonyms: Similar product names
        - Process Complex Categories: Look beyond misleading names
        """
        print(f"Analyzing {len(items)} items for core product types")
        
        # Step 1: Normalize and extract core product types
        analyzed_items = []
        for item in items:
            normalized_name = self.normalize_product_name(item['name'])
            core_type, sub_type, confidence = self.extract_core_product_type(item['name'])
            
            analyzed_item = {
                **item,
                'normalized_name': normalized_name,
                'core_type': core_type,
                'sub_type': sub_type,
                'confidence': confidence,
                'key_words': normalized_name.split()
            }
            analyzed_items.append(analyzed_item)
        
        # Step 2: Group by core type first, then by similarity within each type
        type_groups = defaultdict(list)
        for item in analyzed_items:
            type_groups[item['core_type']].append(item)
        
        # Step 3: Create intelligent groups
        final_groups = []
        
        for core_type, type_items in type_groups.items():
            print(f"Processing {len(type_items)} items of type: {core_type}")
            
            if core_type == 'other':
                # For 'other' category, use more sophisticated similarity analysis
                similarity_groups = self.create_similarity_groups(type_items)
                final_groups.extend(similarity_groups)
            else:
                # For known types, group by sub-type and similarity
                subtype_groups = defaultdict(list)
                for item in type_items:
                    subtype_groups[item['sub_type']].append(item)
                
                for sub_type, sub_items in subtype_groups.items():
                    if len(sub_items) >= 2:
                        # Further group by similarity within subtype
                        similarity_groups = self.create_similarity_groups(sub_items)
                        final_groups.extend(similarity_groups)
                    else:
                        # Single item - create individual group
                        group_name = self.generate_intelligent_group_name(sub_items, core_type, sub_type)
                        final_groups.append({
                            'name': group_name,
                            'items': sub_items,
                            'core_type': core_type,
                            'sub_type': sub_type,
                            'keywords': list(set([word for item in sub_items for word in item['key_words']]))
                        })
        
        print(f"Created {len(final_groups)} core product type groups")
        return final_groups

    def create_similarity_groups(self, items: List[Dict], similarity_threshold: float = 0.6) -> List[Dict]:
        """Create groups based on product similarity within items of same type"""
        if len(items) <= 1:
            return [{'name': items[0]['name'] if items else 'Empty', 'items': items, 'core_type': 'unknown', 'keywords': []}]
        
        groups = []
        processed_items = set()
        
        for i, item1 in enumerate(items):
            if item1['id'] in processed_items:
                continue
                
            # Start a new group with this item
            current_group = [item1]
            processed_items.add(item1['id'])
            
            # Find similar items
            for j, item2 in enumerate(items[i+1:], i+1):
                if item2['id'] in processed_items:
                    continue
                    
                # Calculate similarity
                similarity = self.calculate_product_similarity(item1, item2)
                
                if similarity >= similarity_threshold:
                    current_group.append(item2)
                    processed_items.add(item2['id'])
            
            # Generate group name based on common patterns
            if len(current_group) >= 2:
                group_name = self.generate_intelligent_group_name(
                    current_group, 
                    current_group[0].get('core_type', 'unknown'),
                    current_group[0].get('sub_type', 'general')
                )
                
                groups.append({
                    'name': group_name,
                    'items': current_group,
                    'core_type': current_group[0].get('core_type', 'unknown'),
                    'sub_type': current_group[0].get('sub_type', 'general'),
                    'keywords': list(set([word for item in current_group for word in item['key_words']]))
                })
            else:
                # Single item group
                groups.append({
                    'name': self.clean_group_name(current_group[0]['name']),
                    'items': current_group,
                    'core_type': current_group[0].get('core_type', 'unknown'),
                    'keywords': current_group[0]['key_words']
                })
        
        return groups

    def generate_intelligent_group_name(self, items: List[Dict], core_type: str, sub_type: str) -> str:
        """Generate an intelligent group name based on the items' common characteristics"""
        if not items:
            return "Empty Group"
        
        if len(items) == 1:
            return self.clean_group_name(items[0]['name'])
        
        # Find common words among all items (excluding noise words)
        noise_words = {'the', 'and', 'or', 'with', 'for', 'in', 'on', 'at', 'by', 'from', 'to', 'of', 'a', 'an'}
        
        all_words = []
        for item in items:
            words = [w.lower() for w in item['key_words'] if len(w) > 2 and w.lower() not in noise_words]
            all_words.extend(words)
        
        # Count word frequency
        word_counts = Counter(all_words)
        common_words = [word for word, count in word_counts.most_common(3) if count >= len(items) * 0.5]
        
        if common_words:
            group_name = ' '.join(common_words).title()
        elif core_type != 'other':
            group_name = core_type.replace('_', ' ').title()
            if sub_type != 'general' and sub_type != core_type:
                group_name = f"{sub_type.title()} {group_name}"
        else:
            # Fallback: use the most common first word
            first_words = [item['name'].split()[0] for item in items if item['name'].split()]
            if first_words:
                most_common_first = Counter(first_words).most_common(1)[0][0]
                group_name = f"{most_common_first} Products"
            else:
                group_name = "Similar Products"
        
        # Clean and limit length
        group_name = self.clean_group_name(group_name)
        if len(group_name) > 50:
            group_name = group_name[:47] + "..."
        
        return group_name

    def validate_and_count_groups(self, groups: List[Dict], total_rows: int) -> Dict:
        """
        Validate group data integrity and add counts to all levels.
        
        Validation Requirements:
        - Confirm: Sum(Grouped Records) + Ungrouped Records = Total Rows
        - Ensure no duplicate subgroup names inside same main group
        - Each product item should have count value
        - Each main group should have count of records
        - Each sub group should have count of records
        """
        print("Starting group validation and counting...")
        
        validation_results = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'counts': {
                'total_rows': total_rows,
                'grouped_records': 0,
                'ungrouped_records': 0,
                'main_groups': len(groups),
                'total_sub_groups': 0
            }
        }
        
        total_grouped_items = 0
        
        for group_idx, group in enumerate(groups):
            # Validate and count main group
            main_group_count = 0
            sub_group_names = set()
            
            # Count items directly in main group
            if 'items' in group and group['items']:
                main_group_items = len(group['items'])
                main_group_count += main_group_items
                
                # Add count to each item in main group
                for item in group['items']:
                    if isinstance(item, dict):
                        item['count'] = item.get('quantity', 1)
                        if 'quantity' not in item:
                            item['quantity'] = 1
            
            # Process sub-groups
            if 'sub_groups' in group and group['sub_groups']:
                validation_results['counts']['total_sub_groups'] += len(group['sub_groups'])
                
                for sub_group_idx, sub_group in enumerate(group['sub_groups']):
                    sub_group_name = sub_group.get('name', f'SubGroup_{sub_group_idx}')
                    
                    # Check for duplicate sub-group names within main group
                    if sub_group_name in sub_group_names:
                        validation_results['errors'].append(
                            f"Duplicate sub-group name '{sub_group_name}' in main group '{group.get('name', f'Group_{group_idx}')}'"
                        )
                        validation_results['is_valid'] = False
                        # Make name unique
                        counter = 1
                        original_name = sub_group_name
                        while sub_group_name in sub_group_names:
                            sub_group_name = f"{original_name} ({counter})"
                            counter += 1
                        sub_group['name'] = sub_group_name
                    
                    sub_group_names.add(sub_group_name)
                    
                    # Count items in sub-group
                    sub_group_count = 0
                    if 'items' in sub_group and sub_group['items']:
                        sub_group_count = len(sub_group['items'])
                        main_group_count += sub_group_count
                        
                        # Add count to each item in sub-group
                        for item in sub_group['items']:
                            if isinstance(item, dict):
                                item['count'] = item.get('quantity', 1)
                                if 'quantity' not in item:
                                    item['quantity'] = 1
                    
                    # Add count to sub-group
                    sub_group['count'] = sub_group_count
                    sub_group['item_count'] = sub_group_count
                    
                    # Note if this is an ungrouped sub-group for logging
                    if sub_group.get('is_ungrouped_subgroup', False):
                        print(f"   Found ungrouped sub-group '{sub_group_name}' with {sub_group_count} items")
            
            # Add count to main group
            group['count'] = main_group_count
            group['item_count'] = main_group_count
            total_grouped_items += main_group_count
        
        # Update validation counts
        validation_results['counts']['grouped_records'] = total_grouped_items
        validation_results['counts']['ungrouped_records'] = total_rows - total_grouped_items
        
        # Validate total count
        calculated_total = validation_results['counts']['grouped_records'] + validation_results['counts']['ungrouped_records']
        if calculated_total != total_rows:
            validation_results['errors'].append(
                f"Count mismatch: Sum(Grouped: {validation_results['counts']['grouped_records']}) + "
                f"Ungrouped: {validation_results['counts']['ungrouped_records']}) = {calculated_total} "
                f"≠ Total Rows: {total_rows}"
            )
            validation_results['is_valid'] = False
        
        # Count ungrouped sub-groups
        ungrouped_subgroups_count = 0
        for group in groups:
            for sub_group in group.get('sub_groups', []):
                if sub_group.get('is_ungrouped_subgroup', False):
                    ungrouped_subgroups_count += 1
        
        validation_results['counts']['ungrouped_subgroups'] = ungrouped_subgroups_count
        
        # Log validation results
        if validation_results['is_valid']:
            print("✅ Group validation passed:")
            print(f"   - Total rows: {validation_results['counts']['total_rows']}")
            print(f"   - Grouped records: {validation_results['counts']['grouped_records']}")
            print(f"   - Ungrouped records: {validation_results['counts']['ungrouped_records']}")
            print(f"   - Main groups: {validation_results['counts']['main_groups']}")
            print(f"   - Total sub-groups: {validation_results['counts']['total_sub_groups']}")
            print(f"   - Ungrouped sub-groups: {validation_results['counts']['ungrouped_subgroups']}")
        else:
            print("❌ Group validation failed:")
            for error in validation_results['errors']:
                print(f"   - ERROR: {error}")
        
        if validation_results['warnings']:
            print("⚠️ Warnings:")
            for warning in validation_results['warnings']:
                print(f"   - WARNING: {warning}")
        
        return validation_results

    def add_counts_to_ungrouped_items(self, ungrouped_items: List[Dict]) -> List[Dict]:
        """Add count information to ungrouped items"""
        for item in ungrouped_items:
            if isinstance(item, dict):
                item['count'] = item.get('quantity', 1)
                if 'quantity' not in item:
                    item['quantity'] = 1
        return ungrouped_items

    def generate_ai_powered_groups_from_columns(self, df: pd.DataFrame, main_group_column: str = None, sub_group_column: str = None):
        """
        AI-powered grouping using unique values and counts analysis.
        Uses machine learning approach to group products by core type, ignoring superficial differences.
        """
        try:
            print(f"\n=== Starting AI-Powered Column-Based Grouping ===")
            print(f"Dataset size: {len(df)} rows")
            print(f"Main group column: {main_group_column}")
            print(f"Sub group column: {sub_group_column}")
            
            # Step 1: Get unique values and counts for main group column
            main_unique_values = []
            main_value_counts = []
            if main_group_column and main_group_column in df.columns:
                main_unique = df[main_group_column].unique()
                main_counts = df[main_group_column].value_counts()
                
                # Filter out null/empty values and convert to lists
                for value in main_unique:
                    if pd.notna(value) and str(value).strip():
                        clean_value = str(value).strip()
                        count = main_counts.get(value, 0)
                        # Convert numpy types to native Python types
                        if hasattr(count, 'item'):
                            count = count.item()
                        main_unique_values.append(clean_value)
                        main_value_counts.append(int(count))
                
                print(f"Main group analysis: {len(main_unique_values)} unique values")
                print(f"Sample main values: {main_unique_values[:5]}...")
            
            # Step 2: Get unique values and counts for sub group column
            sub_unique_values = []
            sub_value_counts = []
            if sub_group_column and sub_group_column in df.columns:
                sub_unique = df[sub_group_column].unique()
                sub_counts = df[sub_group_column].value_counts()
                
                # Filter out null/empty values and convert to lists
                for value in sub_unique:
                    if pd.notna(value) and str(value).strip():
                        clean_value = str(value).strip()
                        count = sub_counts.get(value, 0)
                        # Convert numpy types to native Python types
                        if hasattr(count, 'item'):
                            count = count.item()
                        sub_unique_values.append(clean_value)
                        sub_value_counts.append(int(count))
                
                print(f"Sub group analysis: {len(sub_unique_values)} unique values")
                print(f"Sample sub values: {sub_unique_values[:5]}...")
            
            # Step 3: Use AI to plan intelligent grouping
            grouping_plan = self.create_ai_grouping_plan(
                main_unique_values, main_value_counts,
                sub_unique_values, sub_value_counts,
                main_group_column, sub_group_column
            )
            
            if not grouping_plan:
                raise Exception("Failed to create AI grouping plan")
            
            # Step 4: Apply the grouping plan to the actual data
            groups = self.apply_ai_grouping_plan(df, grouping_plan, main_group_column, sub_group_column)
            
            # Step 5: Validate and add counts - CRITICAL for validation data
            print(f"Validating {len(groups)} groups against {len(df)} total rows...")
            validation_results = self.validate_and_count_groups(groups, len(df))
            
            print(f"Validation results: {validation_results}")
            
            # Step 6: Create ungrouped items list if there are any
            ungrouped_items = []
            ungrouped_count = validation_results['counts']['ungrouped_records']
            if ungrouped_count > 0:
                print(f"Creating {ungrouped_count} ungrouped items...")
                # Find rows that weren't grouped
                grouped_indices = set()
                for group in groups:
                    for sub_group in group.get('sub_groups', []):
                        for item in sub_group.get('items', []):
                            if 'original_index' in item:
                                grouped_indices.add(item['original_index'])
                
                # Add ungrouped rows
                for index, row in df.iterrows():
                    if index not in grouped_indices:
                        ungrouped_item = self.create_item_from_row(row, index, 'Ungrouped', 'Ungrouped Item')
                        ungrouped_items.append(ungrouped_item)
                        if len(ungrouped_items) >= 100:  # Limit for performance
                            break
            
            # Step 7: Create final result structure with proper validation
            result = {
                'groups': groups,
                'ungrouped_items': ungrouped_items,
                'validation': validation_results,
                'total_items': validation_results['counts']['total_rows'],
                'grouped_items': validation_results['counts']['grouped_records'],
                'ungrouped_count': validation_results['counts']['ungrouped_records'],
                'total_groups': validation_results['counts']['main_groups'],
                'total_sub_groups': validation_results['counts']['total_sub_groups'],
                'estimated_time_saved': self.calculate_estimated_savings(df.to_dict('records')),
                'is_valid': validation_results['is_valid'],
                'processing_method': 'ai_powered_column_analysis',
                'ai_grouping_plan': grouping_plan
            }
            
            print(f"\n=== AI-Powered Grouping Complete ===")
            print(f"Groups created: {len(groups)}")
            print(f"Records processed: {len(df)}")
            print(f"Grouped records: {validation_results['counts']['grouped_records']}")
            print(f"Ungrouped records: {validation_results['counts']['ungrouped_records']}")
            print(f"Validation: {validation_results['is_valid']}")
            
            return result
            
        except Exception as e:
            print(f"Error in AI-powered grouping: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def create_ai_grouping_plan(self, main_unique_values, main_value_counts, sub_unique_values, sub_value_counts, main_column, sub_column):
        """
        Use OpenAI to create an intelligent grouping plan based on unique values and counts.
        """
        try:
            print(f"Creating AI grouping plan...")
            
            # Prepare data for AI analysis - ensure all values are native Python types
            main_data = []
            for i, value in enumerate(main_unique_values):
                count = main_value_counts[i] if i < len(main_value_counts) else 0
                # Convert numpy types to native Python types
                if hasattr(count, 'item'):  # numpy types have .item() method
                    count = count.item()
                main_data.append({
                    "value": str(value),  # Ensure string
                    "count": int(count)   # Ensure native int
                })
            
            sub_data = []
            for i, value in enumerate(sub_unique_values):
                count = sub_value_counts[i] if i < len(sub_value_counts) else 0
                # Convert numpy types to native Python types
                if hasattr(count, 'item'):  # numpy types have .item() method
                    count = count.item()
                sub_data.append({
                    "value": str(value),  # Ensure string
                    "count": int(count)   # Ensure native int
                })
            
            # Create AI prompt for grouping analysis
            prompt = f"""
You are an expert in product categorization and procurement optimization. Analyze the following data and create an intelligent grouping plan.

DATASET ANALYSIS:
- Main Group Column: "{main_column}"
- Sub Group Column: "{sub_column}"

MAIN GROUP VALUES (with counts):
{json.dumps(main_data[:50], indent=2)}  # Limit to 50 for API

SUB GROUP VALUES (with counts):
{json.dumps(sub_data[:100], indent=2)}  # Limit to 100 for API

GROUPING INSTRUCTIONS:
1. Group by Core Product Type: Focus on what the product fundamentally is, not brand, model, or variations
2. Ignore Superficial Differences: Brands, colors, sizes, packaging variations should be grouped together
3. Handle Size/Weight Variations: "Flour 1kg" and "Flour 5kg" belong in the same "Flour" group
4. Recognize Synonyms: "Laptop" = "Notebook" = "Portable Computer"
5. Process Complex Categories: Look beyond misleading category names to actual product function

REQUIRED OUTPUT FORMAT (JSON only):
{{
  "main_group_mappings": {{
    "Electronics": {{
      "core_type": "electronics",
      "original_values": ["Laptop", "Phone", "Computer", "Mobile"],
      "total_count": 150,
      "reasoning": "Core electronic devices"
    }},
    "Food Items": {{
      "core_type": "food",
      "original_values": ["Rice", "Flour", "Sugar"],
      "total_count": 200,
      "reasoning": "Basic food commodities"
    }}
  }},
  "sub_group_mappings": {{
    "Computing Devices": {{
      "core_type": "computing",
      "original_values": ["MacBook Pro", "Dell Laptop", "HP Notebook"],
      "total_count": 75,
      "reasoning": "All laptop/notebook variations"
    }},
    "Grains": {{
      "core_type": "grain",
      "original_values": ["Rice 1kg", "Rice 5kg", "Basmati Rice"],
      "total_count": 120,
      "reasoning": "Rice products regardless of size/brand"
    }}
  }},
  "grouping_strategy": {{
    "approach": "core_product_classification",
    "total_main_groups": 5,
    "total_sub_groups": 15,
    "coverage_percentage": 95
  }}
}}

Create logical groups that procurement teams can actually use for bulk purchasing. Focus on practical business value.
"""
            
            # Call OpenAI API
            response = openai.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a procurement and product categorization expert. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=3000,
                temperature=0.3
            )
            
            # Parse response
            response_text = response.choices[0].message.content.strip()
            
            # Clean JSON response
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            
            grouping_plan = json.loads(response_text)
            
            # Validate the plan structure
            required_keys = ["main_group_mappings", "sub_group_mappings", "grouping_strategy"]
            for key in required_keys:
                if key not in grouping_plan:
                    raise ValueError(f"Missing required key: {key}")
            
            print(f"AI grouping plan created successfully")
            print(f"Main groups planned: {len(grouping_plan['main_group_mappings'])}")
            print(f"Sub groups planned: {len(grouping_plan['sub_group_mappings'])}")
            
            return grouping_plan
            
        except Exception as e:
            print(f"Error creating AI grouping plan: {str(e)}")
            # Fallback: create simple plan based on unique values
            return self.create_fallback_grouping_plan(main_unique_values, main_value_counts, sub_unique_values, sub_value_counts)

    def create_fallback_grouping_plan(self, main_unique_values, main_value_counts, sub_unique_values, sub_value_counts):
        """
        Create a fallback grouping plan when AI fails.
        """
        plan = {
            "main_group_mappings": {},
            "sub_group_mappings": {},
            "grouping_strategy": {
                "approach": "fallback_direct_mapping",
                "total_main_groups": len(main_unique_values),
                "total_sub_groups": len(sub_unique_values),
                "coverage_percentage": 100
            }
        }
        
        # Create direct mappings for main groups
        for i, value in enumerate(main_unique_values):
            count = main_value_counts[i] if i < len(main_value_counts) else 0
            # Convert numpy types to native Python types
            if hasattr(count, 'item'):
                count = count.item()
            clean_name = self.clean_group_name(str(value))
            plan["main_group_mappings"][clean_name] = {
                "core_type": clean_name.lower().replace(" ", "_"),
                "original_values": [str(value)],
                "total_count": int(count),
                "reasoning": "Direct mapping (fallback)"
            }
        
        # Create direct mappings for sub groups
        for i, value in enumerate(sub_unique_values):
            count = sub_value_counts[i] if i < len(sub_value_counts) else 0
            # Convert numpy types to native Python types
            if hasattr(count, 'item'):
                count = count.item()
            clean_name = self.clean_group_name(str(value))
            plan["sub_group_mappings"][clean_name] = {
                "core_type": clean_name.lower().replace(" ", "_"),
                "original_values": [str(value)],
                "total_count": int(count),
                "reasoning": "Direct mapping (fallback)"
            }
        
        return plan

    def apply_ai_grouping_plan(self, df: pd.DataFrame, grouping_plan: dict, main_column: str, sub_column: str):
        """
        Apply the AI-generated grouping plan to the actual DataFrame.
        """
        try:
            print(f"Applying AI grouping plan to {len(df)} records...")
            
            groups = []
            
            # Get the mappings from the plan
            main_mappings = grouping_plan.get("main_group_mappings", {})
            sub_mappings = grouping_plan.get("sub_group_mappings", {})
            
            # Create reverse lookup for original values to group names
            main_value_to_group = {}
            for group_name, mapping in main_mappings.items():
                for original_value in mapping.get("original_values", []):
                    main_value_to_group[original_value] = group_name
            
            sub_value_to_group = {}
            for group_name, mapping in sub_mappings.items():
                for original_value in mapping.get("original_values", []):
                    sub_value_to_group[original_value] = group_name
            
            # Group data by main group categories
            if main_column and main_column in df.columns:
                main_groups_data = {}
                
                # Process each row and assign to groups
                for index, row in df.iterrows():
                    main_value = str(row.get(main_column, '')).strip()
                    sub_value = str(row.get(sub_column, '')).strip() if sub_column else ''
                    
                    # Skip empty values
                    if not main_value or pd.isna(row.get(main_column)):
                        continue
                    
                    # Find the group for this main value
                    group_name = main_value_to_group.get(main_value)
                    if not group_name:
                        # Try fuzzy matching for values not in the plan
                        group_name = self.find_best_group_match(main_value, main_mappings)
                        if not group_name:
                            group_name = self.clean_group_name(main_value)  # Create new group
                    
                    # Initialize group if not exists
                    if group_name not in main_groups_data:
                        main_groups_data[group_name] = {
                            'id': self.generate_group_id(),
                            'name': group_name,
                            'type': 'main',
                            'enabled': True,
                            'sub_groups': {},
                            'items': [],
                            'count': 0
                        }
                    
                    # Find sub group for this item
                    if sub_column and sub_value:
                        sub_group_name = sub_value_to_group.get(sub_value)
                        if not sub_group_name:
                            # Try fuzzy matching
                            sub_group_name = self.find_best_group_match(sub_value, sub_mappings)
                            if not sub_group_name:
                                sub_group_name = self.clean_group_name(sub_value)
                        
                        # Initialize sub group if not exists
                        if sub_group_name not in main_groups_data[group_name]['sub_groups']:
                            main_groups_data[group_name]['sub_groups'][sub_group_name] = {
                                'id': self.generate_group_id(),
                                'name': sub_group_name,
                                'items': [],
                                'count': 0
                            }
                        
                        # Create item and add to sub group
                        item = self.create_item_from_row(row, index, main_value, sub_value)
                        main_groups_data[group_name]['sub_groups'][sub_group_name]['items'].append(item)
                        main_groups_data[group_name]['sub_groups'][sub_group_name]['count'] += 1
                    else:
                        # No sub-grouping, add directly to main group
                        item = self.create_item_from_row(row, index, main_value, sub_value)
                        
                        # Create default sub-group
                        if 'All Items' not in main_groups_data[group_name]['sub_groups']:
                            main_groups_data[group_name]['sub_groups']['All Items'] = {
                                'id': self.generate_group_id(),
                                'name': 'All Items',
                                'items': [],
                                'count': 0
                            }
                        
                        main_groups_data[group_name]['sub_groups']['All Items']['items'].append(item)
                        main_groups_data[group_name]['sub_groups']['All Items']['count'] += 1
                    
                    main_groups_data[group_name]['count'] += 1
                
                # Convert to groups array format
                for group_name, group_data in main_groups_data.items():
                    # Convert sub_groups dict to array
                    sub_groups_array = []
                    for sub_name, sub_data in group_data['sub_groups'].items():
                        sub_groups_array.append({
                            'id': sub_data['id'],
                            'name': sub_data['name'],
                            'items': sub_data['items'],
                            'count': len(sub_data['items'])
                        })
                    
                    group = {
                        'id': group_data['id'],
                        'name': group_data['name'],
                        'type': 'main',
                        'enabled': True,
                        'sub_groups': sub_groups_array,
                        'count': group_data['count'],
                        'item_count': group_data['count'],
                        'estimated_savings': self.calculate_estimated_savings(
                            [item for sg in sub_groups_array for item in sg['items']]
                        )
                    }
                    groups.append(group)
            
            print(f"Applied grouping plan: {len(groups)} groups created")
            return groups
            
        except Exception as e:
            print(f"Error applying AI grouping plan: {str(e)}")
            import traceback
            traceback.print_exc()
            return []

    def find_best_group_match(self, value: str, mappings: dict, threshold: float = 0.6):
        """
        Find the best matching group for a value using fuzzy matching.
        """
        try:
            value_lower = value.lower()
            best_match = None
            best_score = 0.0
            
            for group_name, mapping in mappings.items():
                for original_value in mapping.get("original_values", []):
                    # Direct substring match
                    if value_lower in original_value.lower() or original_value.lower() in value_lower:
                        score = 0.8
                    else:
                        # Use sequence matcher for similarity
                        score = SequenceMatcher(None, value_lower, original_value.lower()).ratio()
                    
                    if score > best_score and score >= threshold:
                        best_score = score
                        best_match = group_name
            
            return best_match
            
        except Exception:
            return None

    def create_item_from_row(self, row: pd.Series, index: int, main_value: str, sub_value: str):
        """
        Create a standardized item dictionary from a DataFrame row.
        Ensures all values are native Python types to avoid JSON/BSON encoding issues.
        """
        # Convert pandas/numpy types to native Python types
        def convert_value(val):
            if pd.isna(val):
                return None
            elif hasattr(val, 'item'):  # numpy types
                return val.item()
            elif isinstance(val, (int, float, str, bool)):
                return val
            else:
                return str(val)
        
        # Create row_data with converted values
        row_data = {}
        for k, v in row.to_dict().items():
            row_data[str(k)] = convert_value(v)
        
        return {
            'id': str(index),
            'name': str(sub_value) if sub_value else str(main_value),
            'price': float(self.safe_float(row.get('price', row.get('Price', 0)))),
            'category': str(main_value),
            'quantity': int(self.safe_int(row.get('quantity', row.get('Quantity', 1)))),
            'count': 1,
            'row_data': row_data,
            'original_index': int(index)
        }

    def recalculate_validation_data(self, groups_data: Dict) -> Dict:
        """
        Recalculate validation data from existing groups structure.
        This is crucial for fixing empty validation data issues.
        """
        print("Recalculating validation data from groups...")
        
        # Extract groups array from different possible structures
        groups = []
        ungrouped_items = []
        
        if isinstance(groups_data, dict):
            if 'groups' in groups_data:
                groups = groups_data.get('groups', [])
                ungrouped_items = groups_data.get('ungrouped_items', [])
            elif 'main_groups' in groups_data:
                # Convert legacy format
                main_groups = groups_data.get('main_groups', {})
                ungrouped_items = groups_data.get('ungrouped_items', [])
                
                # Convert main_groups dict to groups array
                for group_id, group_data in main_groups.items():
                    if isinstance(group_data, dict):
                        group_data['id'] = group_id
                        groups.append(group_data)
        
        # Count everything
        total_grouped_items = 0
        total_sub_groups = 0
        
        for group in groups:
            # Count items directly in main group
            if 'items' in group and group['items']:
                group_items = len(group['items'])
                total_grouped_items += group_items
                group['count'] = group_items
                group['item_count'] = group_items
            
            # Count sub-groups and their items
            if 'sub_groups' in group and group['sub_groups']:
                sub_group_count = len(group['sub_groups'])
                total_sub_groups += sub_group_count
                
                main_group_total = 0
                for sub_group in group['sub_groups']:
                    if 'items' in sub_group and sub_group['items']:
                        sub_items = len(sub_group['items'])
                        main_group_total += sub_items
                        total_grouped_items += sub_items
                        sub_group['count'] = sub_items
                        sub_group['item_count'] = sub_items
                
                # Update main group count to include sub-group items
                if main_group_total > 0:
                    group['count'] = main_group_total
                    group['item_count'] = main_group_total
        
        # Count ungrouped items
        ungrouped_count = len(ungrouped_items)
        total_rows = total_grouped_items + ungrouped_count
        
        # Create validation structure
        validation_data = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'counts': {
                'total_rows': total_rows,
                'grouped_records': total_grouped_items,
                'ungrouped_records': ungrouped_count,
                'main_groups': len(groups),
                'total_sub_groups': total_sub_groups
            }
        }
        
        # Validate the counts
        if total_grouped_items + ungrouped_count != total_rows:
            validation_data['errors'].append(f"Count mismatch detected during recalculation")
            validation_data['is_valid'] = False
        
        print(f"Recalculated validation data:")
        print(f"  Total rows: {total_rows}")
        print(f"  Grouped records: {total_grouped_items}")
        print(f"  Ungrouped records: {ungrouped_count}")
        print(f"  Main groups: {len(groups)}")
        print(f"  Sub groups: {total_sub_groups}")
        
        # Update the original structure
        updated_data = {
            'groups': groups,
            'ungrouped_items': ungrouped_items,
            'validation': validation_data,
            'total_items': total_rows,
            'grouped_items': total_grouped_items,
            'ungrouped_count': ungrouped_count,
            'total_groups': len(groups),
            'total_sub_groups': total_sub_groups,
            'is_valid': validation_data['is_valid']
        }
        
        return updated_data

    def generate_main_groups_from_unique_values(self, df: pd.DataFrame, column_name: str) -> Dict[str, Any]:
        """
        Create main groups for each unique value in the user-selected column.
        Each unique value becomes a main group containing all records with that value.
        """
        try:
            print(f"\n=== Creating Main Groups from Unique Values ===")
            print(f"Dataset size: {len(df)} rows")
            print(f"Column: {column_name}")
            
            if column_name not in df.columns:
                raise Exception(f"Column '{column_name}' not found in dataset")
            
            # Get unique values and their counts
            unique_values = df[column_name].value_counts()
            print(f"Found {len(unique_values)} unique values")
            
            # Create groups for each unique value
            groups = []
            total_grouped_items = 0
            
            for unique_value, count in unique_values.items():
                # Skip null/empty values
                if pd.isna(unique_value) or str(unique_value).strip() == '':
                    continue
                
                # Get all rows with this value
                value_rows = df[df[column_name] == unique_value]
                
                # Create items for this group
                items = []
                for index, row in value_rows.iterrows():
                    item = self.create_item_from_row(row, index, str(unique_value), str(unique_value))
                    items.append(item)
                
                # Create main group
                group = {
                    'id': self.generate_group_id(),
                    'name': str(unique_value),
                    'enabled': True,
                    'type': 'main',
                    'items': [],  # Main group items (empty for this approach)
                    'sub_groups': [{
                        'id': self.generate_group_id(),
                        'name': f"{unique_value} Items",
                        'items': items,
                        'count': len(items),
                        'item_count': len(items)
                    }],
                    'count': len(items),
                    'item_count': len(items),
                    'estimated_savings': f"{min(30, len(items) * 2)}%"
                }
                
                groups.append(group)
                total_grouped_items += len(items)
                
                print(f"Created group '{unique_value}' with {len(items)} items")
            
            # Handle ungrouped items (null/empty values)
            ungrouped_items = []
            null_rows = df[pd.isna(df[column_name]) | (df[column_name].astype(str).str.strip() == '')]
            
            for index, row in null_rows.iterrows():
                item = self.create_item_from_row(row, index, 'Ungrouped', 'No Value')
                ungrouped_items.append(item)
            
            # Calculate validation
            validation_results = self.validate_and_count_groups(groups, len(df))
            
            # Create final result
            result = {
                'groups': groups,
                'ungrouped_items': ungrouped_items,
                'validation': validation_results,
                'total_items': len(df),
                'grouped_items': total_grouped_items,
                'ungrouped_count': len(ungrouped_items),
                'total_groups': len(groups),
                'total_sub_groups': len(groups),  # Each main group has 1 sub-group
                'estimated_time_saved': self.calculate_estimated_savings(df.to_dict('records')),
                'is_valid': validation_results['is_valid'],
                'processing_method': 'unique_values_main_groups',
                'source_column': column_name
            }
            
            print(f"\n=== Main Groups Creation Complete ===")
            print(f"Main groups created: {len(groups)}")
            print(f"Total items processed: {len(df)}")
            print(f"Grouped items: {total_grouped_items}")
            print(f"Ungrouped items: {len(ungrouped_items)}")
            
            return result
            
        except Exception as e:
            print(f"Error creating main groups from unique values: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def generate_ai_powered_sub_groups_from_columns(self, df: pd.DataFrame, main_group_column: str = None, sub_group_column: str = None):
        """
        Generate AI-powered groups with intelligent sub-grouping.
        
        If main_group_column is provided:
        - Creates main groups for each unique value in main_group_column
        - Within each main group, analyzes sub_group_column for AI-powered sub-grouping
        
        If main_group_column is None:
        - Creates AI-powered sub-groups directly from sub_group_column across entire dataset
        """
        try:
            print(f"\n=== AI-Powered Sub-Grouping Analysis ===")
            print(f"Dataset size: {len(df)} rows")
            print(f"Main group column: {main_group_column}")
            print(f"Sub group column: {sub_group_column}")
            
            if not sub_group_column or sub_group_column not in df.columns:
                raise Exception(f"Sub group column '{sub_group_column}' is required and must exist in dataset")
            
            groups = []
            total_grouped_items = 0
            
            if main_group_column and main_group_column in df.columns:
                # Scenario 1: WITH Main Groups
                print(f"🎯 Processing WITH main groups from column: {main_group_column}")
                
                # Get unique values in main group column
                main_unique_values = df[main_group_column].value_counts()
                print(f"Found {len(main_unique_values)} main groups")
                
                for main_value, main_count in main_unique_values.items():
                    if pd.isna(main_value) or str(main_value).strip() == '':
                        continue
                    
                    print(f"\n📁 Processing main group: '{main_value}' ({main_count} records)")
                    
                    # Filter DataFrame for this main group
                    filtered_df = df[df[main_group_column] == main_value]
                    
                    # Get unique values and counts for sub-group column within this main group
                    sub_unique_values = filtered_df[sub_group_column].unique()
                    sub_value_counts = filtered_df[sub_group_column].value_counts()
                    
                    # Clean and prepare data for AI
                    clean_sub_values = []
                    clean_sub_counts = []
                    
                    for value in sub_unique_values:
                        if pd.notna(value) and str(value).strip():
                            clean_value = str(value).strip()
                            count = sub_value_counts.get(value, 0)
                            if hasattr(count, 'item'):
                                count = count.item()
                            clean_sub_values.append(clean_value)
                            clean_sub_counts.append(int(count))
                    
                    print(f"   Sub-column analysis: {len(clean_sub_values)} unique values")
                    print(f"   Sample values: {clean_sub_values[:5]}...")
                    
                    # Create AI-powered sub-groups for this main group
                    ai_sub_groups = self.create_ai_sub_groups_for_main_group(
                        filtered_df, clean_sub_values, clean_sub_counts, 
                        main_value, sub_group_column
                    )
                    
                    # The create_ai_sub_groups_for_main_group method already has fallback logic
                    if not ai_sub_groups:
                        ai_sub_groups = []  # Empty list to prevent errors, let validation handle it
                    
                    # Create main group with AI sub-groups
                    main_group = {
                        'id': self.generate_group_id(),
                        'name': str(main_value),
                        'enabled': True,
                        'type': 'main',
                        'items': [],  # No direct items in main group
                        'sub_groups': ai_sub_groups,
                        'count': main_count,
                        'item_count': main_count,
                        'estimated_savings': f"{min(30, main_count * 2)}%"
                    }
                    
                    groups.append(main_group)
                    total_grouped_items += main_count
                    
                    print(f"   ✅ Created {len(ai_sub_groups)} AI-powered sub-groups for '{main_value}'")
            
            else:
                # Scenario 2: WITHOUT Main Groups - Direct AI sub-grouping
                print(f"🤖 Processing WITHOUT main groups - direct AI sub-grouping")
                
                # Get unique values and counts for entire dataset
                sub_unique_values = df[sub_group_column].unique()
                sub_value_counts = df[sub_group_column].value_counts()
                
                # Clean and prepare data for AI
                clean_sub_values = []
                clean_sub_counts = []
                
                for value in sub_unique_values:
                    if pd.notna(value) and str(value).strip():
                        clean_value = str(value).strip()
                        count = sub_value_counts.get(value, 0)
                        if hasattr(count, 'item'):
                            count = count.item()
                        clean_sub_values.append(clean_value)
                        clean_sub_counts.append(int(count))
                
                print(f"Sub-column analysis: {len(clean_sub_values)} unique values across entire dataset")
                
                # Create AI-powered sub-groups for entire dataset
                ai_sub_groups = self.create_ai_sub_groups_for_dataset(
                    df, clean_sub_values, clean_sub_counts, sub_group_column
                )
                
                # The create_ai_sub_groups_for_dataset method already has fallback logic
                if not ai_sub_groups:
                    ai_sub_groups = []  # Empty list to prevent errors, let validation handle it
                
                # Create single main group containing all AI sub-groups
                main_group = {
                    'id': self.generate_group_id(),
                    'name': f"All {sub_group_column} Groups",
                    'enabled': True,
                    'type': 'main',
                    'items': [],
                    'sub_groups': ai_sub_groups,
                    'count': len(df),
                    'item_count': len(df),
                    'estimated_savings': f"{min(30, len(df) * 2)}%"
                }
                
                groups.append(main_group)
                total_grouped_items = len(df)
                
                print(f"✅ Created {len(ai_sub_groups)} AI-powered sub-groups")
            
            # Handle ungrouped items
            ungrouped_items = []
            ungrouped_count = len(df) - total_grouped_items
            
            if ungrouped_count > 0:
                print(f"Handling {ungrouped_count} ungrouped items...")
                # Add ungrouped items logic here if needed
            
            # Calculate validation
            validation_results = self.validate_and_count_groups(groups, len(df))
            
            # Create final result
            result = {
                'groups': groups,
                'ungrouped_items': ungrouped_items,
                'validation': validation_results,
                'total_items': len(df),
                'grouped_items': total_grouped_items,
                'ungrouped_count': ungrouped_count,
                'total_groups': len(groups),
                'total_sub_groups': sum(len(g.get('sub_groups', [])) for g in groups),
                'estimated_time_saved': self.calculate_estimated_savings(df.to_dict('records')),
                'is_valid': validation_results['is_valid'],
                'processing_method': 'ai_powered_sub_grouping',
                'main_column': main_group_column,
                'sub_column': sub_group_column
            }
            
            print(f"\n=== AI-Powered Sub-Grouping Complete ===")
            print(f"Main groups created: {len(groups)}")
            print(f"Total sub-groups: {result['total_sub_groups']}")
            print(f"Records processed: {len(df)}")
            print(f"Validation: {validation_results['is_valid']}")
            
            return result
            
        except Exception as e:
            print(f"❌ ERROR in AI-powered sub-grouping: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def create_ai_sub_groups_for_main_group(self, filtered_df: pd.DataFrame, unique_values: List[str], 
                                           value_counts: List[int], main_group_name: str, sub_column: str):
        """
        Create AI-powered sub-groups for a specific main group using core product type analysis.
        """
        try:
            print(f"🤖 Creating AI sub-groups for main group '{main_group_name}'")
            print(f"📊 Data analysis: {len(filtered_df)} rows, {len(unique_values)} unique values in '{sub_column}'")
            print(f"📋 Sample unique values: {unique_values[:5]}")
            
            # Try AI sub-grouping first
            try:
                sub_grouping_plan = self.create_ai_sub_grouping_plan(
                    unique_values, value_counts, main_group_name, sub_column
                )
                
                if sub_grouping_plan:
                    # Apply the sub-grouping plan to create actual sub-groups
                    sub_groups = self.apply_ai_sub_grouping_plan(
                        filtered_df, sub_grouping_plan, sub_column
                    )
                    
                    # Add "Other Items" sub-group for ungrouped items
                    sub_groups = self.add_other_items_sub_group(filtered_df, sub_groups, sub_column)
                    
                    if sub_groups and len(sub_groups) > 0:
                        print(f"✅ AI sub-grouping successful for '{main_group_name}'")
                        return sub_groups
            
            except Exception as ai_error:
                print(f"⚠️ AI sub-grouping failed for '{main_group_name}': {str(ai_error)}")
                print(f"🔄 Falling back to similarity-based sub-grouping...")
            
            # Fallback to similarity-based sub-grouping
            print(f"🔧 Using fallback similarity-based sub-grouping for '{main_group_name}'")
            fallback_sub_groups = self.create_fallback_sub_groups(filtered_df, sub_column)
            
            if fallback_sub_groups and len(fallback_sub_groups) > 0:
                print(f"✅ Fallback sub-grouping successful for '{main_group_name}'")
                return fallback_sub_groups
            else:
                print(f"🔧 Trying intelligent value-based sub-grouping for '{main_group_name}'...")
                # Try value-based sub-grouping before giving up
                value_based_sub_groups = self.create_simple_value_based_sub_groups(filtered_df, sub_column)
                
                if value_based_sub_groups and len(value_based_sub_groups) > 1:
                    print(f"✅ Value-based sub-grouping successful for '{main_group_name}': {len(value_based_sub_groups)} sub-groups")
                    return value_based_sub_groups
                else:
                    print(f"🔧 Creating default sub-group for '{main_group_name}' as ultimate fallback")
                    # Ultimate fallback - create one sub-group with all items
                    default_sub_group = self.create_default_sub_group(filtered_df, main_group_name, sub_column)
                    if default_sub_group:
                        return [default_sub_group]
                    else:
                        print(f"❌ All sub-grouping methods failed for '{main_group_name}'")
                        return []  # Return empty list instead of raising error
            
        except Exception as e:
            print(f"❌ ERROR creating sub-groups for '{main_group_name}': {str(e)}")
            # Instead of raising, return empty list to allow graceful handling
            return []

    def create_fallback_sub_groups(self, df: pd.DataFrame, sub_column: str):
        """
        Create fallback sub-groups using intelligent analysis when AI fails.
        This method creates multiple meaningful sub-groups based on actual product analysis.
        """
        try:
            print(f"🔧 Creating intelligent fallback sub-groups...")
            
            # Get unique values in the sub-column
            unique_values = df[sub_column].dropna().unique()
            print(f"🔍 Analyzing {len(unique_values)} unique values for intelligent sub-grouping")
            
            if len(unique_values) <= 1:
                print(f"⚠️ Only {len(unique_values)} unique value(s), creating single sub-group")
                return self.create_simple_value_based_sub_groups(df, sub_column)
            
            # Use rule-based intelligent grouping
            sub_groups = self.create_rule_based_sub_groups(df, sub_column, unique_values)
            
            if len(sub_groups) >= 2:
                print(f"✅ Created {len(sub_groups)} intelligent fallback sub-groups")
                return sub_groups
            else:
                print(f"🔄 Rule-based grouping yielded {len(sub_groups)} groups, trying similarity-based...")
                # Fall back to similarity if rule-based doesn't work well
                return self.create_similarity_based_sub_groups(df, sub_column)
            
        except Exception as e:
            print(f"❌ ERROR in fallback sub-grouping: {str(e)}")
            return self.create_simple_value_based_sub_groups(df, sub_column)

    def create_rule_based_sub_groups(self, df: pd.DataFrame, sub_column: str, unique_values: List[str]):
        """
        Create sub-groups using intelligent rules that follow your requirements.
        """
        try:
            print(f"🧠 Applying intelligent rules for sub-grouping...")
            
            # Create groups based on core product type analysis
            product_groups = {}
            
            for value in unique_values:
                if pd.isna(value) or str(value).strip() == '':
                    continue
                    
                value_str = str(value).strip()
                
                # Extract core product type using intelligent rules
                core_type = self.extract_core_product_type_fallback(value_str)
                
                if core_type not in product_groups:
                    product_groups[core_type] = []
                
                product_groups[core_type].append(value_str)
            
            print(f"📊 Found {len(product_groups)} core product types: {list(product_groups.keys())}")
            
            # Convert to sub-groups
            sub_groups = []
            for core_type, values in product_groups.items():
                if len(values) == 0:
                    continue
                    
                # Get all items for this core type
                group_items = []
                for value in values:
                    matching_rows = df[df[sub_column] == value]
                    for index, row in matching_rows.iterrows():
                        item = self.create_item_from_row(row, index, core_type, value)
                        group_items.append(item)
                
                if group_items:
                    sub_group = {
                        'id': self.generate_group_id(),
                        'name': core_type,
                        'items': group_items,
                        'count': len(group_items),
                        'item_count': len(group_items),
                        'is_rule_based': True,
                        'reasoning': f'Grouped by core product type: {core_type}'
                    }
                    sub_groups.append(sub_group)
                    print(f"   ✅ Created '{core_type}' sub-group with {len(group_items)} items")
            
            return sub_groups
            
        except Exception as e:
            print(f"❌ ERROR in rule-based sub-grouping: {str(e)}")
            return []

    def extract_core_product_type_fallback(self, value_str: str) -> str:
        """
        Extract core product type using intelligent rules (fallback when AI fails).
        """
        try:
            value_lower = value_str.lower().strip()
            
            # Remove common size/weight/brand indicators
            # Remove sizes like "1kg", "2kg", "500g", "1L", "2L", etc.
            import re
            value_clean = re.sub(r'\b\d+(\.\d+)?\s*(kg|g|l|ml|lb|oz|inch|cm|mm)\b', '', value_lower)
            
            # Remove common brand indicators and descriptors
            brand_words = ['brand', 'co', 'ltd', 'inc', 'corp', '&', 'and']
            color_words = ['red', 'blue', 'green', 'yellow', 'black', 'white', 'brown', 'pink', 'grey', 'gray', 'orange', 'purple']
            size_words = ['small', 'medium', 'large', 'xl', 'xxl', 'mini', 'big', 'tiny', 'huge']
            
            words = value_clean.split()
            filtered_words = []
            
            for word in words:
                if (word not in brand_words and 
                    word not in color_words and 
                    word not in size_words and 
                    not word.isdigit() and
                    len(word) > 1):
                    filtered_words.append(word)
            
            if not filtered_words:
                # If all words were filtered out, use the first word from original
                first_word = value_str.split()[0] if value_str.split() else value_str
                return self.normalize_product_name(first_word)
            
            # Take the most meaningful words (usually the first 1-2 words after filtering)
            core_words = filtered_words[:2]
            core_type = ' '.join(core_words).title()
            
            # Normalize common product types
            core_type = self.normalize_product_name(core_type)
            
            return core_type
            
        except Exception as e:
            print(f"❌ ERROR extracting core type from '{value_str}': {str(e)}")
            return self.normalize_product_name(value_str.split()[0] if value_str.split() else value_str)

    def create_similarity_based_sub_groups(self, df: pd.DataFrame, sub_column: str):
        """
        Create sub-groups using similarity analysis.
        """
        try:
            print(f"🔍 Creating similarity-based sub-groups...")
            
            # Convert DataFrame to items for processing
            items = []
            for index, row in df.iterrows():
                sub_value = str(row.get(sub_column, '')) if pd.notna(row.get(sub_column)) else ''
                
                if not sub_value.strip():
                    continue
                
                item = self.create_item_from_row(row, index, 'Similarity Group', sub_value)
                items.append(item)
            
            if not items:
                print(f"❌ No valid items found for similarity-based sub-grouping")
                return []
            
            print(f"🔍 Processing {len(items)} items for similarity analysis")
            
            # Use existing similarity grouping method with lower threshold for more groups
            similarity_groups = self.create_similarity_groups(items, similarity_threshold=0.5)
            
            # Convert to sub-groups format
            sub_groups = []
            for group_info in similarity_groups:
                if len(group_info['items']) >= 1:
                    sub_group = {
                        'id': self.generate_group_id(),
                        'name': group_info['name'],
                        'items': group_info['items'],
                        'count': len(group_info['items']),
                        'item_count': len(group_info['items']),
                        'is_similarity_based': True
                    }
                    sub_groups.append(sub_group)
            
            print(f"🔧 Created {len(sub_groups)} similarity-based sub-groups")
            return sub_groups
            
        except Exception as e:
            print(f"❌ ERROR in similarity-based sub-grouping: {str(e)}")
            return []

    def create_simple_value_based_sub_groups(self, df: pd.DataFrame, sub_column: str):
        """
        Create sub-groups based on unique values (when other methods fail).
        """
        try:
            print(f"🔧 Creating value-based sub-groups...")
            
            unique_values = df[sub_column].dropna().unique()
            sub_groups = []
            
            # If we have very few unique values, group them individually
            if len(unique_values) <= 10:
                for value in unique_values:
                    if pd.isna(value) or str(value).strip() == '':
                        continue
                        
                    matching_rows = df[df[sub_column] == value]
                    group_items = []
                    
                    for index, row in matching_rows.iterrows():
                        item = self.create_item_from_row(row, index, str(value), value)
                        group_items.append(item)
                    
                    if group_items:
                        sub_group = {
                            'id': self.generate_group_id(),
                            'name': self.normalize_product_name(str(value)),
                            'items': group_items,
                            'count': len(group_items),
                            'item_count': len(group_items),
                            'is_value_based': True
                        }
                        sub_groups.append(sub_group)
                
                print(f"✅ Created {len(sub_groups)} value-based sub-groups")
                return sub_groups
            else:
                # Too many unique values, fallback to single group
                print(f"⚠️ Too many unique values ({len(unique_values)}), creating single fallback group")
                return []
                
        except Exception as e:
            print(f"❌ ERROR in value-based sub-grouping: {str(e)}")
            return []

    def create_default_sub_group(self, df: pd.DataFrame, group_name: str, sub_column: str):
        """
        Create a default sub-group containing all items as ultimate fallback.
        """
        try:
            print(f"🛡️ Creating default sub-group for '{group_name}'")
            
            items = []
            for index, row in df.iterrows():
                sub_value = str(row.get(sub_column, '')) if pd.notna(row.get(sub_column)) else 'Unknown'
                item = self.create_item_from_row(row, index, group_name, sub_value)
                items.append(item)
            
            if items:
                default_sub_group = {
                    'id': self.generate_group_id(),
                    'name': f"All {group_name} Items",
                    'items': items,
                    'count': len(items),
                    'item_count': len(items),
                    'is_default_fallback': True
                }
                print(f"✅ Created default sub-group with {len(items)} items")
                return default_sub_group
            else:
                print(f"❌ No items found for default sub-group")
                return None
                
        except Exception as e:
            print(f"❌ ERROR creating default sub-group: {str(e)}")
            return None

    def create_ai_sub_groups_for_dataset(self, df: pd.DataFrame, unique_values: List[str], 
                                       value_counts: List[int], sub_column: str):
        """
        Create AI-powered sub-groups for entire dataset (when no main groups).
        """
        try:
            print(f"🤖 Creating AI sub-groups for entire dataset")
            
            # Try AI sub-grouping first
            try:
                sub_grouping_plan = self.create_ai_sub_grouping_plan(
                    unique_values, value_counts, "Dataset", sub_column
                )
                
                if sub_grouping_plan:
                    # Apply the sub-grouping plan to create actual sub-groups
                    sub_groups = self.apply_ai_sub_grouping_plan(
                        df, sub_grouping_plan, sub_column
                    )
                    
                    # Add "Other Items" sub-group for ungrouped items
                    sub_groups = self.add_other_items_sub_group(df, sub_groups, sub_column)
                    
                    if sub_groups and len(sub_groups) > 0:
                        print(f"✅ AI sub-grouping successful for entire dataset")
                        return sub_groups
            
            except Exception as ai_error:
                print(f"⚠️ AI sub-grouping failed for dataset: {str(ai_error)}")
                print(f"🔄 Falling back to similarity-based sub-grouping...")
            
            # Fallback to similarity-based sub-grouping
            print(f"🔧 Using fallback similarity-based sub-grouping for entire dataset")
            fallback_sub_groups = self.create_fallback_sub_groups(df, sub_column)
            
            if fallback_sub_groups and len(fallback_sub_groups) > 0:
                print(f"✅ Fallback sub-grouping successful for dataset")
                return fallback_sub_groups
            else:
                print(f"🔧 Creating default sub-group for dataset as ultimate fallback")
                # Ultimate fallback - create one sub-group with all items
                default_sub_group = self.create_default_sub_group(df, "All Items", sub_column)
                if default_sub_group:
                    return [default_sub_group]
                else:
                    print(f"❌ All sub-grouping methods failed for dataset")
                    return []  # Return empty list instead of raising error
            
        except Exception as e:
            print(f"❌ ERROR creating sub-groups for dataset: {str(e)}")
            # Instead of raising, return empty list to allow graceful handling
            return []

    def create_ai_sub_grouping_plan(self, unique_values: List[str], value_counts: List[int], 
                                   context_name: str, column_name: str):
        """
        Use OpenAI to create an intelligent sub-grouping plan based on core product types.
        """
        try:
            print(f"🧠 Creating AI sub-grouping plan for {len(unique_values)} unique values")
            
            # Check if we have valid OpenAI API key
            if not self.openai_api_key or self.openai_api_key == "test-key-for-demo":
                print(f"❌ Invalid OpenAI API key: {self.openai_api_key[:10]}...")
                raise Exception("Invalid OpenAI API key. Please check your environment variables.")
            
            # Debug: Check if we have enough unique values to make sub-groups
            if len(unique_values) <= 1:
                print(f"⚠️ Only {len(unique_values)} unique value(s) in sub-column - cannot create multiple sub-groups")
                raise Exception(f"Insufficient unique values ({len(unique_values)}) for meaningful sub-grouping")
            
            # Prepare data for AI analysis
            values_with_counts = []
            for i, value in enumerate(unique_values):
                count = value_counts[i] if i < len(value_counts) else 0
                values_with_counts.append(f"{value} ({count} items)")
            
            print(f"📋 Sample values to analyze: {values_with_counts[:10]}")
            
            # Create AI prompt
            prompt = f"""
You are creating SUB-GROUPS within a main group "{context_name}". Your goal is to create MULTIPLE meaningful sub-groups based on CORE PRODUCT TYPE.

Column: {column_name}
Values to analyze: {values_with_counts[:75]}  # Analyze more values for better sub-grouping

CRITICAL REQUIREMENTS:
1. CREATE MULTIPLE SUB-GROUPS: Aim for 3-8 sub-groups to maximize organization
2. Same/Similar Products Together: Items with same core function go in same sub-group
3. Group by Core Product Type: Focus on what the product fundamentally is
4. Ignore Superficial Differences: Brands, colors, sizes, packaging → same sub-group
5. Handle Size/Weight Variations: "Flour 1kg" and "Flour 5kg" → same "Flour" sub-group
6. Recognize Synonyms: "Laptop" = "Notebook" = "Portable Computer" → same sub-group
7. Look Beyond Names: Focus on actual product function, not misleading category names

GOOD EXAMPLES (Multiple sub-groups within main groups):
Main Group "Office Supplies":
- Sub-group "Pens" → ["Ballpoint Pen", "Gel Pen", "Blue Pen", "Red Pen", "Bic Pen"]
- Sub-group "Paper" → ["A4 Paper", "Copy Paper", "Printer Paper", "White Paper"]
- Sub-group "Folders" → ["File Folder", "Manila Folder", "Document Folder"]

Main Group "Electronics":
- Sub-group "Laptops" → ["MacBook Pro", "Dell Laptop", "Gaming Laptop", "Notebook Computer"]
- Sub-group "Phones" → ["iPhone 13", "Samsung Galaxy", "Mobile Phone", "Smartphone"]
- Sub-group "Tablets" → ["iPad", "Android Tablet", "Surface Pro"]

Main Group "Food":
- Sub-group "Rice" → ["Rice 1kg", "Rice 5kg", "Basmati Rice", "White Rice", "Brown Rice"]
- Sub-group "Flour" → ["Wheat Flour", "All-Purpose Flour", "Flour 1kg", "Flour 2kg"]
- Sub-group "Sugar" → ["White Sugar", "Brown Sugar", "Sugar 500g", "Granulated Sugar"]

IMPORTANT: 
- Create MORE sub-groups rather than fewer (aim for 3-8 sub-groups)
- Each sub-group should contain items that are essentially the SAME PRODUCT with minor variations
- If you see 20+ unique values, create 5-8 sub-groups
- If you see 10-20 unique values, create 3-5 sub-groups  
- If you see 5-10 unique values, create 2-4 sub-groups
- Even with few values, try to find meaningful distinctions to create multiple sub-groups

Return JSON format:
{{
    "sub_groups": [
        {{
            "name": "Specific Product Type (e.g., 'Pens', 'Rice', 'Laptops')",
            "values": ["exact", "original", "values", "that", "belong", "together"],
            "reasoning": "Why these items are the same core product"
        }}
    ]
}}

Focus on creating MANY meaningful sub-groups based on IDENTICAL CORE PRODUCT FUNCTION.
"""

            print(f"📝 Sending request to OpenAI...")
            print(f"🔑 API Key present: {bool(self.openai_api_key)}")
            print(f"📊 Prompt length: {len(prompt)} characters")

            # Call OpenAI with better error handling
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "You are an expert product categorization specialist. Your specialty is creating MULTIPLE meaningful sub-groups within each main group. Always aim for 3-8 sub-groups per main group. Group identical/similar products together (same core function but different brands/sizes/colors). Ignore superficial differences like brand names, colors, sizes, and packaging."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=2500,  # Increased for more detailed sub-grouping
                    temperature=0.2   # Lower temperature for more consistent grouping
                )
                
                response_text = response.choices[0].message.content.strip()
                print(f"📝 AI Response received: {len(response_text)} characters")
                print(f"🔍 First 200 chars: {response_text[:200]}...")
                
            except openai.error.AuthenticationError as e:
                print(f"❌ OpenAI Authentication Error: {str(e)}")
                raise Exception(f"OpenAI API authentication failed. Please check your API key. Error: {str(e)}")
                
            except openai.error.RateLimitError as e:
                print(f"❌ OpenAI Rate Limit Error: {str(e)}")
                raise Exception(f"OpenAI API rate limit exceeded. Please try again later. Error: {str(e)}")
                
            except openai.error.APIError as e:
                print(f"❌ OpenAI API Error: {str(e)}")
                raise Exception(f"OpenAI API error occurred. Error: {str(e)}")
                
            except Exception as e:
                print(f"❌ Unexpected OpenAI Error: {str(e)}")
                print(f"Error type: {type(e)}")
                raise Exception(f"Unexpected error calling OpenAI API: {str(e)}")
            
            # Parse JSON response with better error handling
            try:
                # Extract JSON from response
                json_start = response_text.find('{')
                json_end = response_text.rfind('}') + 1
                
                if json_start == -1 or json_end == 0:
                    print(f"❌ No JSON found in response")
                    print(f"Full response: {response_text}")
                    raise ValueError("No JSON structure found in AI response")
                
                json_text = response_text[json_start:json_end]
                print(f"🔍 Extracted JSON: {json_text[:200]}...")
                
                plan = json.loads(json_text)
                
                if 'sub_groups' not in plan:
                    print(f"❌ No 'sub_groups' key in parsed JSON")
                    print(f"Available keys: {list(plan.keys())}")
                    raise ValueError("No 'sub_groups' found in AI response")
                
                sub_groups = plan['sub_groups']
                if not isinstance(sub_groups, list):
                    print(f"❌ 'sub_groups' is not a list: {type(sub_groups)}")
                    raise ValueError("'sub_groups' must be a list")
                
                if len(sub_groups) == 0:
                    print(f"❌ Empty sub_groups list")
                    raise ValueError("AI returned empty sub-groups list")
                
                print(f"✅ AI created {len(sub_groups)} sub-groups")
                for i, group in enumerate(sub_groups):
                    group_name = group.get('name', f'Group {i+1}')
                    group_values = group.get('values', [])
                    print(f"   {i+1}. '{group_name}' ({len(group_values)} items)")
                    if len(group_values) > 0:
                        print(f"      Sample values: {group_values[:3]}")
                
                # Validate we have enough sub-groups for good organization
                if len(sub_groups) < 2:
                    print(f"⚠️ AI created only {len(sub_groups)} sub-group(s). Ideally should have 3-8 sub-groups for better organization.")
                    print(f"📝 Consider: The unique values might be very similar, or the AI might need more specific instructions.")
                elif len(sub_groups) >= 3:
                    print(f"✅ Good! AI created {len(sub_groups)} sub-groups for effective organization.")
                
                return plan
                
            except json.JSONDecodeError as e:
                print(f"❌ Failed to parse AI JSON response: {e}")
                print(f"JSON text: {json_text}")
                print(f"Full response: {response_text}")
                raise Exception(f"Failed to parse AI response as JSON. Response may be malformed. Error: {str(e)}")
                
        except Exception as e:
            print(f"❌ ERROR in AI sub-grouping plan creation: {str(e)}")
            print(f"Error type: {type(e)}")
            import traceback
            traceback.print_exc()
            return None

    def apply_ai_sub_grouping_plan(self, df: pd.DataFrame, plan: dict, sub_column: str):
        """
        Apply the AI sub-grouping plan to create actual sub-groups with items.
        """
        try:
            print(f"🔧 Applying AI sub-grouping plan...")
            
            sub_groups = []
            used_values = set()
            
            for group_plan in plan.get('sub_groups', []):
                group_name = group_plan.get('name', 'Unknown Group')
                planned_values = group_plan.get('values', [])
                
                print(f"   Creating sub-group: '{group_name}' with {len(planned_values)} planned values")
                
                # Find all rows that match the planned values
                group_items = []
                for value in planned_values:
                    # Find exact matches first
                    matching_rows = df[df[sub_column] == value]
                    
                    # If no exact match, try fuzzy matching (case-insensitive, strip spaces)
                    if len(matching_rows) == 0:
                        value_clean = str(value).strip().lower()
                        for actual_value in df[sub_column].unique():
                            if pd.notna(actual_value):
                                actual_clean = str(actual_value).strip().lower()
                                if actual_clean == value_clean or value_clean in actual_clean or actual_clean in value_clean:
                                    matching_rows = df[df[sub_column] == actual_value]
                                    print(f"     🔍 Fuzzy matched '{value}' → '{actual_value}'")
                                    break
                    
                    for index, row in matching_rows.iterrows():
                        original_value = row[sub_column]
                        item = self.create_item_from_row(row, index, group_name, original_value)
                        group_items.append(item)
                        used_values.add(original_value)
                
                if group_items:
                    sub_group = {
                        'id': self.generate_group_id(),
                        'name': group_name,
                        'items': group_items,
                        'count': len(group_items),
                        'item_count': len(group_items),
                        'reasoning': group_plan.get('reasoning', 'AI-grouped by core product type')
                    }
                    sub_groups.append(sub_group)
                    print(f"     ✅ Created '{group_name}' with {len(group_items)} items")
            
            print(f"📊 Applied AI plan: {len(sub_groups)} sub-groups created")
            print(f"📊 Used {len(used_values)} unique values")
            
            return sub_groups
            
        except Exception as e:
            print(f"❌ ERROR applying AI sub-grouping plan: {str(e)}")
            return []

    def add_other_items_sub_group(self, df: pd.DataFrame, existing_sub_groups: List[dict], sub_column: str):
        """
        Add "Other Items" sub-group for items that weren't assigned to any AI sub-group.
        """
        try:
            # Find which values were already used
            used_values = set()
            for sub_group in existing_sub_groups:
                for item in sub_group.get('items', []):
                    original_value = item.get('row_data', {}).get(sub_column)
                    if original_value:
                        used_values.add(original_value)
            
            # Find unused values
            all_values = set(df[sub_column].dropna().unique())
            unused_values = all_values - used_values
            
            print(f"🗂️  Found {len(unused_values)} ungrouped values for 'Other Items' sub-group")
            
            if unused_values:
                other_items = []
                for value in unused_values:
                    matching_rows = df[df[sub_column] == value]
                    for index, row in matching_rows.iterrows():
                        item = self.create_item_from_row(row, index, 'Other Items', str(value))
                        other_items.append(item)
                
                if other_items:
                    other_sub_group = {
                        'id': self.generate_group_id(),
                        'name': 'Other Items',
                        'items': other_items,
                        'count': len(other_items),
                        'item_count': len(other_items),
                        'is_other_items': True
                    }
                    existing_sub_groups.append(other_sub_group)
                    print(f"     ✅ Added 'Other Items' sub-group with {len(other_items)} items")
            
            return existing_sub_groups
            
        except Exception as e:
            print(f"❌ ERROR adding other items sub-group: {str(e)}")
            return existing_sub_groups

# Global engine instance
engine = None


def get_engine():
    """Get or create the global engine instance"""
    global engine
    if engine is None:
        # Using a dummy API key for now - in production this should be properly configured
        engine = ProductGroupingEngine("dummy_key")
    return engine


def generate_intelligent_groups_with_config(df, use_main_groups=True, main_group_column=None, sub_group_column=None):
    """
    Main function for user-configured group generation.
    Called from server.py for the new configured endpoint.
    """
    try:
        engine = get_engine()
        return engine.generate_groups_with_config(df, use_main_groups, main_group_column, sub_group_column)
    except Exception as e:
        print(f"Error in generate_intelligent_groups_with_config: {str(e)}")
        return None


def generate_ai_powered_groups_with_config(df, main_group_column=None, sub_group_column=None):
    """
    Main function for AI-powered group generation using machine learning approach.
    Analyzes unique values and counts from specified columns and uses AI to intelligently group them.
    Called from server.py for the AI-powered configured endpoint.
    """
    try:
        engine = get_engine()
        return engine.generate_ai_powered_groups_from_columns(df, main_group_column, sub_group_column)
    except Exception as e:
        print(f"Error in generate_ai_powered_groups_with_config: {str(e)}")
        return None


def generate_intelligent_groups_chunked(df):
    """
    Main function for intelligent group generation with chunked processing.
    This is the function called from server.py for large datasets.
    """
    try:
        engine = get_engine()
        return engine.generate_intelligent_groups(df)
    except Exception as e:
        print(f"Error in generate_intelligent_groups_chunked: {str(e)}")
        return None


def generate_simple_fallback_groups(df, column_name=None):
    """
    Simple fallback grouping when main algorithm fails
    """
    try:
        if column_name and column_name in df.columns:
            # Use the specified column for grouping
            groups = []
            column_groups = df.groupby(column_name)
            
            for value, group_df in column_groups:
                if pd.isna(value) or str(value).strip() == '':
                    continue
                    
                group = {
                    'id': str(uuid.uuid4())[:8],
                    'name': str(value).title(),
                    'type': 'main',
                    'items': group_df.to_dict('records'),
                    'sub_groups': [],
                    'enabled': True
                }
                groups.append(group)
            
            grouped_count = sum(len(group['items']) for group in groups)
            
            return {
                'groups': groups,
                'ungrouped_items': [],
                'total_items': len(df),
                'grouped_items': grouped_count,
                'ungrouped_count': 0,
                'estimated_time_saved': f"{max(0, grouped_count * 0.5 / 60):.1f} minutes"
            }
        else:
            # Basic fallback - try to group by first text column
            text_columns = df.select_dtypes(include=['object']).columns
            if len(text_columns) > 0:
                return generate_simple_fallback_groups(df, text_columns[0])
            
            # Ultimate fallback - single group
            return {
                'groups': [{
                    'id': str(uuid.uuid4())[:8],
                    'name': 'All Items',
                    'type': 'main',
                    'items': df.to_dict('records'),
                    'sub_groups': [],
                    'enabled': True
                }],
                'ungrouped_items': [],
                'total_items': len(df),
                'grouped_items': len(df),
                'ungrouped_count': 0,
                'estimated_time_saved': f"{max(0, len(df) * 0.5 / 60):.1f} minutes"
            }
    except Exception as e:
        print(f"Error in fallback grouping: {str(e)}")
        return None

def generate_main_groups_from_unique_values(df, column_name):
    """
    Generate main groups for each unique value in the specified column.
    Each unique value becomes a main group.
    """
    global engine
    if engine is None:
        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key:
            raise Exception("OpenAI API key not found in environment variables")
        engine = ProductGroupingEngine(openai_key)
    
    return engine.generate_main_groups_from_unique_values(df, column_name)

def generate_ai_powered_sub_groups_with_config(df, main_group_column=None, sub_group_column=None):
    """
    Generate AI-powered groups with intelligent sub-grouping based on core product types.
    """
    global engine
    if engine is None:
        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key:
            raise Exception("OpenAI API key not found in environment variables")
        engine = ProductGroupingEngine(openai_key)
    
    return engine.generate_ai_powered_sub_groups_from_columns(df, main_group_column, sub_group_column)