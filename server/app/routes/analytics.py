"""
Analytics routes for Expense Tracker API
Handles expense and income aggregation and analytics
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
import asyncpg
import logging
import csv
import io
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from decimal import Decimal
from pydantic import BaseModel, Field

from app.database import get_db
from app.models.pydantic_models import TransactionCategory, TransactionType
from app.deps.auth import get_optional_user, AuthenticatedUser

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# Pydantic models for analytics responses
class CategorySummary(BaseModel):
    """Summary for a specific category"""
    category: TransactionCategory
    total_amount: Decimal = Field(..., description="Total amount for this category")
    transaction_count: int = Field(..., description="Number of transactions in this category")
    average_amount: Decimal = Field(..., description="Average transaction amount")

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v)
        }

class AnalyticsSummary(BaseModel):
    """Complete analytics summary response"""
    total_inflow: Decimal = Field(..., description="Total income (credit transactions)")
    total_outflow: Decimal = Field(..., description="Total expenses (debit transactions)")
    balance: Decimal = Field(..., description="Net balance (inflow - outflow)")
    expense_categories: List[CategorySummary] = Field(..., description="Expense breakdown by category")
    income_categories: List[CategorySummary] = Field(..., description="Income breakdown by category")
    period_start: Optional[datetime] = Field(None, description="Start date of analysis period")
    period_end: Optional[datetime] = Field(None, description="End date of analysis period")
    total_transactions: int = Field(..., description="Total number of transactions analyzed")

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v),
            datetime: lambda v: v.isoformat()
        }

class MonthlyData(BaseModel):
    """Monthly financial data"""
    month: str = Field(..., description="Month in YYYY-MM format")
    month_name: str = Field(..., description="Human readable month name")
    total_inflow: Decimal = Field(..., description="Total income for the month")
    total_outflow: Decimal = Field(..., description="Total expenses for the month")
    net_balance: Decimal = Field(..., description="Net balance (inflow - outflow)")
    inflow_categories: Dict[str, Decimal] = Field(..., description="Breakdown of inflow by category")
    outflow_categories: Dict[str, Decimal] = Field(..., description="Breakdown of outflow by category")
    transaction_count: int = Field(..., description="Total number of transactions")

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v)
        }

class TimeSeriesAnalytics(BaseModel):
    """Time series analytics response for the last 12 months"""
    monthly_data: List[MonthlyData] = Field(..., description="Monthly financial data for last 12 months")
    total_period_inflow: Decimal = Field(..., description="Total inflow across all months")
    total_period_outflow: Decimal = Field(..., description="Total outflow across all months")
    total_period_balance: Decimal = Field(..., description="Net balance across all months")
    analysis_period: str = Field(..., description="Analysis period description")

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v)
        }

@router.get("/summary", response_model=AnalyticsSummary)
async def get_analytics_summary(
    db: asyncpg.Connection = Depends(get_db),
    user: Optional[AuthenticatedUser] = Depends(get_optional_user),
    account_id: Optional[str] = Query(None, description="Filter by specific account"),
    from_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)")
):
    """
    Get analytics summary aggregating expenses and income by category.
    Returns total amounts per category, total inflow, total outflow, and balance.
    """
    user_id = user.id if user else None
    logger.info(f"📊 Analytics summary requested for user: {user_id}")

    # Parse date parameters
    period_start = None
    period_end = None

    try:
        if from_date:
            period_start = datetime.fromisoformat(from_date)
        if to_date:
            period_end = datetime.fromisoformat(to_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}. Use YYYY-MM-DD format.")

    if not db:
        # Mock data for development mode
        logger.info("📊 Development mode: returning mock analytics data")
        return AnalyticsSummary(
            total_inflow=Decimal("50000.00"),
            total_outflow=Decimal("35000.00"),
            balance=Decimal("15000.00"),
            expense_categories=[
                CategorySummary(
                    category=TransactionCategory.FOOD,
                    total_amount=Decimal("8000.00"),
                    transaction_count=45,
                    average_amount=Decimal("177.78")
                ),
                CategorySummary(
                    category=TransactionCategory.TRANSPORT,
                    total_amount=Decimal("5000.00"),
                    transaction_count=20,
                    average_amount=Decimal("250.00")
                )
            ],
            income_categories=[
                CategorySummary(
                    category=TransactionCategory.SALARY,
                    total_amount=Decimal("50000.00"),
                    transaction_count=2,
                    average_amount=Decimal("25000.00")
                )
            ],
            total_transactions=67
        )

    try:
        # Build dynamic WHERE clause
        where_conditions = ["1=1"]
        params = []
        param_count = 0

        if user_id:
            param_count += 1
            where_conditions.append(f"user_id = ${param_count}")
            params.append(user_id)

        if account_id:
            param_count += 1
            where_conditions.append(f"account_id = ${param_count}")
            params.append(account_id)

        if period_start:
            param_count += 1
            where_conditions.append(f"ts >= ${param_count}")
            params.append(period_start)

        if period_end:
            param_count += 1
            where_conditions.append(f"ts <= ${param_count}")
            params.append(period_end)

        where_clause = " AND ".join(where_conditions)

        # Query for category-wise breakdown
        category_query = f"""
            SELECT 
                type,
                category,
                SUM(amount) as total_amount,
                COUNT(*) as transaction_count,
                AVG(amount) as average_amount
            FROM transactions 
            WHERE {where_clause} AND category IS NOT NULL
            GROUP BY type, category
            ORDER BY type, total_amount DESC
        """

        # Query for overall totals
        totals_query = f"""
            SELECT 
                type,
                SUM(amount) as total_amount,
                COUNT(*) as transaction_count
            FROM transactions 
            WHERE {where_clause}
            GROUP BY type
        """

        # Execute queries
        category_rows = await db.fetch(category_query, *params)
        totals_rows = await db.fetch(totals_query, *params)

        # Process results
        total_inflow = Decimal("0.00")
        total_outflow = Decimal("0.00")
        total_transactions = 0
        expense_categories = []
        income_categories = []

        # Process totals
        for row in totals_rows:
            if row['type'] == 'credit':
                total_inflow = row['total_amount']
                total_transactions += row['transaction_count']
            elif row['type'] == 'debit':
                total_outflow = row['total_amount']
                total_transactions += row['transaction_count']

        # Process category breakdown
        for row in category_rows:
            category_summary = CategorySummary(
                category=TransactionCategory(row['category']),
                total_amount=row['total_amount'],
                transaction_count=row['transaction_count'],
                average_amount=row['average_amount']
            )

            if row['type'] == 'debit':
                expense_categories.append(category_summary)
            elif row['type'] == 'credit':
                income_categories.append(category_summary)

        balance = total_inflow - total_outflow

        logger.info(f"📊 Analytics processed: {total_transactions} transactions, Balance: {balance}")

        return AnalyticsSummary(
            total_inflow=total_inflow,
            total_outflow=total_outflow,
            balance=balance,
            expense_categories=expense_categories,
            income_categories=income_categories,
            period_start=period_start,
            period_end=period_end,
            total_transactions=total_transactions
        )

    except Exception as e:
        logger.error(f"❌ Analytics query failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate analytics: {str(e)}")

@router.get("/categories")
async def get_category_analytics(
    db: asyncpg.Connection = Depends(get_db),
    user: Optional[AuthenticatedUser] = Depends(get_optional_user),
    transaction_type: Optional[TransactionType] = Query(None, description="Filter by transaction type"),
    account_id: Optional[str] = Query(None, description="Filter by specific account"),
    from_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)")
):
    """
    Get detailed category-wise analytics
    """
    user_id = user.id if user else None
    logger.info(f"📈 Category analytics requested for user: {user_id}")

    # Parse date parameters
    period_start = None
    period_end = None

    try:
        if from_date:
            period_start = datetime.fromisoformat(from_date)
        if to_date:
            period_end = datetime.fromisoformat(to_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}. Use YYYY-MM-DD format.")

    if not db:
        # Mock response for development mode
        return {"message": "Category analytics - development mode"}

    try:
        # Build dynamic WHERE clause
        where_conditions = ["1=1", "category IS NOT NULL"]
        params = []
        param_count = 0

        if user_id:
            param_count += 1
            where_conditions.append(f"user_id = ${param_count}")
            params.append(user_id)

        if account_id:
            param_count += 1
            where_conditions.append(f"account_id = ${param_count}")
            params.append(account_id)

        if transaction_type:
            param_count += 1
            where_conditions.append(f"type = ${param_count}")
            params.append(transaction_type.value)

        if period_start:
            param_count += 1
            where_conditions.append(f"ts >= ${param_count}")
            params.append(period_start)

        if period_end:
            param_count += 1
            where_conditions.append(f"ts <= ${param_count}")
            params.append(period_end)

        where_clause = " AND ".join(where_conditions)

        # Detailed category query
        query = f"""
            SELECT 
                category,
                type,
                SUM(amount) as total_amount,
                COUNT(*) as transaction_count,
                AVG(amount) as average_amount,
                MIN(amount) as min_amount,
                MAX(amount) as max_amount,
                DATE_TRUNC('month', ts) as month
            FROM transactions 
            WHERE {where_clause}
            GROUP BY category, type, DATE_TRUNC('month', ts)
            ORDER BY category, month DESC
        """

        rows = await db.fetch(query, *params)

        # Group results by category
        categories = {}
        for row in rows:
            category = row['category']
            if category not in categories:
                categories[category] = {
                    'category': category,
                    'type': row['type'],
                    'total_amount': float(row['total_amount']),
                    'transaction_count': row['transaction_count'],
                    'average_amount': float(row['average_amount']),
                    'min_amount': float(row['min_amount']),
                    'max_amount': float(row['max_amount']),
                    'monthly_breakdown': []
                }

            categories[category]['monthly_breakdown'].append({
                'month': row['month'].isoformat(),
                'amount': float(row['total_amount']),
                'count': row['transaction_count']
            })

        return {
            'categories': list(categories.values()),
            'period_start': period_start.isoformat() if period_start else None,
            'period_end': period_end.isoformat() if period_end else None,
            'total_categories': len(categories)
        }

    except Exception as e:
        logger.error(f"❌ Category analytics query failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate category analytics: {str(e)}")

@router.get("/timeseries", response_model=TimeSeriesAnalytics)
async def get_timeseries_analytics(
    db: asyncpg.Connection = Depends(get_db),
    user: Optional[AuthenticatedUser] = Depends(get_optional_user),
    account_id: Optional[str] = Query(None, description="Filter by specific account"),
    months: int = Query(12, ge=1, le=24, description="Number of months to analyze (1-24)")
):
    """
    Get time-series analytics showing monthly inflows and outflows for the specified period.

    Inflows include: salary, investment, other credit transactions
    Outflows include: shopping, bills, transport, food, entertainment, healthcare, education
    """
    user_id = user.id if user else None
    logger.info(f"📈 Time-series analytics requested for user: {user_id}, months: {months}")

    # Calculate the start date (months ago from now)
    end_date = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    start_date = end_date - timedelta(days=30 * months)

    # Define inflow and outflow categories
    inflow_categories = {'salary', 'investment'}
    outflow_categories = {'shopping', 'bills', 'transport', 'food', 'entertainment', 'healthcare', 'education', 'other'}

    if not db:
        # Mock data for development mode
        logger.info("📈 Development mode: returning mock time-series data")
        mock_monthly_data = []

        for i in range(months):
            month_date = end_date - timedelta(days=30 * (months - 1 - i))
            month_str = month_date.strftime("%Y-%m")
            month_name = month_date.strftime("%B %Y")

            # Generate realistic mock data
            inflow = Decimal(str(45000 + (i * 1000)))  # Slightly increasing salary
            outflow = Decimal(str(30000 + (i * 500)))   # Slightly increasing expenses

            mock_monthly_data.append(MonthlyData(
                month=month_str,
                month_name=month_name,
                total_inflow=inflow,
                total_outflow=outflow,
                net_balance=inflow - outflow,
                inflow_categories={"salary": float(inflow)},
                outflow_categories={
                    "food": float(outflow * Decimal("0.3")),
                    "shopping": float(outflow * Decimal("0.25")),
                    "bills": float(outflow * Decimal("0.2")),
                    "transport": float(outflow * Decimal("0.15")),
                    "entertainment": float(outflow * Decimal("0.1"))
                },
                transaction_count=45
            ))

        total_inflow = sum(md.total_inflow for md in mock_monthly_data)
        total_outflow = sum(md.total_outflow for md in mock_monthly_data)

        return TimeSeriesAnalytics(
            monthly_data=mock_monthly_data,
            total_period_inflow=total_inflow,
            total_period_outflow=total_outflow,
            total_period_balance=total_inflow - total_outflow,
            analysis_period=f"Last {months} months"
        )

    try:
        # Build dynamic WHERE clause
        where_conditions = ["ts >= $1 AND ts < $2"]
        params = [start_date, end_date]
        param_count = 2

        if user_id:
            param_count += 1
            where_conditions.append(f"user_id = ${param_count}")
            params.append(user_id)

        if account_id:
            param_count += 1
            where_conditions.append(f"account_id = ${param_count}")
            params.append(account_id)

        where_clause = " AND ".join(where_conditions)

        # Query for monthly aggregated data
        query = f"""
            SELECT 
                DATE_TRUNC('month', ts) as month,
                type,
                category,
                SUM(amount) as total_amount,
                COUNT(*) as transaction_count
            FROM transactions 
            WHERE {where_clause} AND category IS NOT NULL
            GROUP BY DATE_TRUNC('month', ts), type, category
            ORDER BY month DESC, type, category
        """

        rows = await db.fetch(query, *params)

        # Process results into monthly data structure
        monthly_data_dict = {}

        for row in rows:
            month_key = row['month'].strftime("%Y-%m")

            if month_key not in monthly_data_dict:
                monthly_data_dict[month_key] = {
                    'month': month_key,
                    'month_name': row['month'].strftime("%B %Y"),
                    'total_inflow': Decimal('0.00'),
                    'total_outflow': Decimal('0.00'),
                    'inflow_categories': {},
                    'outflow_categories': {},
                    'transaction_count': 0
                }

            category = row['category']
            amount = row['total_amount']
            tx_type = row['type']

            monthly_data_dict[month_key]['transaction_count'] += row['transaction_count']

            # Categorize as inflow or outflow based on transaction type and category
            if tx_type == 'credit' or category in inflow_categories:
                monthly_data_dict[month_key]['total_inflow'] += amount
                monthly_data_dict[month_key]['inflow_categories'][category] = float(amount)
            else:
                monthly_data_dict[month_key]['total_outflow'] += amount
                monthly_data_dict[month_key]['outflow_categories'][category] = float(amount)

        # Convert to list and calculate net balance
        monthly_data_list = []
        total_period_inflow = Decimal('0.00')
        total_period_outflow = Decimal('0.00')

        # Sort by month (most recent first)
        for month_key in sorted(monthly_data_dict.keys(), reverse=True):
            data = monthly_data_dict[month_key]
            net_balance = data['total_inflow'] - data['total_outflow']

            monthly_data_list.append(MonthlyData(
                month=data['month'],
                month_name=data['month_name'],
                total_inflow=data['total_inflow'],
                total_outflow=data['total_outflow'],
                net_balance=net_balance,
                inflow_categories=data['inflow_categories'],
                outflow_categories=data['outflow_categories'],
                transaction_count=data['transaction_count']
            ))

            total_period_inflow += data['total_inflow']
            total_period_outflow += data['total_outflow']

        logger.info(f"📈 Time-series processed: {len(monthly_data_list)} months, Total Balance: {total_period_inflow - total_period_outflow}")

        return TimeSeriesAnalytics(
            monthly_data=monthly_data_list,
            total_period_inflow=total_period_inflow,
            total_period_outflow=total_period_outflow,
            total_period_balance=total_period_inflow - total_period_outflow,
            analysis_period=f"Last {months} months ({start_date.strftime('%Y-%m')} to {end_date.strftime('%Y-%m')})"
        )

    except Exception as e:
        logger.error(f"❌ Time-series analytics query failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate time-series analytics: {str(e)}")

@router.get("/export")
async def export_transactions_csv(
    db: asyncpg.Connection = Depends(get_db),
    user: Optional[AuthenticatedUser] = Depends(get_optional_user),
    account_id: Optional[str] = Query(None, description="Filter by specific account"),
    from_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    format: str = Query("csv", description="Export format (csv only for now)")
):
    """
    Export transactions as CSV file for a given date range.

    Returns a CSV file with columns:
    - Date: Transaction date
    - Merchant: Merchant/description
    - Category: Transaction category
    - Amount: Transaction amount
    - Type: inflow (credit) or outflow (debit)
    """
    user_id = user.id if user else None
    logger.info(f"📊 CSV export requested for user: {user_id}")

    # Parse date parameters
    period_start = None
    period_end = None

    try:
        if from_date:
            period_start = datetime.fromisoformat(from_date)
        if to_date:
            period_end = datetime.fromisoformat(to_date)

        # Default to last 30 days if no dates provided
        if not period_start and not period_end:
            period_end = datetime.utcnow()
            period_start = period_end - timedelta(days=30)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}. Use YYYY-MM-DD format.")

    if not db:
        # Mock data for development mode
        logger.info("📊 Development mode: returning mock CSV data")
        mock_data = [
            ["2024-01-15", "Starbucks Coffee", "food", "450.00", "outflow"],
            ["2024-01-16", "Uber Ride", "transport", "280.00", "outflow"],
            ["2024-01-20", "Salary Credit", "salary", "50000.00", "inflow"],
            ["2024-01-22", "Amazon Purchase", "shopping", "1250.00", "outflow"],
            ["2024-01-25", "Restaurant Bill", "food", "890.00", "outflow"]
        ]

        # Create CSV content
        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow(["Date", "Merchant", "Category", "Amount", "Type"])

        # Write data
        writer.writerows(mock_data)

        # Get CSV content
        csv_content = output.getvalue()
        output.close()

        # Create response
        response = StreamingResponse(
            io.StringIO(csv_content),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=transactions_export.csv"}
        )
        return response

    try:
        # Build dynamic WHERE clause
        where_conditions = ["1=1"]
        params = []
        param_count = 0

        if user_id:
            param_count += 1
            where_conditions.append(f"user_id = ${param_count}")
            params.append(user_id)

        if account_id:
            param_count += 1
            where_conditions.append(f"account_id = ${param_count}")
            params.append(account_id)

        if period_start:
            param_count += 1
            where_conditions.append(f"ts >= ${param_count}")
            params.append(period_start)

        if period_end:
            param_count += 1
            where_conditions.append(f"ts <= ${param_count}")
            params.append(period_end)

        where_clause = " AND ".join(where_conditions)

        # Query for transactions
        query = f"""
            SELECT 
                DATE(ts) as transaction_date,
                COALESCE(merchant, raw_desc, 'Unknown') as merchant,
                COALESCE(category::text, 'other') as category,
                amount,
                type::text as transaction_type
            FROM transactions 
            WHERE {where_clause}
            ORDER BY ts DESC
        """

        rows = await db.fetch(query, *params)

        # Create CSV content
        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow(["Date", "Merchant", "Category", "Amount", "Type"])

        # Write data rows
        for row in rows:
            # Convert transaction type from database enum to user-friendly labels
            transaction_type = 'inflow' if row['transaction_type'] == 'credit' else 'outflow'

            writer.writerow([
                row['transaction_date'].strftime('%Y-%m-%d'),
                row['merchant'],
                row['category'],
                f"{float(row['amount']):.2f}",
                transaction_type
            ])

        # Get CSV content
        csv_content = output.getvalue()
        output.close()

        logger.info(f"📊 CSV export generated: {len(rows)} transactions")

        # Generate filename with date range
        filename = f"transactions_export_{period_start.strftime('%Y%m%d')}_{period_end.strftime('%Y%m%d')}.csv"

        # Create streaming response
        def iter_csv():
            yield csv_content

        return StreamingResponse(
            iter(csv_content.split('\n').__iter__()),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        logger.error(f"❌ CSV export failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to export transactions: {str(e)}")
