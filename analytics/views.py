# analytics/views.py

import base64
import calendar
import io
from datetime import datetime, date, timedelta # Added timedelta
from collections import defaultdict
from urllib import response
import numpy as np

# Set Matplotlib backend BEFORE importing pyplot
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.dates as mdates # Added for date formatting on axis

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from emailparser.models import StoredTransaction
import csv
from django.http import HttpResponse, HttpResponseServerError
from django.template.loader import render_to_string
from django.utils.text import slugify

from weasyprint import HTML, CSS
from django.conf import settings
import os

@login_required
def analytics_dashboard(request):
    today = date.today()
    current_year = today.year
    current_month = today.month
    month_name = today.strftime('%B')
    _, num_days = calendar.monthrange(current_year, current_month)

    # --- Define Time Period for Monthly Comparison (e.g., last 6 months) ---
    # Calculate the first day of the month 5 months ago (total 6 months including current)
    months_to_compare = 6
    first_month_date = (today.replace(day=1) - timedelta(days=1)).replace(day=1) # Go to start of previous month
    for _ in range(months_to_compare - 2): # Go back further months
        first_month_date = (first_month_date - timedelta(days=1)).replace(day=1)

    print(f"DEBUG (Dashboard): Comparing monthly spending from {first_month_date.strftime('%Y-%m')}")

    # --- Initialize Data Structures ---
    # For Bar Chart (Current Month Daily)
    daily_totals_current_month = defaultdict(float)
    # For Donut Chart (Current Month Categories)
    category_totals_current_month = defaultdict(float)
    total_spending_current_month = 0.0
    # For Area Chart (Monthly Totals - Historical)
    monthly_spending_totals = defaultdict(float) # Key: (year, month) tuple

    processed_txns_count = 0
    parse_errors = []

    # --- Fetch Data ONCE (Consider fetching only data since first_month_date for optimization later) ---
    user_stored_transactions = StoredTransaction.objects.filter(
        user=request.user,
        # Optimization: Optionally filter by date here if StoredTransaction has a parsed date field
        # fetched_date__gte=first_month_date # Example if using fetched_date as a proxy
    ).order_by('fetched_date') # Or order by a parsed date field if available
    print(f"DEBUG (Dashboard): Found {user_stored_transactions.count()} stored transactions potentially in range for user {request.user.username}")

    # --- Process Data for ALL charts ---
    for stored_txn in user_stored_transactions:
        txn_data = stored_txn.transaction_data
        if not isinstance(txn_data, dict): continue

        try:
            # --- Date Parsing (Common) ---
            date_str = txn_data.get('date')
            if not date_str: continue
            parsed_date = None
            possible_formats = ["%d-%m-%y", "%d/%m/%y", "%Y-%m-%d %H:%M:%S"]
            for fmt in possible_formats:
                try:
                    dt_obj = datetime.strptime(date_str.split()[0], fmt)
                    parsed_date = dt_obj.date()
                    break
                except ValueError: continue
            if parsed_date is None: continue

            # --- Amount Parsing (Common) ---
            amount_val = txn_data.get('amount')
            if amount_val is None: continue
            try:
                amount = float(str(amount_val).replace(',', ''))
                if amount < 0: amount = abs(amount)
            except (ValueError, TypeError): continue

            # --- Filter & Process for CURRENT MONTH Charts (Bar & Donut) ---
            if parsed_date.year == current_year and parsed_date.month == current_month:
                processed_txns_count += 1
                # Daily Bar
                daily_totals_current_month[parsed_date.day] += amount
                # Category Donut
                category = txn_data.get('category', 'Uncategorized')
                if category in ['N/A (Model Error)', 'Categorization Error', 'Unknown Description', None, '']:
                     category = 'Uncategorized'
                category_totals_current_month[category] += amount
                total_spending_current_month += amount

            # --- Process for HISTORICAL Monthly Area Chart ---
            # Check if the transaction date is within our comparison period
            if parsed_date >= first_month_date:
                month_key = (parsed_date.year, parsed_date.month)
                monthly_spending_totals[month_key] += amount

        except Exception as e:
            parse_errors.append(f"Error processing StoredTxn ID {stored_txn.id} for dashboard: {e}")
            print(f"ERROR processing StoredTxn ID {stored_txn.id}: {e}")
            continue
    # --- End of Processing Loop ---

    print(f"DEBUG (Dashboard): Processed {processed_txns_count} transactions for {month_name} {current_year}.")
    print(f"DEBUG (Dashboard): Historical monthly totals: {dict(monthly_spending_totals)}")


    # ==============================================================
    # --- Generate Daily Spending Bar Chart (Current Month Only) ---
    # ==============================================================
    bar_chart_image = None
    daily_labels = [str(day) for day in range(1, num_days + 1)]
    # Use the data aggregated specifically for the current month
    daily_spending_data = [daily_totals_current_month.get(day, 0.0) for day in range(1, num_days + 1)]
    bar_has_data = any(s > 0 for s in daily_spending_data)

    if bar_has_data:
        try:
            # (Keep the exact Matplotlib code for the styled bar chart)
            # --- Define Bar Chart Colors ---
            fig_bg_color_bar = '#1F2A40'; axes_bg_color_bar = '#141B2D'; text_color_bar = '#e0e0e0'; grid_color_bar = '#525252'; bar_color = '#4cceac'
            fig_bar, ax_bar = plt.subplots(figsize=(12, 5.5)); fig_bar.patch.set_facecolor(fig_bg_color_bar); ax_bar.set_facecolor(axes_bg_color_bar)
            bars = ax_bar.bar(daily_labels, daily_spending_data, color=bar_color)
            ax_bar.set_title(f"Daily Spending - {month_name} {current_year}", fontsize=14, fontweight='bold', color=text_color_bar, pad=20)
            ax_bar.set_xlabel("Day", fontsize=11, color=text_color_bar, labelpad=10); ax_bar.set_ylabel("Amount Spent (INR)", fontsize=11, color=text_color_bar, labelpad=10)
            ax_bar.tick_params(axis='x', colors=text_color_bar, labelsize=9); ax_bar.tick_params(axis='y', colors=text_color_bar, labelsize=9)
            ax_bar.spines['top'].set_visible(False); ax_bar.spines['right'].set_visible(False); ax_bar.spines['bottom'].set_color(grid_color_bar); ax_bar.spines['left'].set_color(grid_color_bar); ax_bar.spines['bottom'].set_linewidth(0.6); ax_bar.spines['left'].set_linewidth(0.6)
            ax_bar.yaxis.grid(True, linestyle='--', linewidth=0.5, color=grid_color_bar, alpha=0.7); ax_bar.xaxis.grid(False)
            formatter_bar = mticker.FormatStrFormatter('₹%.0f'); ax_bar.yaxis.set_major_formatter(formatter_bar)
            ax_bar.set_ylim(bottom=0, top=max(daily_spending_data) * 1.15 if daily_spending_data else 10)
            for bar in bars: # Add data labels
                yval = bar.get_height();
                if yval > 0: plt.text(bar.get_x() + bar.get_width()/2.0, yval, f'₹{yval:.0f}', va='bottom', ha='center', fontsize=8, color=text_color_bar, alpha=0.9)
            plt.tight_layout(pad=1.5)
            buffer_bar = io.BytesIO(); plt.savefig(buffer_bar, format='png', dpi=110, facecolor=fig_bar.get_facecolor()); buffer_bar.seek(0)
            image_png_bar = buffer_bar.getvalue(); buffer_bar.close(); graphic_bar = base64.b64encode(image_png_bar); bar_chart_image = graphic_bar.decode('utf-8')
            plt.close(fig_bar); print("DEBUG (Dashboard): Bar chart generated.")
        except Exception as e: print(f"ERROR generating bar chart: {e}"); parse_errors.append(f"Failed to generate daily bar chart: {e}")

    # ===================================================================
    # --- Generate Category Spending Donut Chart (Current Month Only) ---
    # ===================================================================
    donut_chart_image = None
    # Group small categories logic (using current month category data)
    threshold_percentage = 0; final_category_totals = defaultdict(float); other_total = 0.0
    if total_spending_current_month > 0:
        for category, amount in category_totals_current_month.items():
            percentage = (amount / total_spending_current_month) * 100
            if percentage < threshold_percentage and category != 'Uncategorized': other_total += amount
            else: final_category_totals[category] = amount
    if other_total > 0: final_category_totals['Other'] = other_total
    # Sort categories (using current month data)
    sorted_categories = sorted(final_category_totals.items(), key=lambda item: item[1], reverse=True)
    categories = [item[0] for item in sorted_categories]
    spending_by_category = [item[1] for item in sorted_categories]
    donut_has_data = bool(spending_by_category)

    if donut_has_data:
        try:
            # (Keep the exact Matplotlib code for the styled donut chart)
            # --- Define Donut Chart Colors ---
            fig_bg_color_donut = '#1F2A40'; axes_bg_color_donut = '#141B2D'; text_color_donut = '#e0e0e0'; wedge_edge_color = fig_bg_color_donut; wedge_edge_width = 1.5
            custom_colors = ['#4cceac', '#6870fa', '#f47c7c', '#f7b731','#5aa4ec', '#dea1fc', '#90ee90', '#ffdead', '#b0c4de']
            num_colors_defined = len(custom_colors); plot_colors = [custom_colors[i % num_colors_defined] for i in range(len(categories))]
            # --- Create Figure and Axes ---
            fig_donut, ax_donut = plt.subplots(figsize=(8, 8), subplot_kw=dict(aspect="equal")); fig_donut.patch.set_facecolor(fig_bg_color_donut)
            # --- Plot the Donut Chart ---
            wedges, texts, autotexts = ax_donut.pie(spending_by_category, labels=None, colors=plot_colors, autopct='%1.0f%%', startangle=90, pctdistance=0.82, wedgeprops=dict(width=0.35, edgecolor=wedge_edge_color, linewidth=wedge_edge_width))
            # --- Style Percentage Text ---
            plt.setp(autotexts, size=7, weight="bold", color=text_color_donut, alpha=0.9)
            # --- Add Total Spending Text in the Center ---
            center_text = f'Total\n₹{total_spending_current_month:,.0f}'; ax_donut.text(0, 0, center_text, ha='center', va='center', fontsize=16, fontweight='bold', color=text_color_donut)
            # --- Add Legend ---
            legend_labels = [f"{cat}: ₹{amt:,.0f}" for cat, amt in sorted_categories]
            ax_donut.legend(wedges, legend_labels, title="Categories", title_fontsize='10', loc="center left", bbox_to_anchor=(1.05, 0.5), fontsize='9', labelcolor=text_color_donut, facecolor=axes_bg_color_donut, edgecolor=fig_bg_color_donut, frameon=False)
            # --- Title ---
            ax_donut.set_title(f"Spending by Category - {month_name} {current_year}", fontsize=14, fontweight='bold', color=text_color_donut, pad=30)
            # --- Save plot ---
            buffer_donut = io.BytesIO(); plt.savefig(buffer_donut, format='png', dpi=110, facecolor=fig_donut.get_facecolor(), bbox_inches='tight'); buffer_donut.seek(0)
            image_png_donut = buffer_donut.getvalue(); buffer_donut.close(); graphic_donut = base64.b64encode(image_png_donut); donut_chart_image = graphic_donut.decode('utf-8')
            plt.close(fig_donut); print("DEBUG (Dashboard): Donut chart generated.")
        except Exception as e: print(f"ERROR generating donut chart: {e}"); parse_errors.append(f"Failed to generate category donut chart: {e}")

    # ======================================================
    # --- Generate Monthly Spending Comparison Area Chart ---
    # ======================================================
    area_chart_image = None
    month_labels_area = []
    monthly_totals_data_area = []
    area_has_data = False

    # Create date objects for labels and data lookups (last N months)
    temp_date = first_month_date
    while temp_date <= today.replace(day=1): # Loop through months in the period
        month_key = (temp_date.year, temp_date.month)
        # Format label as "Mon 'YY" e.g., "Jul '24"
        month_labels_area.append(temp_date.strftime("%b '%y"))
        # Get spending for this month (default to 0 if no transactions)
        monthly_totals_data_area.append(monthly_spending_totals.get(month_key, 0.0))

        # Move to the next month
        next_month_day1 = (temp_date.replace(day=28) + timedelta(days=4)).replace(day=1)
        temp_date = next_month_day1

    # Check if there's any data to plot in the area chart
    area_has_data = any(m > 0 for m in monthly_totals_data_area)
    print(f"DEBUG (Dashboard): Area chart labels: {month_labels_area}")
    print(f"DEBUG (Dashboard): Area chart data: {monthly_totals_data_area}")

    if area_has_data:
        try:
            # --- Define Area Chart Colors & Theme ---
            fig_bg_color_area = '#1F2A40'; axes_bg_color_area = '#141B2D'; text_color_area = '#e0e0e0'; grid_color_area = '#525252'
            # Use a different accent color for the area chart line/fill
            area_line_color = '#6870fa' # Purple accent
            area_fill_color = '#6870fa' # Same purple, but with alpha

            # Create Figure and Axes
            fig_area, ax_area = plt.subplots(figsize=(12, 5)) # Adjust size
            fig_area.patch.set_facecolor(fig_bg_color_area)
            ax_area.set_facecolor(axes_bg_color_area)

            # Plot the line
            ax_area.plot(month_labels_area, monthly_totals_data_area,
                         color=area_line_color, marker='o', markersize=4, linewidth=2, label="Monthly Spending")

            # Plot the filled area underneath
            ax_area.fill_between(month_labels_area, monthly_totals_data_area, 0,
                                 color=area_fill_color, alpha=0.3) # Use alpha for transparency

            # Titles and Labels
            ax_area.set_title(f"Monthly Spending Trend (Last {months_to_compare} Months)", fontsize=14, fontweight='bold', color=text_color_area, pad=20)
            # No X label needed if months are clear
            # ax_area.set_xlabel("Month", fontsize=11, color=text_color_area, labelpad=10)
            ax_area.set_ylabel("Total Spent (INR)", fontsize=11, color=text_color_area, labelpad=10)

            # Ticks and Spines (similar to bar chart)
            ax_area.tick_params(axis='x', colors=text_color_area, labelsize=9, rotation=0) # No rotation needed for few months
            ax_area.tick_params(axis='y', colors=text_color_area, labelsize=9)
            ax_area.spines['top'].set_visible(False); ax_area.spines['right'].set_visible(False)
            ax_area.spines['bottom'].set_color(grid_color_area); ax_area.spines['left'].set_color(grid_color_area)
            ax_area.spines['bottom'].set_linewidth(0.6); ax_area.spines['left'].set_linewidth(0.6)

            # Grid and Y-axis Formatting
            ax_area.yaxis.grid(True, linestyle='--', linewidth=0.5, color=grid_color_area, alpha=0.7)
            ax_area.xaxis.grid(False)
            formatter_area = mticker.FormatStrFormatter('₹%.0f')
            ax_area.yaxis.set_major_formatter(formatter_area)
            # Adjust Y limit based on monthly data
            ax_area.set_ylim(bottom=0, top=max(monthly_totals_data_area) * 1.15 if monthly_totals_data_area else 10)

            # Optional: Add data point values - can get cluttered on area charts
            # for i, txt in enumerate(monthly_totals_data_area):
            #     if txt > 0: ax_area.annotate(f'₹{txt:.0f}', (month_labels_area[i], monthly_totals_data_area[i]), textcoords="offset points", xytext=(0,5), ha='center', fontsize=7, color=text_color_area)

            # Final Layout Adjustment and Saving
            plt.tight_layout(pad=1.5)
            buffer_area = io.BytesIO()
            plt.savefig(buffer_area, format='png', dpi=110, facecolor=fig_area.get_facecolor())
            buffer_area.seek(0)
            image_png_area = buffer_area.getvalue()
            buffer_area.close()
            graphic_area = base64.b64encode(image_png_area)
            area_chart_image = graphic_area.decode('utf-8')
            plt.close(fig_area) # IMPORTANT: Close the figure
            print("DEBUG (Dashboard): Area chart generated.")
        except Exception as e:
            print(f"ERROR generating area chart: {e}")
            parse_errors.append(f"Failed to generate monthly spending area chart: {e}")


    # ========================================
    # --- Prepare FINAL Context for Template ---
    # ========================================
    context = {
        'bar_chart_image': bar_chart_image,
        'donut_chart_image': donut_chart_image,
        'area_chart_image': area_chart_image, # Add area chart image
        'current_month_year': f"{month_name} {current_year}",
        'bar_has_data': bar_has_data,
        'donut_has_data': donut_has_data,
        'area_has_data': area_has_data,       # Add area chart data flag
        'total_spending_current_month': total_spending_current_month, # Pass current month total
        'parse_errors': parse_errors,
    }

    # Render the single dashboard template with the prepared context
    return render(request, 'analytics/dashboard.html', context)


