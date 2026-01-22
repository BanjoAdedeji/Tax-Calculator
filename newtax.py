from flask import Flask, render_template_string, request, jsonify

app = Flask(__name__)

# -------------------- TAX CONFIG --------------------
# NEW TAX LAW (2026) - UPDATED BRACKETS
PIT_BRACKETS_NEW = [
    (800000, 0.00),
    (3200000, 0.15),    # 800,001 - 3,200,000: 15%
    (7200000, 0.25),    # 3,200,001 - 7,200,000: 25%
    (12200000, 0.30),   # 7,200,001 - 12,200,000: 30%
    (22200000, 0.35),   # 12,200,001 - 22,200,000: 35%
    (float('inf'), 0.40)  # Above 22,200,000: 40%
]

# OLD TAX LAW (Pre-2026)
PIT_BRACKETS_OLD = [
    (300000, 0.07),
    (600000, 0.11),
    (1100000, 0.15),
    (1600000, 0.19),
    (3200000, 0.21),
    (float('inf'), 0.24)
]

CGT_RATE_NEW = 0.10  # New capital gains rate
CGT_RATE_OLD = 0.05  # Old capital gains rate
HOUSING_ALLOWANCE_CAP = 500000  # New housing allowance cap

def calculate_progressive_tax(amount, brackets):
    """Calculate progressive tax with the first bracket being tax-free"""
    tax = 0
    prev = 0
    
    # First bracket is always 0% (first ₦800,000 is not taxable)
    for limit, rate in brackets:
        if amount <= prev:
            break
        portion = min(amount, limit) - prev
        tax += portion * rate
        prev = limit
    
    return tax

# -------------------- PIT LOGIC --------------------
def calculate_pit(data, use_old_law=False):
    basic = float(data.get('basic_salary', 0))
    housing_raw = float(data.get('housing_allowance', 0))
    
    # Apply housing allowance cap only for new law
    if use_old_law:
        housing = housing_raw  # No cap in old law
    else:
        housing = min(housing_raw, HOUSING_ALLOWANCE_CAP)  # Apply cap for new law
    
    transport = float(data.get('transport_allowance', 0))
    others = float(data.get('other_allowances', 0))
    
    pension = float(data.get('pension', 0))
    nhf = float(data.get('nhf', 0))
    life = float(data.get('life_insurance', 0))
    
    capital_gains = float(data.get('capital_gains', 0))
    digital_assets = float(data.get('digital_assets', 0))
    
    gross = basic + housing + transport + others
    
    if use_old_law:
        # OLD LAW: Consolidated Relief Allowance = 1% of gross income + 200,000
        cra = (0.01 * gross) + 200000
        cgt_rate = CGT_RATE_OLD
        brackets = PIT_BRACKETS_OLD
        law_label = "OLD"
        first_tax_free = 0  # Old law had different structure
    else:
        # NEW LAW: Consolidated Relief Allowance = 20% of gross income + 200,000
        cra = (0.20 * gross) + 200000
        cgt_rate = CGT_RATE_NEW
        brackets = PIT_BRACKETS_NEW
        law_label = "NEW"
        first_tax_free = 800000  # First ₦800,000 is not taxable
    
    deductions = pension + nhf + life
    
    taxable_income = max(0, gross - cra - deductions)
    annual_paye = calculate_progressive_tax(taxable_income, brackets)
    monthly_paye = annual_paye / 12
    
    cgt = (capital_gains + digital_assets) * cgt_rate
    total_tax = annual_paye + cgt
    net_income = gross + capital_gains + digital_assets - total_tax
    monthly_take_home = net_income / 12
    
    return {
        "law": law_label,
        "gross_income": gross,
        "cra": cra,
        "taxable_income": taxable_income,
        "annual_paye": annual_paye,
        "monthly_paye": monthly_paye,
        "capital_gains_tax": cgt,
        "total_tax": total_tax,
        "net_income": net_income,
        "monthly_take_home": monthly_take_home,
        "housing_allowance_capped": housing,
        "housing_raw": housing_raw,
        "first_tax_free": first_tax_free
    }

# -------------------- CIT LOGIC --------------------
def calculate_cit(data, use_old_law=False):
    turnover = float(data.get('turnover', 0))
    profit = float(data.get('profit', 0))
    
    if use_old_law:
        # OLD CIT LAW
        if turnover <= 25_000_000:
            rate = 0.0
            company_size = "Small Company"
        elif turnover <= 100_000_000:
            rate = 0.20
            company_size = "Medium Company"
        else:
            rate = 0.30
            company_size = "Large Company"
        law_label = "OLD"
    else:
        # NEW CIT LAW (2026 changes)
        if turnover <= 50_000_000:  # Increased threshold for small companies
            rate = 0.0
            company_size = "Small Company"
        elif turnover <= 150_000_000:  # Increased threshold for medium companies
            rate = 0.18  # Reduced rate for medium companies
            company_size = "Medium Company"
        else:
            rate = 0.25  # Reduced rate for large companies
            company_size = "Large Company"
        law_label = "NEW"
    
    cit = profit * rate
    net_profit = profit - cit
    monthly_net_profit = net_profit / 12
    
    return {
        "law": law_label,
        "company_size": company_size,
        "turnover": turnover,
        "profit": profit,
        "cit_rate": rate * 100,
        "cit_payable": cit,
        "net_profit": net_profit,
        "monthly_net_profit": monthly_net_profit
    }

