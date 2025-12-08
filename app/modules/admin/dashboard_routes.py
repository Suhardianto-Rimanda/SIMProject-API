from flask import jsonify
from sqlalchemy import func
from datetime import datetime, timedelta, date, time
from app.extensions import db
from app.models import Order, Ingredient, User
from app.decorators import admin_required
from . import admin_bp

@admin_bp.route('/dashboard', methods=['GET'])
@admin_required()
def admin_dashboard():
    # 1. Tentukan Rentang Waktu HARI INI (00:00:00 s/d 23:59:59)
    now = datetime.now()
    start_of_day = datetime.combine(now.date(), time.min)
    end_of_day = datetime.combine(now.date(), time.max)

    print(f"\n--- DEBUG ADMIN DASHBOARD ---")
    print(f"Cek Data dari: {start_of_day} s/d {end_of_day}")

    # =========================================================
    # 1. TARIK SEMUA DATA HARI INI (Tanpa Filter Status Dulu)
    # =========================================================
    todays_orders = Order.query.filter(
        Order.transaction_date >= start_of_day,
        Order.transaction_date <= end_of_day
    ).all()

    revenue_today = 0
    trx_count = 0

    # =========================================================
    # 2. HITUNG MANUAL DI PYTHON (Lebih Aman & Stabil)
    # =========================================================
    for order in todays_orders:
        # Debug: Lihat apa yang sebenarnya ada di database
        print(f"> Order: {order.invoice_no} | Status: {order.status} | Pay: {order.payment_method} | Total: {order.total_amount}")

        # LOGIKA FILTER:
        # 1. Status tidak boleh 'cancelled'
        # 2. Payment method tidak boleh 'pending' (harus lunas)
        
        is_valid_status = (order.status != 'cancelled')
        # Gunakan .lower() untuk mengatasi masalah 'Cash' vs 'cash'
        is_paid = (str(order.payment_method).lower() != 'pending')

        if is_valid_status and is_paid:
            revenue_today += float(order.total_amount)
            trx_count += 1

    print(f"Total Omset Valid: {revenue_today}")

    # 3. CEK STOK MENIPIS
    low_stock_count = Ingredient.query.filter(Ingredient.current_stock < 5).count()

    # 4. TOTAL STAFF
    staff_count = User.query.filter(User.role != 'admin').count()

    # 5. DATA GRAFIK 7 HARI TERAKHIR
    chart_dates = []
    chart_values = []
    
    for i in range(6, -1, -1):
        day_target = now.date() - timedelta(days=i)
        day_start = datetime.combine(day_target, time.min)
        day_end = datetime.combine(day_target, time.max)

        # Hitung per hari
        day_orders = Order.query.filter(
            Order.transaction_date >= day_start,
            Order.transaction_date <= day_end
        ).all()

        day_total = 0
        for o in day_orders:
            if o.status != 'cancelled' and str(o.payment_method).lower() != 'pending':
                day_total += float(o.total_amount)
        
        chart_dates.append(day_target.strftime('%d/%m'))
        chart_values.append(day_total)

    return jsonify({
        "summary": {
            "revenue_today": revenue_today,
            "trx_today": trx_count,
            "low_stock": low_stock_count,
            "staff_active": staff_count
        },
        "chart": {
            "labels": chart_dates,
            "series": chart_values
        },
        "menu": ["Manajemen User", "Master Bahan", "Master Resep", "Laporan Keuangan"]
    }), 200