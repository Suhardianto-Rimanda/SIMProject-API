from flask import request, jsonify
from datetime import datetime
from app.extensions import db
from app.models import User, SalesSession, Product, Order, OrderItem, Recipe, Ingredient, InventoryLog
from app.decorators import cashier_required
from flask_jwt_extended import jwt_required, get_jwt_identity
from . import sales_bp

# =====================================================
# DASHBOARD KASIR (Info Umum)
# =====================================================
@sales_bp.route('/dashboard', methods=['GET'])
@cashier_required()
def sales_dashboard():
    user_id = get_jwt_identity()
    active_session = SalesSession.query.filter_by(user_id=user_id, end_time=None).first()
    
    status = "Shift Aktif" if active_session else "Shift Belum Dibuka"
    
    return jsonify({
        "title": "KASIR / POS",
        "status": status,
        "menu": ["Buka Shift", "Input Transaksi", "Riwayat Penjualan", "Tutup Shift"]
    }), 200

# =====================================================
# 1. BUKA SHIFT (START WORK)
# =====================================================
@sales_bp.route('/shift/open', methods=['POST'])
@cashier_required()
def open_shift():
    user_id = get_jwt_identity()
    data = request.get_json()
    start_cash = data.get('start_cash', 0)

    # Cek apakah kasir ini masih punya shift aktif?
    active_shift = SalesSession.query.filter_by(user_id=user_id, end_time=None).first()
    if active_shift:
        return jsonify({
            'message': 'Anda masih memiliki shift aktif. Tutup dulu sebelum buka baru.',
            'session_id': active_shift.id
        }), 400

    new_session = SalesSession(
        user_id=user_id,
        start_cash=start_cash,
        start_time=datetime.now()
    )
    db.session.add(new_session)
    db.session.commit()

    return jsonify({
        'message': 'Shift dibuka. Selamat bekerja!', 
        'session_id': new_session.id,
        'modal_awal': start_cash
    }), 201

# =====================================================
# 2. INPUT PESANAN (CORE TRANSACTION)
# =====================================================
@sales_bp.route('/orders', methods=['POST'])
@cashier_required()
def create_order():
    user_id = get_jwt_identity()
    
    # A. Validasi: Harus ada shift aktif
    active_session = SalesSession.query.filter_by(user_id=user_id, end_time=None).first()
    if not active_session:
        return jsonify({'message': 'Shift belum dibuka! Silakan Buka Shift dulu.'}), 403

    data = request.get_json()
    items_req = data.get('items') # Format: [{'product_id': 1, 'qty': 2}, ...]
    payment_method = data.get('payment_method', 'cash')

    if not items_req:
        return jsonify({'message': 'Keranjang belanja kosong!'}), 400

    # B. Buat Invoice Baru
    invoice_no = f"INV-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    try:
        total_amount = 0
        new_order = Order(
            invoice_no=invoice_no,
            user_id=user_id,
            session_id=active_session.id,
            payment_method=payment_method,
            total_amount=0 # Nanti diupdate
        )
        db.session.add(new_order)
        db.session.flush() # Agar new_order.id terbentuk

        # C. Loop Barang & Potong Stok
        for item in items_req:
            product = Product.query.get(item['product_id'])
            qty_sold = int(item['qty'])
            
            if not product: raise Exception(f"Produk ID {item['product_id']} tidak ditemukan")

            # --- LOGIC POTONG STOK BAHAN (Resep) ---
            menu_cogs = 0
            recipes = Recipe.query.filter_by(product_id=product.id).all()
            
            if not recipes:
                # Optional: Warning jika produk tidak punya resep (Misal: Kerupuk titipan)
                print(f"Info: Produk {product.name} tidak memiliki resep.")

            for r in recipes:
                ingredient = r.ingredient
                required_qty = r.quantity_needed * qty_sold
                
                # Cek Stok Cukup?
                if ingredient.current_stock < required_qty:
                     raise Exception(f"Stok '{ingredient.name}' tidak cukup! Sisa: {ingredient.current_stock}, Butuh: {required_qty}")

                # KURANGI STOK
                ingredient.current_stock -= required_qty
                
                # Catat Log Gudang
                log = InventoryLog(
                    ingredient_id=ingredient.id,
                    user_id=user_id,
                    change_type='production', 
                    quantity_change= -required_qty 
                )
                db.session.add(log)

                # Hitung HPP saat ini
                menu_cogs += (float(ingredient.avg_cost) * float(r.quantity_needed))

            # Simpan Item Transaksi
            price_at_sale = float(product.price)
            order_item = OrderItem(
                order_id=new_order.id,
                product_id=product.id,
                quantity=qty_sold,
                price_at_sale=price_at_sale,
                cogs_at_sale=menu_cogs 
            )
            db.session.add(order_item)
            
            total_amount += (price_at_sale * qty_sold)

        # D. Finalisasi
        new_order.total_amount = total_amount
        
        # Update Total Penjualan di Shift ini
        active_session.total_system = float(active_session.total_system) + total_amount
        
        db.session.commit() 

        return jsonify({
            'message': 'Transaksi berhasil!',
            'invoice': invoice_no,
            'total': total_amount
        }), 201

    except Exception as e:
        db.session.rollback() # Batalkan jika error
        return jsonify({'message': f'Transaksi Gagal: {str(e)}'}), 400