# -------------------- ROUTES --------------------
@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/calculate", methods=["POST"])
def calculate():
    data = request.get_json()
    tax_type = data.get("tax_type")
    
    if tax_type == "PIT":
        # Calculate both old and new laws
        old_result = calculate_pit(data, use_old_law=True)
        new_result = calculate_pit(data, use_old_law=False)
        
        # Calculate differences
        tax_diff = new_result["total_tax"] - old_result["total_tax"]
        net_diff = new_result["net_income"] - old_result["net_income"]
        monthly_diff = new_result["monthly_take_home"] - old_result["monthly_take_home"]
        
        recommendation = "Better under NEW law" if net_diff > 0 else "Better under OLD law"
        
        return jsonify({
            "old": old_result,
            "new": new_result,
            "comparison": {
                "tax_difference": tax_diff,
                "net_income_difference": net_diff,
                "monthly_take_home_difference": monthly_diff,
                "recommendation": recommendation
            }
        })
    else:
        # Calculate both old and new laws for CIT
        old_result = calculate_cit(data, use_old_law=True)
        new_result = calculate_cit(data, use_old_law=False)
        
        # Calculate differences
        tax_diff = new_result["cit_payable"] - old_result["cit_payable"]
        net_diff = new_result["net_profit"] - old_result["net_profit"]
        monthly_diff = new_result["monthly_net_profit"] - old_result["monthly_net_profit"]
        
        recommendation = "Better under NEW law" if net_diff > 0 else "Better under OLD law"
        
        return jsonify({
            "old": old_result,
            "new": new_result,
            "comparison": {
                "tax_difference": tax_diff,
                "net_profit_difference": net_diff,
                "monthly_profit_difference": monthly_diff,
                "recommendation": recommendation
            }
        })

