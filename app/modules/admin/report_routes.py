from flask import request, jsonify
from sqlalchemy import func
from datetime import datetime, time
from app.extensions import db
from app.models import Ingredient, Order, OrderItem, OperationalExpense
from app.decorators import admin_required
from . import admin_bp

# =====================================================
# 1. LAPORAN STOK (Asset Value) - TIDAK ADA PERUBAHAN (SUDAH BENAR)
# =====================================================
@admin_bp.route('/reports/stock', methods=['GET'])
@admin_required()
def report_stock():
    items = Ingredient.query.all()
    output = []
    total_asset_value = 0
    
    for i in items:
        asset_value = float(i.current_stock) * float(i.avg_cost)
        total_asset_value += asset_value
        
        output.append({
            'name': i.name,
            'unit': i.unit,
            'current_stock': float(i.current_stock),
            'avg_cost': float(i.avg_cost),
            'total_value': asset_value
        })
        
    return jsonify({
        'title': 'Laporan Nilai Aset Stok',
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'total_asset_value': total_asset_value,
        'items': output
    }), 200

# =====================================================
# 2. LAPORAN PENJUALAN (Sales Recap) - LOGIC FIX (WIB)
# =====================================================
@admin_bp.route('/reports/sales', methods=['GET'])
@admin_required()
def report_sales():
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    query = db.session.query(
        func.date(Order.transaction_date).label('date'),
        func.count(Order.id).label('total_trx'),
        func.sum(Order.total_amount).label('total_revenue')
    )

    # 1. FILTER STATUS VALID (Hanya Lunas & Tidak Batal)
    query = query.filter(Order.status != 'cancelled')
    query = query.filter(Order.payment_method != 'pending')

    # 2. FILTER TANGGAL (WIB RANGE 00:00 - 23:59)
    # Ini kuncinya agar data hari ini terbaca
    if start_date_str and end_date_str:
        # Konversi string ke object Date
        start_date_obj = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date_obj = datetime.strptime(end_date_str, '%Y-%m-%d')
        
        # Buat Range Jam Lengkap (WIB)
        start_full = datetime.combine(start_date_obj, time.min) # 00:00:00
        end_full = datetime.combine(end_date_obj, time.max)     # 23:59:59
        
        # Filter berdasarkan kolom DateTime langsung (Lebih Akurat)
        query = query.filter(Order.transaction_date >= start_full)
        query = query.filter(Order.transaction_date <= end_full)
        
    # Grouping tetap by Date untuk grafik
    sales_data = query.group_by(func.date(Order.transaction_date)).all()
    
    output = []
    grand_total = 0
    
    for row in sales_data:
        grand_total += float(row.total_revenue)
        output.append({
            'date': row.date.strftime('%Y-%m-%d'),
            'total_transactions': row.total_trx,
            'revenue': float(row.total_revenue)
        })
        
    return jsonify({
        'title': 'Laporan Penjualan Harian',
        'period': f"{start_date_str} s/d {end_date_str}" if start_date_str else "Semua Waktu",
        'grand_total_revenue': grand_total,
        'daily_data': output
    }), 200

# =====================================================
# 3. LAPORAN LABA RUGI (Profit & Loss) - LOGIC FIX (WIB)
# =====================================================
@admin_bp.route('/reports/profit-loss', methods=['GET'])
@admin_required()
def report_profit_loss():
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    # 1. SETUP FILTER TANGGAL (WIB Range)
    start_full = None
    end_full = None
    start_d_obj = None # Untuk operational expense
    end_d_obj = None

    if start_date_str and end_date_str:
        start_d_obj = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_d_obj = datetime.strptime(end_date_str, '%Y-%m-%d')
        
        start_full = datetime.combine(start_d_obj, time.min) # 00:00:00
        end_full = datetime.combine(end_d_obj, time.max)     # 23:59:59

    # 2. HITUNG OMZET (Revenue)
    # Filter Status & Payment
    rev_query = db.session.query(func.sum(Order.total_amount))\
        .filter(Order.status != 'cancelled')\
        .filter(Order.payment_method != 'pending')
    
    # Filter Waktu
    if start_full:
        rev_query = rev_query.filter(Order.transaction_date >= start_full, Order.transaction_date <= end_full)
    
    revenue = float(rev_query.scalar() or 0)

    # 3. HITUNG HPP (COGS)
    # Join Order agar bisa filter status transaksi
    cogs_query = db.session.query(func.sum(OrderItem.quantity * OrderItem.cogs_at_sale))\
        .join(Order)\
        .filter(Order.status != 'cancelled')\
        .filter(Order.payment_method != 'pending')

    if start_full:
        cogs_query = cogs_query.filter(Order.transaction_date >= start_full, Order.transaction_date <= end_full)

    cogs = float(cogs_query.scalar() or 0)

    # 4. HITUNG BIAYA OPERASIONAL
    # Menggunakan filter tanggal (Date) karena expense_date bertipe Date (bukan DateTime)
    exp_query = db.session.query(func.sum(OperationalExpense.amount))
    if start_d_obj:
        exp_query = exp_query.filter(OperationalExpense.expense_date >= start_d_obj, OperationalExpense.expense_date <= end_d_obj)
    
    total_expense = float(exp_query.scalar() or 0)

    # 5. KALKULASI HASIL
    gross_profit = revenue - cogs
    net_profit = gross_profit - total_expense
    
    return jsonify({
        'title': 'Laporan Laba Rugi (Income Statement)',
        'period': f"{start_date_str} s/d {end_date_str}" if start_date_str else "Semua Waktu",
        'details': {
            '1. Pendapatan (Omzet)': revenue,
            '2. Beban Pokok Penjualan (HPP Bahan)': cogs,
            '3. Laba Kotor (Gross Profit)': gross_profit,
            '4. Beban Operasional': total_expense,
            '5. LABA BERSIH (Net Profit)': net_profit
        }
    }), 200

# =====================================================
# TAMBAHAN: Input Biaya Operasional
# =====================================================
@admin_bp.route('/expenses', methods=['POST'])
@admin_required()
def add_expense():
    data = request.get_json()
    if not data.get('name') or not data.get('amount') or not data.get('date'):
        return jsonify({'message': 'Data biaya tidak lengkap'}), 400
        
    new_expense = OperationalExpense(
        expense_name=data['name'],
        amount=data['amount'],
        expense_date=datetime.strptime(data['date'], '%Y-%m-%d'),
        description=data.get('description', '-')
    )
    db.session.add(new_expense)
    db.session.commit()
    
    return jsonify({'message': 'Biaya operasional dicatat.'}), 201