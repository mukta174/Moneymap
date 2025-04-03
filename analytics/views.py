# analytics/views.py

import base64
import calendar
import io
from datetime import datetime, date, timedelta # Added timedelta
from collections import defaultdict
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
    threshold_percentage = 3; final_category_totals = defaultdict(float); other_total = 0.0
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