@login_required
def expense_report(request):
    """Generate a simplified, tabular expense report"""
    # --- Date parameter handling (as before) ---
    today = date.today()
    report_year = int(request.GET.get('year', today.year))
    report_month = int(request.GET.get('month', today.month))
    full_year = request.GET.get('full_year', 'false').lower() == 'true'

    if full_year:
        report_title = f"Annual Expenses Summary - {report_year}"
        report_period = f"January - December {report_year}"
        start_date = date(report_year, 1, 1)
        end_date = date(report_year, 12, 31)
    else:
        month_name = calendar.month_name[report_month]
        report_title = f"Monthly Expenses Summary - {month_name} {report_year}"
        report_period = f"{month_name} {report_year}"
        start_date = date(report_year, report_month, 1)
        _, last_day = calendar.monthrange(report_year, report_month)
        end_date = date(report_year, report_month, last_day)

    # --- Data structures (as before) ---
    category_totals = defaultdict(float)
    merchant_totals = defaultdict(float)
    monthly_totals = defaultdict(lambda: {'amount': 0.0, 'count': 0})
    weekly_totals = defaultdict(lambda: {'amount': 0.0, 'count': 0})
    day_of_week_totals = defaultdict(lambda: {'amount': 0.0, 'count': 0})
    total_spending = 0.0
    transaction_count = 0
    largest_transaction = {"amount": 0, "date": None, "merchant": None, "category": None}
    user_transactions = StoredTransaction.objects.filter(user=request.user)
    parse_errors = []
    processed_txns_for_csv = []

    # --- Processing loop (as refined before) ---
    for stored_txn in user_transactions:
        txn_data = stored_txn.transaction_data
        if not isinstance(txn_data, dict): continue

        try:
            # Date parsing
            date_str = txn_data.get('date')
            if not date_str: continue
            parsed_date = None
            possible_formats = ["%d-%m-%y", "%d/%m/%y", "%Y-%m-%d %H:%M:%S"]
            for fmt in possible_formats:
                try:
                    parsed_date = datetime.strptime(date_str.split()[0], fmt).date()
                    break
                except ValueError: continue
            if parsed_date is None: continue

            # Filter by time period
            if not (start_date <= parsed_date <= end_date): continue

            # Amount parsing
            amount_val = txn_data.get('amount')
            if amount_val is None: continue
            try:
                amount = float(str(amount_val).replace(',', ''))
                if amount < 0: amount = abs(amount)
            except (ValueError, TypeError): continue

            # Transaction passed filters
            transaction_count += 1
            total_spending += amount

            # Merchant and Category processing (using refined logic)
            merchant_raw = txn_data.get('merchant')
            description_raw = txn_data.get('description')
            category_raw = txn_data.get('category')
            merchant = 'Unknown'
            if merchant_raw and str(merchant_raw).strip() not in ['', 'N/A', 'n/a']:
                merchant = str(merchant_raw).strip()
            elif description_raw and str(description_raw).strip() not in ['', 'N/A', 'n/a']:
                 merchant = str(description_raw).strip()
            category = 'Uncategorized'
            if category_raw and str(category_raw).strip() not in ['', 'N/A (Model Error)', 'Categorization Error', 'Unknown Description']:
                 category = str(category_raw).strip()

            # Prepare data for CSV
            processed_txns_for_csv.append({
                'date': parsed_date, 'amount': amount, 'merchant': merchant,
                'category': category, 'description': description_raw or ''
            })

            # Accumulate totals
            category_totals[category] += amount
            merchant_totals[merchant] += amount
            day_of_week_totals[parsed_date.weekday()]['amount'] += amount
            day_of_week_totals[parsed_date.weekday()]['count'] += 1
            if full_year:
                 month_key = parsed_date.month
                 monthly_totals[month_key]['amount'] += amount
                 monthly_totals[month_key]['count'] += 1
                 week_number = parsed_date.isocalendar()[1]
                 weekly_totals[week_number]['amount'] += amount
                 weekly_totals[week_number]['count'] += 1

            # Track largest transaction
            if amount > largest_transaction["amount"]:
                largest_transaction = {
                    "amount": amount, "date": parsed_date,
                    "merchant": merchant, "category": category
                }
        except Exception as e:
            parse_errors.append(f"Error processing StoredTxn ID {stored_txn.id}: {e}")
            print(f"ERROR processing StoredTxn ID {stored_txn.id}: {e}")
            continue

    # --- Prepare Summaries with percentages/averages (as refined before) ---
    categories_summary_list = []
    for category, amount in category_totals.items():
        percentage = (amount / total_spending * 100) if total_spending > 0 else 0
        categories_summary_list.append({'name': category, 'amount': amount, 'percentage': percentage})
    sorted_categories = sorted(categories_summary_list, key=lambda x: x['amount'], reverse=True)

    sorted_merchants = sorted(merchant_totals.items(), key=lambda x: x[1], reverse=True)

    day_names = list(calendar.day_name)
    day_of_week_summary = []
    for i in range(7):
        data = day_of_week_totals[i]
        day_of_week_summary.append({
            'day_name': day_names[i], 'amount': data['amount'], 'count': data['count'],
            'average': data['amount'] / data['count'] if data['count'] > 0 else 0
        })

    monthly_summary = []
    if full_year:
        for i in range(1, 13):
            data = monthly_totals[i]
            monthly_summary.append({
                'month_name': calendar.month_name[i], 'month_num': i, 'amount': data['amount'],
                'count': data['count'], 'average': data['amount'] / data['count'] if data['count'] > 0 else 0
            })

    weekly_summary = []
    if full_year and weekly_totals:
        for week_num in sorted(weekly_totals.keys()):
             data = weekly_totals[week_num]
             weekly_summary.append({
                 'week_num': week_num, 'amount': data['amount'], 'count': data['count'],
                 'average': data['amount'] / data['count'] if data['count'] > 0 else 0
             })

    avg_transaction = total_spending / transaction_count if transaction_count > 0 else 0
    num_days_in_period = (end_date - start_date).days + 1
    avg_daily = total_spending / num_days_in_period if num_days_in_period > 0 else 0

    # --- Generate insights (as before) ---
    insights = []
    if sorted_categories:
       top_cat_data = sorted_categories[0]
       insights.append(f"Top spending category: '{top_cat_data['name']}' (₹{top_cat_data['amount']:,.2f}, {top_cat_data['percentage']:.1f}% of total).")
    if largest_transaction["date"]:
       insights.append(f"Largest transaction: ₹{largest_transaction['amount']:,.2f} at {largest_transaction['merchant']} ({largest_transaction['category']}) on {largest_transaction['date'].strftime('%d %b %Y')}.")
    # Add more insights if desired

    # --- Context for template (Tabular Focus) ---
    context = {
        'report_title': report_title,
        'report_period': report_period,
        'full_year': full_year,
        'year': report_year,
        'month': report_month if not full_year else None,
        'month_name': calendar.month_name[report_month] if not full_year else None,
        'total_spending': total_spending,
        'transaction_count': transaction_count,
        'avg_transaction': avg_transaction,
        'avg_daily': avg_daily,
        'largest_transaction': largest_transaction,
        'sorted_categories': sorted_categories,
        'sorted_merchants': sorted_merchants,
        'day_of_week_summary': day_of_week_summary,
        'monthly_summary': monthly_summary,
        'weekly_summary': weekly_summary,
        'insights': insights,
        'parse_errors': parse_errors,
        # Flag to indicate if PDF generation is enabled/functional
        'pdf_generation_enabled': True # Set to True only if you fix generate_pdf_report and its template
    }

    # --- Handle Download Requests ---
        # --- Handle Download Requests ---
    if request.method == 'GET':
        download_type = request.GET.get('download')
        if download_type == 'pdf':
            # Use .get for safety, defaulting to False if the key is missing
            if context.get('pdf_generation_enabled', False):
                 # ---- THIS IS THE FIX ----
                 # Call the actual PDF generation function
                 print(f"DEBUG (expense_report): Calling generate_pdf_report for {report_title}") # Add debug print
                 return generate_pdf_report(request, context)
                 # -------------------------
            else:
                # If PDF generation is explicitly disabled in context (though it's True now)
                logger.warning("PDF generation requested but pdf_generation_enabled is False in context.")
                return HttpResponse("PDF generation is currently disabled.", status=403) # 403 Forbidden is more appropriate
        elif download_type == 'csv':
            return generate_csv_report(request, processed_txns_for_csv, report_title)

    # Render the HTML report template (if not downloading)
    return render(request, 'analytics/expense_report.html', context)


