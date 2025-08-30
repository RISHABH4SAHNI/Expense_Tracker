# Merchant Knowledge Base Management Guide

This guide explains how to manage and update the merchant knowledge base (`merchant_kb.json`) for accurate transaction classification.

## 📁 **File Location**
```
server/app/services/merchant_kb.json
```

## 🏗️ **Structure Overview**

The merchant KB is organized into several sections:

### **1. Metadata Section**
```json
{
  "metadata": {
    "version": "1.0.0",
    "last_updated": "2025-01-30T12:30:00Z",
    "description": "Merchant Knowledge Base for transaction classification",
    "total_patterns": 180,
    "categories_covered": ["food", "shopping", "transport", ...]
  }
}
```

### **2. Merchant Patterns by Category**
```json
{
  "merchant_patterns": {
    "food_and_dining": {
      "ZOMATO": {"name": "Zomato", "category": "food", "confidence": 0.95},
      "SWIGGY": {"name": "Swiggy", "category": "food", "confidence": 0.95}
    },
    "e_commerce_shopping": {
      "AMAZON": {"name": "Amazon", "category": "shopping", "confidence": 0.95}
    }
  }
}
```

### **3. Regular Expression Patterns**
```json
{
  "regex_patterns": {
    "patterns": [
      {
        "pattern": "ZOMATO\\*ORDER.*",
        "merchant": "Zomato",
        "category": "food",
        "confidence": 0.95
      }
    ]
  }
}
```

## 🔧 **Update Methods**

### **Method 1: Direct JSON Editing** ⚡

**Best for:** Small updates, adding new merchants

1. **Backup the current file:**
   ```bash
   cp server/app/services/merchant_kb.json server/app/services/merchant_kb.json.backup
   ```

2. **Edit the JSON file directly:**
   ```json
   // Add new merchant to appropriate category
   "food_and_dining": {
     "NEWEATS": {"name": "New Eats", "category": "food", "confidence": 0.85}
   }
   ```

3. **Validate JSON syntax:**
   ```bash
   python -m json.tool server/app/services/merchant_kb.json
   ```

4. **Update metadata:**
   ```json
   {
     "metadata": {
       "last_updated": "2025-01-30T15:30:00Z",
       "total_patterns": 181  // Increment count
     }
   }
   ```

### **Method 2: CSV Upload (Planned)** 📊

**Best for:** Bulk updates, importing from external sources

**CSV Format:**
```csv
pattern,merchant_name,category,confidence,notes
STARBUCKS,Starbucks Coffee,food,0.90,Coffee chain
TARGET,Target Store,shopping,0.85,Retail store
SHELL,Shell Gas Station,transport,0.85,Fuel station
```

**Implementation Steps (Future):**
1. Create admin endpoint: `POST /admin/merchants/upload-csv`
2. Validate CSV format and data
3. Merge with existing patterns
4. Update metadata automatically

### **Method 3: API Endpoints (Planned)** 🔌

**Best for:** Programmatic updates, integrations

**Planned Endpoints:**
```http
# Get all merchants
GET /api/merchants

# Add new merchant
POST /api/merchants
{
  "pattern": "NEWSTORE",
  "name": "New Store",
  "category": "shopping",
  "confidence": 0.80
}

# Update existing merchant
PUT /api/merchants/{pattern}

# Delete merchant pattern
DELETE /api/merchants/{pattern}

# Bulk import
POST /api/merchants/bulk
```

### **Method 4: Machine Learning Suggestions** 🤖

**Best for:** Continuous improvement, automated learning

**How it works:**
1. System identifies unclassified transactions
2. Uses embeddings to find similar patterns
3. Suggests new merchant mappings
4. Admin reviews and approves suggestions

## 📝 **Adding New Merchants**

### **Step-by-Step Process:**

1. **Identify the transaction pattern:**
   ```
   Raw transaction: "NEWCAFE*COFFEE SHOP MUMBAI"
   Pattern to extract: "NEWCAFE"
   ```

