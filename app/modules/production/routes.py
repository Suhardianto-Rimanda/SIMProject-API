from flask import request, jsonify
from datetime import datetime, date
from app.extensions import db
from app.models import Ingredient, InventoryLog, Order
from app.decorators import kitchen_required
from flask_jwt_extended import jwt_required, get_jwt_identity
from . import production_bp

# =====================================================
# DASHBOARD PRODUCTION (GUDANG & DAPUR)
# =====================================================
@production_bp.route('/dashboard', methods=['GET'])
@kitchen_required()
def kitchen_dashboard():
    low_stock_count = Ingredient.query.filter(Ingredient.current_stock < 5).count()
    
    return jsonify({
        "title": "DAPUR & GUDANG (PRODUCTION)",
        "role": "Production Staff",
        "alert": f"Ada {low_stock_count} bahan yang stoknya menipis!",
        "menu": [
            "Cek Stok Detail (Stocks)", 
            "Daftar Nama Bahan (Dropdown)",
            "Input Pembelian (Restock)", 
            "Stock Opname (Penyesuaian)",
            "Antrian Masak (Queue)"
        ]
    }), 200

# =====================================================
# 1. CEK STOK REAL-TIME (DETAIL MONITORING)
# =====================================================
@production_bp.route('/stocks', methods=['GET'])
@kitchen_required()
def get_stocks():
    # Fitur tambahan: Bisa cari nama bahan (?q=tepung)
    search_query = request.args.get('q')
    
    query = Ingredient.query
    if search_query:
        query = query.filter(Ingredient.name.ilike(f"%{search_query}%"))
        
    ingredients = query.all()
    output = []
    
    for item in ingredients:
        status = "Aman"
        qty = float(item.current_stock)
        
        if qty <= 0:
            status = "HABIS!"
        elif qty < 5: 
            status = "Menipis"

        output.append({
            'id': item.id,
            'name': item.name,
            'stock': qty,
            'unit': item.unit,
            'avg_cost': float(item.avg_cost),
            'status': status
        })
        
    return jsonify({'timestamp': datetime.now(), 'count': len(output), 'data': output}), 200

# =====================================================
# 1.B. DAFTAR BAHAN (SIMPLE LIST UNTUK DROPDOWN)
# =====================================================
@production_bp.route('/ingredients', methods=['GET'])
@kitchen_required()
def get_ingredient_list():
    # Endpoint ini ringan, khusus untuk mengisi 'Select Option' di form Restock/Opname
    ingredients = Ingredient.query.order_by(Ingredient.name).all()
    
    data = []
    for item in ingredients:
        data.append({
            'id': item.id,
            'name': item.name,
            'unit': item.unit
        })
        
    return jsonify({'list': data}), 200

# =====================================================
# 2. INPUT PEMBELIAN (RESTOCK)
# =====================================================
@production_bp.route('/restock', methods=['POST'])
@kitchen_required()
def restock_ingredient():
    user_id = get_jwt_identity()
    data = request.get_json()
    
    ingredient_id = data.get('ingredient_id')
    qty_bought = float(data.get('qty'))
    price_per_unit = float(data.get('price'))
    
    ingredient = Ingredient.query.get(ingredient_id)
    if not ingredient:
        return jsonify({'message': 'Bahan baku tidak ditemukan'}), 404

    # WEIGHTED AVERAGE COST
    old_val = float(ingredient.current_stock) * float(ingredient.avg_cost)
    new_val = qty_bought * price_per_unit
    total_stock = float(ingredient.current_stock) + qty_bought
    
    if total_stock > 0:
        new_avg_cost = (old_val + new_val) / total_stock
    else:
        new_avg_cost = price_per_unit

    ingredient.current_stock = total_stock
    ingredient.avg_cost = new_avg_cost
    
    log = InventoryLog(
        ingredient_id=ingredient.id,
        user_id=user_id,
        change_type='purchase',
        quantity_change=qty_bought
    )
    
    db.session.add(log)
    db.session.commit()

    return jsonify({
        'message': 'Restock berhasil dicatat.',
        'item': ingredient.name,
        'added_qty': qty_bought,
        'total_stock': float(ingredient.current_stock),
        'new_avg_cost': round(new_avg_cost, 2)
    }), 200

# =====================================================
# 3. STOCK OPNAME (PENYESUAIAN MANUAL)
# =====================================================
@production_bp.route('/adjustment', methods=['POST'])
@kitchen_required()
def adjust_stock():
    user_id = get_jwt_identity()
    data = request.get_json()
    
    ingredient_id = data.get('ingredient_id')
    qty_change = float(data.get('qty_change')) 
    reason = data.get('reason', 'adjustment')
    
    ingredient = Ingredient.query.get(ingredient_id)
    if not ingredient:
        return jsonify({'message': 'Bahan baku tidak ditemukan'}), 404

    ingredient.current_stock = float(ingredient.current_stock) + qty_change
    
    change_type = 'adjustment'
    reason_lower = reason.lower()
    if qty_change < 0 and ('busuk' in reason_lower or 'rusak' in reason_lower or 'buang' in reason_lower):
        change_type = 'waste' 
    
    log = InventoryLog(
        ingredient_id=ingredient.id,
        user_id=user_id,
        change_type=change_type,
        quantity_change=qty_change
    )
    
    db.session.add(log)
    db.session.commit()
    
    return jsonify({
        'message': 'Stok berhasil disesuaikan (Opname).',
        'item': ingredient.name,
        'current_stock': float(ingredient.current_stock),
        'change_type': change_type
    }), 200

# =====================================================
# 4. ANTRIAN MASAK (PRODUCTION QUEUE)
# =====================================================
@production_bp.route('/queue', methods=['GET'])
@kitchen_required()
def production_queue():
    today = date.today()
    start_of_day = datetime.combine(today, datetime.min.time())
    
    orders = Order.query.filter(Order.transaction_date >= start_of_day).all()
    
    kitchen_tasks = {}
    
    for order in orders:
        for item in order.items:
            menu_name = item.product.name
            if menu_name not in kitchen_tasks:
                kitchen_tasks[menu_name] = {'total_qty': 0, 'orders': []}
            
            kitchen_tasks[menu_name]['total_qty'] += item.quantity
            kitchen_tasks[menu_name]['orders'].append(order.invoice_no)
    
    return jsonify({
        'date': today.strftime('%Y-%m-%d'),
        'tasks': kitchen_tasks
    }), 200