# -------------------- HTML TEMPLATE --------------------
HTML = '''<!DOCTYPE html>
<html>
<head>
    <title>Nigeria Tax Calculator</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        
        body {
            background: linear-gradient(135deg, #f0f4f8 0%, #e6e9f0 100%);
            min-height: 100vh;
            padding: 20px;
            color: #333;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        .header {
            text-align: center;
            margin-bottom: 30px;
            padding: 25px;
            background: white;
            border-radius: 12px;
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.05);
            border: 1px solid #e0e0e0;
        }
        
        .header h1 {
            background: linear-gradient(to right, #2c5282, #9b2c2c);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            font-size: 2.4rem;
            margin-bottom: 10px;
        }
        
        .header p {
            color: #4a5568;
            font-size: 1.1rem;
        }
        
        .calculator-box {
            display: flex;
            flex-wrap: wrap;
            gap: 25px;
            margin-bottom: 30px;
        }
        
        .input-section {
            flex: 1;
            min-width: 350px;
            background: white;
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.05);
            border: 1px solid #e0e0e0;
        }
        
        .result-section {
            flex: 2;
            min-width: 350px;
            background: white;
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.05);
            border: 1px solid #e0e0e0;
        }
        
        .section-title {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 20px;
            padding-bottom: 12px;
            border-bottom: 2px solid #edf2f7;
        }
        
        .section-title i {
            font-size: 1.2rem;
            color: #2c5282;
        }
        
        .tax-type-selector {
            display: flex;
            margin-bottom: 25px;
            background: #f7fafc;
            border-radius: 8px;
            overflow: hidden;
            border: 1px solid #e2e8f0;
        }
        
        .tax-tab {
            flex: 1;
            padding: 16px;
            text-align: center;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.3s;
            color: #4a5568;
        }
        
        .tax-tab.active {
            background: linear-gradient(to right, #2c5282, #9b2c2c);
            color: white;
        }
        
        .input-group {
            margin-bottom: 20px;
            position: relative;
        }
        
        .input-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #2d3748;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .tooltip-icon {
            color: #9b2c2c;
            cursor: help;
            font-size: 0.9rem;
        }
        
        .input-group input, .input-group select {
            width: 100%;
            padding: 14px;
            border: 2px solid #e2e8f0;
            border-radius: 8px;
            font-size: 1rem;
            transition: border 0.3s;
            background: #f8fafc;
        }
        
        .input-group input:focus {
            border-color: #2c5282;
            outline: none;
            box-shadow: 0 0 0 3px rgba(44, 82, 130, 0.1);
            background: white;
        }
        
        .currency-symbol {
            position: absolute;
            right: 15px;
            top: 42px;
            color: #718096;
            font-weight: 600;
        }
        
        .tax-brackets-note {
            background: #f0f7ff;
            padding: 15px;
            border-radius: 8px;
            margin-top: 15px;
            margin-bottom: 15px;
            border-left: 4px solid #2c5282;
            font-size: 0.9rem;
        }
        
        .tax-brackets-note h4 {
            margin-bottom: 8px;
            color: #2c5282;
        }
        
        .tax-brackets-note table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }
        
        .tax-brackets-note th, .tax-brackets-note td {
            padding: 8px;
            text-align: left;
            border: 1px solid #cbd5e0;
        }
        
        .tax-brackets-note th {
            background: #ebf8ff;
            font-weight: 600;
        }
        
        .calculate-btn {
            width: 100%;
            padding: 16px;
            background: linear-gradient(to right, #2c5282, #9b2c2c);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 1.1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            margin-top: 10px;
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 10px;
        }
        
        .calculate-btn:hover {
            background: linear-gradient(to right, #23446e, #7a2323);
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(44, 82, 130, 0.2);
        }
        
        .result-container {
            display: none;
        }
        
        .law-comparison {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-top: 20px;
        }
        
        .law-column {
            padding: 20px;
            border-radius: 8px;
            border: 2px solid;
        }
        
        .new-law {
            border-color: #2c5282;
            background: linear-gradient(to bottom, #f0f7ff, #ffffff);
        }
        
        .old-law {
            border-color: #9b2c2c;
            background: linear-gradient(to bottom, #fff5f5, #ffffff);
        }
        
        .law-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid;
        }
        
        .new-law .law-header {
            border-color: #2c5282;
        }
        
        .old-law .law-header {
            border-color: #9b2c2c;
        }
        
        .law-title {
            font-weight: 700;
            font-size: 1.1rem;
        }
        
        .new-law .law-title {
            color: #2c5282;
        }
        
        .old-law .law-title {
            color: #9b2c2c;
        }
        
        .law-badge {
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: 600;
        }
        
        .new-law .law-badge {
            background: #2c5282;
            color: white;
        }
        
        .old-law .law-badge {
            background: #9b2c2c;
            color: white;
        }
        
        .result-item {
            display: flex;
            justify-content: space-between;
            padding: 12px 0;
            border-bottom: 1px solid #edf2f7;
        }
        
        .result-item:last-child {
            border-bottom: none;
        }
        
        .result-label {
            font-weight: 600;
            color: #4a5568;
        }
        
        .result-value {
            font-weight: 700;
            font-size: 1.1rem;
        }
        
        .new-law .result-value {
            color: #2c5282;
        }
        
        .old-law .result-value {
            color: #9b2c2c;
        }
        
        .tax-free-note {
            font-size: 0.85rem;
            color: #718096;
            font-style: italic;
            margin-top: 5px;
            display: block;
        }
        
        .highlight-box {
            background: #f8fafc;
            padding: 15px;
            border-radius: 8px;
            margin-top: 20px;
            border-left: 4px solid;
        }
        
        .new-law .highlight-box {
            border-left-color: #2c5282;
        }
        
        .old-law .highlight-box {
            border-left-color: #9b2c2c;
        }
        
        .highlight-box .result-label {
            font-size: 1.1rem;
        }
        
        .highlight-box .result-value {
            font-size: 1.3rem;
        }
        
        .comparison-summary {
            margin-top: 25px;
            padding: 20px;
            background: linear-gradient(to right, #f0f7ff, #fff5f5);
            border-radius: 8px;
            border: 1px solid #e2e8f0;
        }
        
        .summary-title {
            text-align: center;
            margin-bottom: 15px;
            color: #2d3748;
            font-size: 1.2rem;
            font-weight: 600;
        }
        
        .summary-item {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #e2e8f0;
        }
        
        .summary-item:last-child {
            border-bottom: none;
        }
        
        .summary-value {
            font-weight: 700;
        }
        
        .savings {
            color: #38a169;
        }
        
        .increase {
            color: #e53e3e;
        }
        
        .info-box {
            background: #f8fafc;
            padding: 15px;
            border-radius: 8px;
            margin-top: 20px;
            font-size: 0.9rem;
            color: #4a5568;
            border: 1px solid #e2e8f0;
        }
        
        .info-box i {
            color: #2c5282;
            margin-right: 8px;
        }
        
        .tax-form {
            display: block;
        }
        
        .tax-form.hidden {
            display: none;
        }
        
        .footer {
            text-align: center;
            margin-top: 30px;
            color: #718096;
            font-size: 0.9rem;
            padding: 20px;
            background: white;
            border-radius: 8px;
            border: 1px solid #e2e8f0;
        }
        
        @media (max-width: 768px) {
            .calculator-box {
                flex-direction: column;
            }
            
            .law-comparison {
                grid-template-columns: 1fr;
            }
            
            .header h1 {
                font-size: 1.8rem;
            }
        }
        
        .law-note {
            font-size: 0.85rem;
            color: #718096;
            margin-top: 5px;
            font-style: italic;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1><i class="fas fa-balance-scale"></i> Nigeria Tax Calculator</h1>
            <p>Compare Old vs New Tax Laws (Pre-2026 vs Post-2026) for PIT and CIT</p>
        </div>
        
        <div class="calculator-box">
            <div class="input-section">
                <div class="tax-type-selector">
                    <div class="tax-tab active" onclick="switchTaxType('PIT')">
                        <i class="fas fa-user"></i> Personal Income Tax
                    </div>
                    <div class="tax-tab" onclick="switchTaxType('CIT')">
                        <i class="fas fa-building"></i> Company Income Tax
                    </div>
                </div>
                
                <div id="pit-form" class="tax-form">
                    <div class="section-title">
                        <i class="fas fa-money-bill-wave"></i>
                        <h3>Income Details</h3>
                    </div>
                    
                    <div class="input-group">
                        <label>Basic Salary <span class="tooltip-icon" title="Your basic salary before any allowances">ⓘ</span></label>
                        <input type="number" id="basic_salary" placeholder="Enter amount">
                        <span class="currency-symbol">₦</span>
                    </div>
                    
                    <div class="input-group">
                        <label>Housing Allowance <span class="tooltip-icon" title="Housing Allowance (Capped) – Part of gross income meant for accommodation; included in taxable income but considered in relief calculations. Capped at ₦500,000 in new law.">ⓘ</span></label>
                        <input type="number" id="housing_allowance" placeholder="Enter amount">
                        <span class="currency-symbol">₦</span>
                        <div class="law-note">New law caps at ₦500,000</div>
                    </div>
                    
                    <div class="input-group">
                        <label>Transport Allowance <span class="tooltip-icon" title="Transport allowance provided by employer">ⓘ</span></label>
                        <input type="number" id="transport_allowance" placeholder="Enter amount">
                        <span class="currency-symbol">₦</span>
                    </div>
                    
                    <div class="input-group">
                        <label>Other Allowances <span class="tooltip-icon" title="Any other allowances or bonuses">ⓘ</span></label>
                        <input type="number" id="other_allowances" placeholder="Enter amount">
                        <span class="currency-symbol">₦</span>
                    </div>
                    
                    <div class="section-title">
                        <i class="fas fa-shield-alt"></i>
                        <h3>Deductions</h3>
                    </div>
                    
                    <div class="input-group">
                        <label>Pension Contribution <span class="tooltip-icon" title="Voluntary pension contribution (up to 20% of gross income)">ⓘ</span></label>
                        <input type="number" id="pension" placeholder="Enter amount">
                        <span class="currency-symbol">₦</span>
                    </div>
                    
                    <div class="input-group">
                        <label>NHF Contribution <span class="tooltip-icon" title="National Housing Fund contribution (2.5% of basic salary)">ⓘ</span></label>
                        <input type="number" id="nhf" placeholder="Enter amount">
                        <span class="currency-symbol">₦</span>
                    </div>
                    
                    <div class="input-group">
                        <label>Life Insurance <span class="tooltip-icon" title="Life insurance premium payments">ⓘ</span></label>
                        <input type="number" id="life_insurance" placeholder="Enter amount">
                        <span class="currency-symbol">₦</span>
                    </div>
                    
                    <div class="section-title">
                        <i class="fas fa-chart-line"></i>
                        <h3>Additional Income</h3>
                    </div>
                    
                    <div class="input-group">
                        <label>Capital Gains <span class="tooltip-icon" title="Profit from sale of assets like property, stocks">ⓘ</span></label>
                        <input type="number" id="capital_gains" placeholder="Enter amount">
                        <span class="currency-symbol">₦</span>
                    </div>
                    
                    <div class="input-group">
                        <label>Digital Asset Gains <span class="tooltip-icon" title="Profit from cryptocurrency and other digital assets (Old: 5%, New: 10%)">ⓘ</span></label>
                        <input type="number" id="digital_assets" placeholder="Enter amount">
                        <span class="currency-symbol">₦</span>
                    </div>
                    
                    <div class="tax-brackets-note">
                        <h4><i class="fas fa-info-circle"></i> New Tax Law (2026) Brackets:</h4>
                        <p><strong>Note:</strong> The first ₦800,000 of taxable income is NOT taxable.</p>
                        <table>
                            <thead>
                                <tr>
                                    <th>Taxable Income Bracket (₦)</th>
                                    <th>Tax Rate</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr>
                                    <td>0 – 800,000</td>
                                    <td>0% (Tax-Free)</td>
                                </tr>
                                <tr>
                                    <td>800,001 – 3,200,000</td>
                                    <td>15%</td>
                                </tr>
                                <tr>
                                    <td>3,200,001 – 7,200,000</td>
                                    <td>25%</td>
                                </tr>
                                <tr>
                                    <td>7,200,001 – 12,200,000</td>
                                    <td>30%</td>
                                </tr>
                                <tr>
                                    <td>12,200,001 – 22,200,000</td>
                                    <td>35%</td>
                                </tr>
                                <tr>
                                    <td>Above 22,200,000</td>
                                    <td>40%</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                    
                    <button class="calculate-btn" onclick="calculateTax()">
                        <i class="fas fa-calculator"></i> Compare Tax Laws
                    </button>
                </div>
                
                <div id="cit-form" class="tax-form hidden">
                    <div class="section-title">
                        <i class="fas fa-chart-bar"></i>
                        <h3>Company Financials</h3>
                    </div>
                    
                    <div class="input-group">
                        <label>Annual Turnover <span class="tooltip-icon" title="Total annual revenue/sales of the company">ⓘ</span></label>
                        <input type="number" id="turnover" placeholder="Enter amount">
                        <span class="currency-symbol">₦</span>
                    </div>
                    
                    <div class="input-group">
                        <label>Profit Before Tax <span class="tooltip-icon" title="Company profit before any tax deductions">ⓘ</span></label>
                        <input type="number" id="profit" placeholder="Enter amount">
                        <span class="currency-symbol">₦</span>
                    </div>
                    
                    <div class="tax-brackets-note">
                        <h4><i class="fas fa-info-circle"></i> CIT Rates Comparison:</h4>
                        <p><strong>Old Tax Law (Pre-2026):</strong><br>
                        • Small Companies (≤ ₦25M turnover): 0%<br>
                        • Medium Companies (≤ ₦100M): 20%<br>
                        • Large Companies: 30%</p>
                        <p><strong>New Tax Law (2026):</strong><br>
                        • Small Companies (≤ ₦50M turnover): 0%<br>
                        • Medium Companies (≤ ₦150M): 18%<br>
                        • Large Companies: 25%</p>
                    </div>
                    
                    <button class="calculate-btn" onclick="calculateTax()">
                        <i class="fas fa-calculator"></i> Compare Tax Laws
                    </button>
                </div>
            </div>
            
            <div class="result-section">
                <div class="section-title">
                    <i class="fas fa-balance-scale"></i>
                    <h3>Tax Law Comparison Results</h3>
                </div>
                
                <div id="pit-results" class="result-container">
                    <div class="law-comparison">
                        <!-- New Law Column -->
                        <div class="law-column new-law">
                            <div class="law-header">
                                <span class="law-title">New Tax Law (2026)</span>
                                <span class="law-badge">NEW</span>
                            </div>
                            
                            <div class="result-item">
                                <span class="result-label">Gross Income: <span class="tax-free-note">Total earnings before any deductions</span></span>
                                <span class="result-value" id="new-gross-income">₦0</span>
                            </div>
                            
                            <div class="result-item">
                                <span class="result-label">Housing Allowance (Capped): <span class="tax-free-note">Part of gross income for accommodation</span></span>
                                <span class="result-value" id="new-housing-capped">₦0</span>
                            </div>
                            
                            <div class="result-item">
                                <span class="result-label">Consolidated Relief: <span class="tax-free-note">20% + ₦200,000 deduction</span></span>
                                <span class="result-value" id="new-cra">₦0</span>
                            </div>
                            
                            <div class="result-item">
                                <span class="result-label">Taxable Income:</span>
                                <span class="result-value" id="new-taxable-income">₦0</span>
                            </div>
                            
                            <div class="result-item">
                                <span class="result-label">Annual PAYE Tax: <span class="tax-free-note">First ₦800,000 is tax-free</span></span>
                                <span class="result-value" id="new-annual-paye">₦0</span>
                            </div>
                            
                            <div class="result-item">
                                <span class="result-label">Capital Gains Tax (10%):</span>
                                <span class="result-value" id="new-cgt">₦0</span>
                            </div>
                            
                            <div class="highlight-box">
                                <div class="result-item">
                                    <span class="result-label">Total Tax Payable:</span>
                                    <span class="result-value" id="new-total-tax">₦0</span>
                                </div>
                            </div>
                            
                            <div class="highlight-box">
                                <div class="result-item">
                                    <span class="result-label">Monthly Take-Home:</span>
                                    <span class="result-value" id="new-monthly-take-home">₦0</span>
                                </div>
                            </div>
                            
                            <div class="highlight-box">
                                <div class="result-item">
                                    <span class="result-label">Net Income After Tax:</span>
                                    <span class="result-value" id="new-net-income">₦0</span>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Old Law Column -->
                        <div class="law-column old-law">
                            <div class="law-header">
                                <span class="law-title">Old Tax Law (Pre-2026)</span>
                                <span class="law-badge">OLD</span>
                            </div>
                            
                            <div class="result-item">
                                <span class="result-label">Gross Income:</span>
                                <span class="result-value" id="old-gross-income">₦0</span>
                            </div>
                            
                            <div class="result-item">
                                <span class="result-label">Housing Allowance:</span>
                                <span class="result-value" id="old-housing-capped">₦0</span>
                            </div>
                            
                            <div class="result-item">
                                <span class="result-label">Consolidated Relief: <span class="tax-free-note">1% + ₦200,000 deduction</span></span>
                                <span class="result-value" id="old-cra">₦0</span>
                            </div>
                            
                            <div class="result-item">
                                <span class="result-label">Taxable Income:</span>
                                <span class="result-value" id="old-taxable-income">₦0</span>
                            </div>
                            
                            <div class="result-item">
                                <span class="result-label">Annual PAYE Tax:</span>
                                <span class="result-value" id="old-annual-paye">₦0</span>
                            </div>
                            
                            <div class="result-item">
                                <span class="result-label">Capital Gains Tax (5%):</span>
                                <span class="result-value" id="old-cgt">₦0</span>
                            </div>
                            
                            <div class="highlight-box">
                                <div class="result-item">
                                    <span class="result-label">Total Tax Payable:</span>
                                    <span class="result-value" id="old-total-tax">₦0</span>
                                </div>
                            </div>
                            
                            <div class="highlight-box">
                                <div class="result-item">
                                    <span class="result-label">Monthly Take-Home:</span>
                                    <span class="result-value" id="old-monthly-take-home">₦0</span>
                                </div>
                            </div>
                            
                            <div class="highlight-box">
                                <div class="result-item">
                                    <span class="result-label">Net Income After Tax:</span>
                                    <span class="result-value" id="old-net-income">₦0</span>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="comparison-summary">
                        <div class="summary-title">Comparison Summary</div>
                        <div class="summary-item">
                            <span>Tax Difference (New - Old):</span>
                            <span class="summary-value" id="tax-difference">₦0</span>
                        </div>
                        <div class="summary-item">
                            <span>Net Income Difference:</span>
                            <span class="summary-value" id="net-income-difference">₦0</span>
                        </div>
                        <div class="summary-item">
                            <span>Monthly Take-Home Difference:</span>
                            <span class="summary-value" id="monthly-difference">₦0</span>
                        </div>
                        <div class="summary-item">
                            <span>Recommendation:</span>
                            <span class="summary-value" id="recommendation">-</span>
                        </div>
                    </div>
                </div>
                
                <div id="cit-results" class="result-container hidden">
                    <div class="law-comparison">
                        <!-- New Law Column -->
                        <div class="law-column new-law">
                            <div class="law-header">
                                <span class="law-title">New Tax Law (2026)</span>
                                <span class="law-badge">NEW</span>
                            </div>
                            
                            <div class="result-item">
                                <span class="result-label">Company Size:</span>
                                <span class="result-value" id="new-company-size">-</span>
                            </div>
                            
                            <div class="result-item">
                                <span class="result-label">Annual Turnover:</span>
                                <span class="result-value" id="new-turnover">₦0</span>
                            </div>
                            
                            <div class="result-item">
                                <span class="result-label">CIT Rate:</span>
                                <span class="result-value" id="new-cit-rate">0%</span>
                            </div>
                            
                            <div class="result-item">
                                <span class="result-label">Profit Before Tax:</span>
                                <span class="result-value" id="new-profit">₦0</span>
                            </div>
                            
                            <div class="highlight-box">
                                <div class="result-item">
                                    <span class="result-label">CIT Payable:</span>
                                    <span class="result-value" id="new-cit-payable">₦0</span>
                                </div>
                            </div>
                            
                            <div class="highlight-box">
                                <div class="result-item">
                                    <span class="result-label">Monthly Net Profit:</span>
                                    <span class="result-value" id="new-monthly-net-profit">₦0</span>
                                </div>
                            </div>
                            
                            <div class="highlight-box">
                                <div class="result-item">
                                    <span class="result-label">Net Profit After Tax:</span>
                                    <span class="result-value" id="new-net-profit">₦0</span>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Old Law Column -->
                        <div class="law-column old-law">
                            <div class="law-header">
                                <span class="law-title">Old Tax Law (Pre-2026)</span>
                                <span class="law-badge">OLD</span>
                            </div>
                            
                            <div class="result-item">
                                <span class="result-label">Company Size:</span>
                                <span class="result-value" id="old-company-size">-</span>
                            </div>
                            
                            <div class="result-item">
                                <span class="result-label">Annual Turnover:</span>
                                <span class="result-value" id="old-turnover">₦0</span>
                            </div>
                            
                            <div class="result-item">
                                <span class="result-label">CIT Rate:</span>
                                <span class="result-value" id="old-cit-rate">0%</span>
                            </div>
                            
                            <div class="result-item">
                                <span class="result-label">Profit Before Tax:</span>
                                <span class="result-value" id="old-profit">₦0</span>
                            </div>
                            
                            <div class="highlight-box">
                                <div class="result-item">
                                    <span class="result-label">CIT Payable:</span>
                                    <span class="result-value" id="old-cit-payable">₦0</span>
                                </div>
                            </div>
                            
                            <div class="highlight-box">
                                <div class="result-item">
                                    <span class="result-label">Monthly Net Profit:</span>
                                    <span class="result-value" id="old-monthly-net-profit">₦0</span>
                                </div>
                            </div>
                            
                            <div class="highlight-box">
                                <div class="result-item">
                                    <span class="result-label">Net Profit After Tax:</span>
                                    <span class="result-value" id="old-net-profit">₦0</span>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="comparison-summary">
                        <div class="summary-title">Comparison Summary</div>
                        <div class="summary-item">
                            <span>Tax Difference (New - Old):</span>
                            <span class="summary-value" id="cit-tax-difference">₦0</span>
                        </div>
                        <div class="summary-item">
                            <span>Net Profit Difference:</span>
                            <span class="summary-value" id="cit-net-profit-difference">₦0</span>
                        </div>
                        <div class="summary-item">
                            <span>Monthly Profit Difference:</span>
                            <span class="summary-value" id="cit-monthly-difference">₦0</span>
                        </div>
                        <div class="summary-item">
                            <span>Recommendation:</span>
                            <span class="summary-value" id="cit-recommendation">-</span>
                        </div>
                    </div>
                </div>
                
                <div id="no-results">
                    <div class="info-box">
                        <i class="fas fa-balance-scale"></i>
                        <p>Enter your income/financial details and click "Compare Tax Laws" to see side-by-side comparison of old vs new tax laws.</p>
                    </div>
                </div>
                
                <div class="info-box">
                    <i class="fas fa-lightbulb"></i>
                    <p><strong>Note:</strong> This calculator provides estimates for comparison purposes. The new tax law (2026) features: 1) Housing allowance cap of ₦500,000, 2) Higher CRA (20% vs 1%), 3) Different tax brackets, 4) Higher capital gains tax (10% vs 5%), 5) Different CIT rates and thresholds.</p>
                </div>
            </div>
        </div>
        
        <div class="footer">
            <p>Nigeria Tax Law Comparison Calculator v3.0 | Blue-Red Theme | Old vs New Tax Law Analysis</p>
        </div>
    </div>

    <script>
        let currentTaxType = 'PIT';
        
        function switchTaxType(type) {
            currentTaxType = type;
            
            // Update tabs
            document.querySelectorAll('.tax-tab').forEach(tab => {
                tab.classList.remove('active');
            });
            
            if (type === 'PIT') {
                document.querySelectorAll('.tax-tab')[0].classList.add('active');
                document.getElementById('pit-form').classList.remove('hidden');
                document.getElementById('cit-form').classList.add('hidden');
            } else {
                document.querySelectorAll('.tax-tab')[1].classList.add('active');
                document.getElementById('pit-form').classList.add('hidden');
                document.getElementById('cit-form').classList.remove('hidden');
            }
            
            // Clear and hide results
            document.getElementById('no-results').style.display = 'block';
            document.getElementById('pit-results').style.display = 'none';
            document.getElementById('cit-results').style.display = 'none';
        }
        
        function formatCurrency(amount) {
            return '₦' + parseFloat(amount).toLocaleString('en-NG', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            });
        }
        
        function getColorClass(value) {
            if (value > 0) return 'savings';
            if (value < 0) return 'increase';
            return '';
        }
        
        async function calculateTax() {
            // Show loading
            const calculateBtn = document.querySelector('.calculate-btn');
            const originalText = calculateBtn.innerHTML;
            calculateBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Calculating...';
            calculateBtn.disabled = true;
            
            try {
                // Build payload based on current tax type
                let payload = {};
                if (currentTaxType === 'PIT') {
                    payload = {
                        tax_type: 'PIT',
                        basic_salary: document.getElementById('basic_salary').value || 0,
                        housing_allowance: document.getElementById('housing_allowance').value || 0,
                        transport_allowance: document.getElementById('transport_allowance').value || 0,
                        other_allowances: document.getElementById('other_allowances').value || 0,
                        pension: document.getElementById('pension').value || 0,
                        nhf: document.getElementById('nhf').value || 0,
                        life_insurance: document.getElementById('life_insurance').value || 0,
                        capital_gains: document.getElementById('capital_gains').value || 0,
                        digital_assets: document.getElementById('digital_assets').value || 0
                    };
                } else {
                    payload = {
                        tax_type: 'CIT',
                        turnover: document.getElementById('turnover').value || 0,
                        profit: document.getElementById('profit').value || 0
                    };
                }
                
                // Make API call to Flask backend
                const response = await fetch("/calculate", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });
                
                const data = await response.json();
                
                // Hide "no results" message
                document.getElementById('no-results').style.display = 'none';
                
                if (currentTaxType === 'PIT') {
                    // Show PIT results
                    document.getElementById('pit-results').style.display = 'block';
                    document.getElementById('cit-results').style.display = 'none';
                    
                    // Populate NEW law results
                    const newLaw = data.new;
                    document.getElementById('new-gross-income').textContent = formatCurrency(newLaw.gross_income);
                    document.getElementById('new-housing-capped').textContent = formatCurrency(newLaw.housing_allowance_capped);
                    document.getElementById('new-cra').textContent = formatCurrency(newLaw.cra);
                    document.getElementById('new-taxable-income').textContent = formatCurrency(newLaw.taxable_income);
                    document.getElementById('new-annual-paye').textContent = formatCurrency(newLaw.annual_paye);
                    document.getElementById('new-cgt').textContent = formatCurrency(newLaw.capital_gains_tax);
                    document.getElementById('new-total-tax').textContent = formatCurrency(newLaw.total_tax);
                    document.getElementById('new-monthly-take-home').textContent = formatCurrency(newLaw.monthly_take_home);
                    document.getElementById('new-net-income').textContent = formatCurrency(newLaw.net_income);
                    
                    // Populate OLD law results
                    const oldLaw = data.old;
                    document.getElementById('old-gross-income').textContent = formatCurrency(oldLaw.gross_income);
                    document.getElementById('old-housing-capped').textContent = formatCurrency(oldLaw.housing_allowance_capped);
                    document.getElementById('old-cra').textContent = formatCurrency(oldLaw.cra);
                    document.getElementById('old-taxable-income').textContent = formatCurrency(oldLaw.taxable_income);
                    document.getElementById('old-annual-paye').textContent = formatCurrency(oldLaw.annual_paye);
                    document.getElementById('old-cgt').textContent = formatCurrency(oldLaw.capital_gains_tax);
                    document.getElementById('old-total-tax').textContent = formatCurrency(oldLaw.total_tax);
                    document.getElementById('old-monthly-take-home').textContent = formatCurrency(oldLaw.monthly_take_home);
                    document.getElementById('old-net-income').textContent = formatCurrency(oldLaw.net_income);
                    
                    // Populate comparison summary
                    const comparison = data.comparison;
                    document.getElementById('tax-difference').textContent = formatCurrency(comparison.tax_difference);
                    document.getElementById('tax-difference').className = 'summary-value ' + getColorClass(-comparison.tax_difference);
                    
                    document.getElementById('net-income-difference').textContent = formatCurrency(comparison.net_income_difference);
                    document.getElementById('net-income-difference').className = 'summary-value ' + getColorClass(comparison.net_income_difference);
                    
                    document.getElementById('monthly-difference').textContent = formatCurrency(comparison.monthly_take_home_difference);
                    document.getElementById('monthly-difference').className = 'summary-value ' + getColorClass(comparison.monthly_take_home_difference);
                    
                    document.getElementById('recommendation').textContent = comparison.recommendation;
                    document.getElementById('recommendation').className = 'summary-value ' + (comparison.net_income_difference > 0 ? 'savings' : 'increase');
                    
                } else {
                    // Show CIT results
                    document.getElementById('pit-results').style.display = 'none';
                    document.getElementById('cit-results').style.display = 'block';
                    
                    // Populate NEW law results
                    const newLaw = data.new;
                    document.getElementById('new-company-size').textContent = newLaw.company_size;
                    document.getElementById('new-turnover').textContent = formatCurrency(newLaw.turnover);
                    document.getElementById('new-cit-rate').textContent = newLaw.cit_rate + '%';
                    document.getElementById('new-profit').textContent = formatCurrency(newLaw.profit);
                    document.getElementById('new-cit-payable').textContent = formatCurrency(newLaw.cit_payable);
                    document.getElementById('new-monthly-net-profit').textContent = formatCurrency(newLaw.monthly_net_profit);
                    document.getElementById('new-net-profit').textContent = formatCurrency(newLaw.net_profit);
                    
                    // Populate OLD law results
                    const oldLaw = data.old;
                    document.getElementById('old-company-size').textContent = oldLaw.company_size;
                    document.getElementById('old-turnover').textContent = formatCurrency(oldLaw.turnover);
                    document.getElementById('old-cit-rate').textContent = oldLaw.cit_rate + '%';
                    document.getElementById('old-profit').textContent = formatCurrency(oldLaw.profit);
                    document.getElementById('old-cit-payable').textContent = formatCurrency(oldLaw.cit_payable);
                    document.getElementById('old-monthly-net-profit').textContent = formatCurrency(oldLaw.monthly_net_profit);
                    document.getElementById('old-net-profit').textContent = formatCurrency(oldLaw.net_profit);
                    
                    // Populate comparison summary
                    const comparison = data.comparison;
                    document.getElementById('cit-tax-difference').textContent = formatCurrency(comparison.tax_difference);
                    document.getElementById('cit-tax-difference').className = 'summary-value ' + getColorClass(-comparison.tax_difference);
                    
                    document.getElementById('cit-net-profit-difference').textContent = formatCurrency(comparison.net_profit_difference);
                    document.getElementById('cit-net-profit-difference').className = 'summary-value ' + getColorClass(comparison.net_profit_difference);
                    
                    document.getElementById('cit-monthly-difference').textContent = formatCurrency(comparison.monthly_profit_difference);
                    document.getElementById('cit-monthly-difference').className = 'summary-value ' + getColorClass(comparison.monthly_profit_difference);
                    
                    document.getElementById('cit-recommendation').textContent = comparison.recommendation;
                    document.getElementById('cit-recommendation').className = 'summary-value ' + (comparison.net_profit_difference > 0 ? 'savings' : 'increase');
                }
                
            } catch (error) {
                alert('Error calculating tax. Please try again.');
                console.error(error);
            } finally {
                // Restore button
                calculateBtn.innerHTML = originalText;
                calculateBtn.disabled = false;
            }
        }
        
        // Add tooltip functionality
        document.addEventListener('DOMContentLoaded', function() {
            const tooltips = document.querySelectorAll('.tooltip-icon');
            tooltips.forEach(tooltip => {
                tooltip.addEventListener('mouseenter', function(e) {
                    const title = this.getAttribute('title');
                    if (title) {
                        // Remove existing tooltip if any
                        const existingTooltip = document.querySelector('.custom-tooltip');
                        if (existingTooltip) existingTooltip.remove();
                        
                        // Create new tooltip
                        const tooltipEl = document.createElement('div');
                        tooltipEl.className = 'custom-tooltip';
                        tooltipEl.textContent = title;
                        tooltipEl.style.position = 'absolute';
                        tooltipEl.style.background = '#2d3748';
                        tooltipEl.style.color = 'white';
                        tooltipEl.style.padding = '8px 12px';
                        tooltipEl.style.borderRadius = '4px';
                        tooltipEl.style.fontSize = '0.85rem';
                        tooltipEl.style.zIndex = '1000';
                        tooltipEl.style.maxWidth = '250px';
                        tooltipEl.style.boxShadow = '0 3px 10px rgba(0,0,0,0.2)';
                        
                        document.body.appendChild(tooltipEl);
                        
                        // Position tooltip
                        const rect = this.getBoundingClientRect();
                        tooltipEl.style.left = (rect.left + window.scrollX) + 'px';
                        tooltipEl.style.top = (rect.top + window.scrollY - tooltipEl.offsetHeight - 10) + 'px';
                        
                        // Remove title to prevent default tooltip
                        this.removeAttribute('title');
                    }
                });
                
                tooltip.addEventListener('mouseleave', function() {
                    const tooltipEl = document.querySelector('.custom-tooltip');
                    if (tooltipEl) tooltipEl.remove();
                });
            });
        });
    </script>
</body>
</html>'''

# -------------------- RUN --------------------
if __name__ == "__main__":
    app.run(debug=True, port=5000)