2. **Choose appropriate category:**
   - `food` - Restaurants, cafes, food delivery
   - `shopping` - E-commerce, retail stores
   - `transport` - Cabs, flights, fuel
   - `entertainment` - Movies, streaming services
   - `bills` - Utilities, phone bills
   - `healthcare` - Hospitals, pharmacies
   - `education` - Schools, online courses
   - `salary` - Salary credits
   - `investment` - Dividends, interest
   - `other` - Everything else

3. **Determine confidence level:**
   - `0.95+` - Very specific patterns (e.g., "ZOMATO")
   - `0.85-0.94` - Clear but less specific (e.g., "STARBUCKS")
   - `0.70-0.84` - Generic terms (e.g., "RESTAURANT")
   - `0.60-0.69` - Very generic (e.g., "PAYMENT")

4. **Add to appropriate section:**
   ```json
   "food_and_dining": {
     "NEWCAFE": {
       "name": "New Cafe",
       "category": "food",
       "confidence": 0.85
     }
   }
   ```

## 🔍 **Testing New Patterns**

### **Manual Testing:**
```bash
# Test merchant classification
cd server
python -c "
from app.services.llm_client import llm_client
import asyncio

async def test():
    result = await llm_client.classify_transaction('NEWCAFE*COFFEE ORDER')
    print(result)

asyncio.run(test())
"
```

### **API Testing:**
```bash
# Test via API endpoint
curl -X POST http://localhost:8000/api/test-classification \
  -H "Content-Type: application/json" \
  -d '{"description": "NEWCAFE*COFFEE ORDER"}'
```

## 📊 **Best Practices**

### **Pattern Naming:**
- Use **UPPERCASE** for consistency
- Keep patterns **specific** but not too narrow
- Include **common variations** (e.g., "ZOMATO", "ZOMATO*")

### **Confidence Scoring:**
- Be **conservative** with high confidence scores
- **Test thoroughly** before setting confidence > 0.90
- **Review regularly** and adjust based on accuracy

### **Category Assignment:**
- **Consistent categorization** across similar merchants
- **User-friendly** category names
- **Consider user expectations** for spending reports

### **Maintenance:**
- **Regular backups** before major updates
- **Version control** for tracking changes
- **Performance monitoring** after updates
- **User feedback** integration for improvements

## 🚨 **Common Issues & Solutions**

### **Issue 1: JSON Syntax Errors**
```bash
# Validate JSON before committing
python -m json.tool merchant_kb.json > /dev/null && echo "Valid JSON" || echo "Invalid JSON"
```

### **Issue 2: Duplicate Patterns**
```bash
# Check for duplicates
cat merchant_kb.json | jq -r '.merchant_patterns[][] | keys[]' | sort | uniq -d
```

### **Issue 3: Performance Issues**
- **Limit total patterns** to < 500 for good performance
- **Use regex patterns** for complex matching
- **Consider pattern priority** (specific before generic)

### **Issue 4: Low Accuracy**
- **Review confidence scores** and adjust based on real data
- **Add more specific patterns** for commonly misclassified merchants
- **Use regex patterns** for complex transaction descriptions

## 📈 **Monitoring & Analytics**

### **Track Performance:**
- Classification accuracy rate
- Most frequently unclassified patterns
- User override statistics
- Processing time metrics

### **Regular Reviews:**
- **Weekly:** Review new unclassified transactions
- **Monthly:** Analyze classification accuracy
- **Quarterly:** Major pattern updates and improvements

## 🔄 **Backup & Recovery**

### **Backup Strategy:**
```bash
# Daily backup
cp merchant_kb.json backups/merchant_kb_$(date +%Y%m%d).json

# Keep last 30 days
find backups/ -name "merchant_kb_*.json" -mtime +30 -delete
```

### **Recovery:**
```bash
# Restore from backup
cp backups/merchant_kb_20250130.json merchant_kb.json

# Restart services
supervisorctl restart expense_tracker