# generate_csv_report function remains the same (as provided previously)
def generate_csv_report(request, transactions, report_title):
    response = HttpResponse(content_type='text/csv')
    filename = slugify(report_title) + '_transactions.csv'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(['Date', 'Amount', 'Category', 'Merchant', 'Original Description'])
    for txn in transactions:
        writer.writerow([
            txn['date'].strftime('%Y-%m-%d'), f"{txn['amount']:.2f}",
            txn['category'], txn['merchant'], txn['description']
        ])
    return response

# analytics/views.py (or wherever this function resides)

from django.http import HttpResponse, HttpResponseServerError
from django.template.loader import render_to_string
import logging
logger = logging.getLogger(__name__)

# analytics/views.py (Function definition)

def generate_pdf_report(request, context):
    """
    Generates a PDF version of the expense report using WeasyPrint.
    Requires WeasyPrint library and its dependencies to be installed,
    and a dedicated template 'analytics/pdf_report_template.html'.
    """
    print(">>> ENTERING generate_pdf_report") # DEBUG

    # 1. Check if WeasyPrint is installed
    try:
        from weasyprint import HTML, CSS
        print(">>> WeasyPrint imported") # DEBUG
    except ImportError:
        print("!!! WeasyPrint import FAILED") # DEBUG
        # logger.error("WeasyPrint library not found for PDF generation.") # Optional logging
        return HttpResponseServerError("PDF generation library (WeasyPrint) not installed. Please install it.")

    # 2. Render the HTML template specifically for PDF
    try:
        print(">>> Rendering PDF template: analytics/pdf_report_template.html") # DEBUG
        html_string = render_to_string('analytics/pdf_report_template.html', context)
        print(">>> PDF template rendered successfully") # DEBUG
    except Exception as e:
        print(f"!!! ERROR rendering PDF template: {e}") # DEBUG
        # logger.error(f"Error rendering PDF template 'analytics/pdf_report_template.html': {e}", exc_info=True) # Optional logging
        # Provide more specific error message if possible
        return HttpResponseServerError(f"Error rendering the PDF template: {e}. Check template existence and context variables.")

    # 3. Prepare the HTTP response object for PDF content
    response = HttpResponse(content_type='application/pdf')

    # 4. Generate a safe filename based on context
    try:
        is_full_year = context.get('full_year', False)
        year = context.get('year', 'YYYY') # Default if missing
        month_num = context.get('month', 0) # Default if missing

        if is_full_year:
            filename = f"expense_summary_{year}_annual.pdf"
        else:
            # Ensure month is formatted correctly if present
            filename = f"expense_summary_{year}_{month_num:02d}.pdf" if month_num else f"expense_summary_{year}_monthly.pdf"

        # Set the Content-Disposition header for download
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        print(f">>> Prepared response, filename: {filename}") # DEBUG
    except Exception as e:
        print(f"!!! ERROR preparing filename or response headers: {e}") # DEBUG
        # logger.error(f"Error setting up PDF response headers: {e}", exc_info=True) # Optional logging
        return HttpResponseServerError(f"Error preparing PDF download headers: {e}")

    # 5. Define CSS for the PDF (can be adjusted or removed if CSS is embedded in HTML)
    #    Keeping CSS embedded in the HTML template ('pdf_report_template.html') is often simpler.
    #    If you remove this css_string, also remove the stylesheets argument below.
    css_string = """
        /* --- PASTE YOUR PDF CSS RULES HERE OR KEEP THEM IN THE HTML TEMPLATE --- */
        /* Using the CSS from the example pdf_report_template.html: */
        @page { size: letter; margin: 0.75in; }
        body { font-family: Helvetica, Arial, sans-serif; font-size: 9pt; color: #333333; line-height: 1.4; }
        h1 { font-size: 18pt; color: #1a2035; text-align: center; margin-bottom: 5px; font-weight: bold; }
        h2 { font-size: 14pt; color: #1F2A40; border-bottom: 1px solid #cccccc; padding-bottom: 4px; margin-top: 25px; margin-bottom: 15px; font-weight: bold; page-break-before: auto; page-break-after: avoid; }
        h3 { font-size: 11pt; color: #333333; margin-top: 15px; margin-bottom: 8px; font-weight: bold; page-break-after: avoid; }
        p { margin-bottom: 10px; }
        .report-period { text-align: center; font-size: 11pt; color: #555555; margin-bottom: 25px; }
        .summary-item { margin-bottom: 8px; padding: 5px; border-bottom: 1px dotted #eee; page-break-inside: avoid; }
        .summary-label { display: block; font-size: 8pt; color: #555555; text-transform: uppercase; margin-bottom: 2px; }
        .summary-value { display: block; font-size: 11pt; font-weight: bold; }
        .summary-secondary { display: block; font-size: 8pt; color: #777777; }
        table { width: 100%; border-collapse: collapse; margin-bottom: 20px; page-break-inside: auto; }
        th, td { border: 1px solid #cccccc; padding: 6px 8px; text-align: left; vertical-align: top; font-size: 9pt; page-break-inside: avoid; }
        th { background-color: #eeeeee; font-weight: bold; color: #444444; }
        tbody tr:nth-child(even) { background-color: #f9f9f9; }
        .text-right { text-align: right; }
        .text-center { text-align: center; }
        .nowrap { white-space: nowrap; }
        .insights-list { list-style: disc; padding-left: 20px; margin-top: 0; }
        .insight-item { margin-bottom: 8px; }
        .no-data { text-align: center; font-style: italic; color: #777777; padding: 15px; }
        .error-message { color: #D8000C; background-color: #FFD2D2; border: 1px solid #D8000C; padding: 8px; margin-bottom: 10px; font-size: 9pt; border-radius: 3px; }
        .footer { text-align: center; margin-top: 30px; font-size: 8pt; color: #888; border-top: 1px solid #ccc; padding-top: 10px; }
        /* --- END OF PDF CSS RULES --- */
    """

    # 6. Generate the PDF using WeasyPrint
    try:
        print(">>> Creating WeasyPrint HTML object") # DEBUG
        # Pass the base_url to resolve relative paths for images/CSS if any are linked in the template
        html = HTML(string=html_string, base_url=request.build_absolute_uri('/'))

        print(">>> Generating PDF with write_pdf") # DEBUG
        # Write the PDF content directly to the HttpResponse object
        # If CSS is embedded in the template, you can potentially remove the stylesheets list:
        # html.write_pdf(response)
        html.write_pdf(response, stylesheets=[CSS(string=css_string)])

        print(">>> PDF generated successfully, returning response") # DEBUG
        # Return the response object containing the generated PDF
        return response

    except Exception as e:
        # Catch potential errors during PDF generation (e.g., invalid HTML/CSS)
        print(f"!!! ERROR during WeasyPrint write_pdf: {e}") # DEBUG
        # logger.error(f"Error generating PDF file using WeasyPrint: {e}", exc_info=True) # Optional logging
        return HttpResponseServerError(f"Failed to generate PDF document: {e}")