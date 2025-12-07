from flask import request, jsonify
from sqlalchemy import func
from datetime import datetime
from app.extensions import db
from app.models import Ingredient, Order, OrderItem, OperationalExpense
from app.decorators import admin_required
from . import admin_bp

# =====================================================
# 1. LAPORAN STOK (Asset Value)
# =====================================================
@admin_bp.route('/reports/stock', methods=['GET'])
@admin_required()
def report_stock():
    # Mengambil semua bahan
    items = Ingredient.query.all()
    
    output = []
    total_asset_value = 0
    
    for i in items:
        # Hitung nilai aset (Stok x Harga Rata-rata)
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
        'total_asset_value': total_asset_value, # Total uang yang mengendap di gudang
        'items': output
    }), 200

# =====================================================
# 2. LAPORAN PENJUALAN (Sales Recap)
# =====================================================
@admin_bp.route('/reports/sales', methods=['GET'])
@admin_required()
def report_sales():
    # Ambil filter tanggal dari URL (contoh: ?start_date=2023-01-01&end_date=2023-01-31)
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    query = db.session.query(
        func.date(Order.transaction_date).label('date'),
        func.count(Order.id).label('total_trx'),
        func.sum(Order.total_amount).label('total_revenue')
    )
    
    # Filter Tanggal (Jika ada)
    if start_date_str and end_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        query = query.filter(func.date(Order.transaction_date).between(start_date, end_date))
        
    # Group by Tanggal
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
# 3. LAPORAN LABA RUGI (Profit & Loss) - INTI ERP
# =====================================================
@admin_bp.route('/reports/profit-loss', methods=['GET'])
@admin_required()
def report_profit_loss():
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    # A. Hitung OMZET (Revenue) & HPP (COGS)
    query = db.session.query(
        func.sum(OrderItem.quantity * OrderItem.price_at_sale).label('revenue'),
        func.sum(OrderItem.quantity * OrderItem.cogs_at_sale).label('cogs')
    ).join(Order, OrderItem.order_id == Order.id)
    
    # Filter Biaya Operasional
    expense_query = db.session.query(func.sum(OperationalExpense.amount))
    
    if start_date_str and end_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        
        query = query.filter(func.date(Order.transaction_date).between(start_date, end_date))
        expense_query = expense_query.filter(OperationalExpense.expense_date.between(start_date, end_date))
        
    result = query.first()
    
    # Ambil nilai expense, default 0 jika None
    raw_total_expense = expense_query.scalar() or 0 
    
    # <--- PERBAIKAN DI SINI: Ubah Decimal ke Float
    total_expense = float(raw_total_expense)
    
    revenue = float(result.revenue or 0)
    cogs = float(result.cogs or 0)
    
    gross_profit = revenue - cogs
    
    # Sekarang pengurangan aman karena keduanya Float
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
# TAMBAHAN: Input Biaya Operasional (Agar P&L Lengkap)
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