# =====================================================
# 3. CETAK STRUK (DATA)
# =====================================================
@sales_bp.route('/orders/<string:invoice_no>', methods=['GET'])
@cashier_required()
def get_receipt(invoice_no):
    order = Order.query.filter_by(invoice_no=invoice_no).first_or_404()
    
    items_data = []
    for item in order.items:
        items_data.append({
            'product': item.product.name,
            'qty': item.quantity,
            'price': float(item.price_at_sale),
            'subtotal': float(item.price_at_sale) * item.quantity
        })

    return jsonify({
        'store_name': 'Kerupuk Mekar Sari',
        'invoice': order.invoice_no,
        'date': order.transaction_date.strftime('%Y-%m-%d %H:%M'),
        'cashier': order.cashier.username,
        'items': items_data,
        'total': float(order.total_amount),
        'payment': order.payment_method
    }), 200

# =====================================================
# 4. TUTUP SHIFT (END DAY)
# =====================================================
@sales_bp.route('/shift/close', methods=['POST'])
@cashier_required()
def close_shift():
    user_id = get_jwt_identity()
    data = request.get_json()
    end_cash_actual = data.get('end_cash_actual') # Uang fisik di laci

    active_session = SalesSession.query.filter_by(user_id=user_id, end_time=None).first()
    if not active_session:
        return jsonify({'message': 'Tidak ada shift aktif.'}), 400

    # Update Sesi
    active_session.end_time = datetime.now()
    active_session.end_cash_actual = end_cash_actual
    
    # Hitung Selisih (Uang Fisik - (Modal Awal + Penjualan Sistem))
    expected_cash = float(active_session.start_cash) + float(active_session.total_system)
    difference = float(end_cash_actual) - expected_cash

    db.session.commit()

    return jsonify({
        'message': 'Shift ditutup.',
        'summary': {
            'modal_awal': float(active_session.start_cash),
            'total_penjualan_sistem': float(active_session.total_system),
            'seharusnya_ada': expected_cash,
            'uang_fisik': float(end_cash_actual),
            'selisih': difference 
        }
    }), 200
    

# =====================================================
# 5. DAFTAR MENU (KATALOG PRODUK)
# =====================================================
@sales_bp.route('/menu', methods=['GET'])
@cashier_required()
def get_menu_list():
    # Ambil parameter filter dari URL (opsional)
    # Contoh: /sales/menu?category=Makanan
    category_filter = request.args.get('category')

    query = Product.query.filter_by(is_active=True)
    
    if category_filter:
        query = query.filter(Product.category.ilike(f"%{category_filter}%"))
    
    products = query.all()
    
    menu_data = []
    for p in products:
        menu_data.append({
            'id': p.id,
            'name': p.name,
            'category': p.category,
            'price': float(p.price),
            # Optional: Cek apakah produk ini punya resep? 
            # (Hanya info, validasi stok tetap saat transaksi)
            'has_recipe': bool(p.recipes) 
        })

    return jsonify({
        'count': len(menu_data),
        'menu': menu_data
    }), 200