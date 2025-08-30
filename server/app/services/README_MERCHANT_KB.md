# Merchant Knowledge Base (merchant_kb.json)

This file contains merchant patterns for automatic transaction classification in the Expense Tracker application.

## 🚀 **Quick Start**

### **View Statistics**
```bash
cd server
python utils/manage_merchant_kb.py stats
```

### **Add New Merchant**
```bash
python utils/manage_merchant_kb.py add \
  --pattern "NEWSTORE" \
  --name "New Store" \
  --category "shopping" \
  --confidence 0.85
```

### **Validate File**
```bash
python utils/manage_merchant_kb.py validate
```

## 📊 **Current Coverage**

- **180+ merchant patterns** across 10 categories
- **Food & Dining**: Zomato, Swiggy, McDonald's, KFC, Starbucks, etc.
- **E-commerce**: Amazon, Flipkart, Myntra, Nykaa, etc.
- **Transportation**: Uber, Ola, IRCTC, airlines, fuel stations
- **Entertainment**: Netflix, Spotify, Prime, Hotstar, etc.
- **Bills & Utilities**: Airtel, Jio, electricity, gas, etc.
- **Healthcare**: Apollo, Fortis, Netmeds, 1mg, etc.
- **Education**: BYJU'S, Unacademy, Udemy, Coursera, etc.
- **Banking**: ATM, transfers, salary, dividends, etc.

## 🎯 **Categories Available**

| Category | Description | Examples |
|----------|-------------|----------|
| `food` | Restaurants, food delivery, cafes | Zomato, Swiggy, Starbucks |
| `shopping` | E-commerce, retail stores | Amazon, Flipkart, Myntra |
| `transport` | Cabs, flights, fuel, public transport | Uber, Ola, IRCTC |
| `entertainment` | Streaming, movies, games | Netflix, Spotify, BookMyShow |
| `bills` | Utilities, phone bills, internet | Airtel, Jio, electricity |
| `healthcare` | Hospitals, pharmacies, medical | Apollo, Netmeds, pharmacy |
| `education` | Schools, courses, learning platforms | BYJU'S, Udemy, school fees |
| `salary` | Salary credits, bonuses | Salary, bonus, incentive |
| `investment` | Dividends, interest, returns | Dividend, interest, returns |
| `other` | Banking, transfers, miscellaneous | ATM, UPI, bank transfers |

## 🔧 **How It Works**

1. **Pattern Matching**: Transaction descriptions are matched against patterns
2. **Confidence Scoring**: Each pattern has a confidence score (0.0-1.0)
3. **Category Assignment**: Matched merchants are automatically categorized
4. **Fallback**: Unmatched transactions use keyword-based classification

## 📝 **Adding New Patterns**

### **Method 1: Command Line**
```bash
python utils/manage_merchant_kb.py add \
  --pattern "NEWCAFE" \
  --name "New Cafe" \
  --category "food" \
  --confidence 0.80
```

### **Method 2: Direct JSON Edit**
```json
"food_and_dining": {
  "NEWCAFE": {"name": "New Cafe", "category": "food", "confidence": 0.80}
}
