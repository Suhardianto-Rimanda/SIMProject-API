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
    session_info = None
    if active_session:
        session_info = {
            "id": active_session.id,
            "start_cash": float(active_session.start_cash),   # Modal Awal
            "total_sales": float(active_session.total_system) # Omset Sementara
        }
    return jsonify({
        "title": "KASIR / POS",
        "status": status,
        "session_info": session_info,
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
    customer_name = data.get('customer_name', 'Pelanggan Umum')
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
            status='pending',
            customer_name=customer_name,
            total_amount=0, # Nanti diupdate
            transaction_date=datetime.now()
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
        if payment_method != 'pending':
            active_session.total_system = float(active_session.total_system) + total_amount
        
        db.session.commit() 

        return jsonify({
            'message': 'Transaksi berhasil!',
            'invoice': invoice_no,
            'total': total_amount,
            'customer': customer_name,
            'date': new_order.transaction_date.strftime('%d-%m-%Y %H:%M')
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Gagal: {str(e)}'}), 400

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
        'customer': order.customer_name,
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
    # =====================================================
# 6. LIHAT PESANAN BELUM LUNAS (OPEN BILL)
# =====================================================
@sales_bp.route('/orders/pending', methods=['GET'])
@cashier_required()
def get_pending_orders():
    # Ambil order yang payment_method nya 'pending' (belum bayar)
    orders = Order.query.filter_by(payment_method='pending').order_by(Order.transaction_date.desc()).all()
    
    output = []
    for o in orders:
        output.append({
            'invoice': o.invoice_no,
            'customer': o.customer_name,    
            'time': o.transaction_date.strftime('%H:%M'),
            'total': float(o.total_amount),
            'items_count': len(o.items)
        })
        
    return jsonify(output), 200

# =====================================================
# 7. BAYAR TAGIHAN (PELUNASAN)
# =====================================================
@sales_bp.route('/orders/<string:invoice>/pay', methods=['POST'])
@cashier_required()
def pay_pending_order(invoice):
    data = request.get_json()
    method = data.get('payment_method', 'cash')
    
    order = Order.query.filter_by(invoice_no=invoice).first()
    if not order:
        return jsonify({'message': 'Invoice tidak ditemukan'}), 404
        
    if order.payment_method != 'pending':
        return jsonify({'message': 'Pesanan ini sudah lunas!'}), 400
        
    # Update Status Pembayaran
    order.payment_method = method
    
    # Update Total Sales di Session (Karena baru uang masuk sekarang)
    if order.session_id:
        session = SalesSession.query.get(order.session_id)
        if session:
            session.total_system = float(session.total_system) + float(order.total_amount)
            
    db.session.commit()
    
    return jsonify({'message': 'Pembayaran berhasil!', 'invoice': order.invoice_no}), 200
# =====================================================
# [BARU] REFUND / BATALKAN PESANAN
# =====================================================
@sales_bp.route('/orders/<string:invoice>/void', methods=['POST'])
@cashier_required()
def void_order(invoice):
    user_id = get_jwt_identity()
    order = Order.query.filter_by(invoice_no=invoice).first()
    
    if not order: return jsonify({'message': 'Invoice tidak ditemukan'}), 404
    if order.status == 'cancelled': return jsonify({'message': 'Pesanan sudah dibatalkan sebelumnya'}), 400

    try:
        # 1. Tandai Order sebagai Cancelled
        order.status = 'cancelled'
        
        # 2. Kembalikan Uang ke Shift (Jika sudah lunas)
        if order.payment_method != 'pending' and order.session_id:
            session = SalesSession.query.get(order.session_id)
            if session:
                session.total_system = float(session.total_system) - float(order.total_amount)

        # 3. Kembalikan Stok Bahan Baku (Restoration)
        for item in order.items:
            recipes = Recipe.query.filter_by(product_id=item.product_id).all()
            for r in recipes:
                ingredient = r.ingredient
                restore_qty = r.quantity_needed * item.quantity
                
                # Tambah stok balik
                ingredient.current_stock += restore_qty
                
                # Catat Log Pengembalian
                log = InventoryLog(
                    ingredient_id=ingredient.id,
                    user_id=user_id,
                    change_type='adjustment', # Dianggap penyesuaian/pembatalan
                    quantity_change=restore_qty
                )
                db.session.add(log)

        db.session.commit()
        return jsonify({'message': f'Transaksi {invoice} berhasil dibatalkan (Refund). Stok dikembalikan.'}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Gagal Refund: {str(e)}'}), 500
 # =====================================================
# 8. DATA RIWAYAT TRANSAKSI (ALL TIME - LIMIT 50)
# =====================================================
@sales_bp.route('/orders/history', methods=['GET'])
@cashier_required()
def get_order_history():
    # REVISI: Jangan filter 'today' agar data tidak hilang saat pergantian hari/jam server beda.
    # Ambil 50 transaksi terakhir secara global.
    
    orders = Order.query.order_by(Order.transaction_date.desc()).limit(50).all()
    
    output = []
    for o in orders:
        output.append({
            'invoice': o.invoice_no,
            'customer': o.customer_name, 
            'total': float(o.total_amount),
            'status': o.status,
            'payment': o.payment_method,
            # Format tanggal lebih lengkap: Tgl-Blan Jam:Menit
            'time': o.transaction_date.strftime('%d/%m %H:%M') 
        })
    return jsonify(output), 200
# =====================================================
# 9. HAPUS RIWAYAT TRANSAKSI (HARD DELETE)
# =====================================================
@sales_bp.route('/orders/<string:invoice>', methods=['DELETE'])
@cashier_required()
def delete_order_permanently(invoice):
    order = Order.query.filter_by(invoice_no=invoice).first()
    if not order: 
        return jsonify({'message': 'Invoice tidak ditemukan'}), 404

    try:
        # A. KEMBALIKAN UANG KE SHIFT (Jika Lunas & Belum Cancel)
        # Supaya omset hari ini tidak kelebihan
        if order.payment_method != 'pending' and order.status != 'cancelled' and order.session_id:
            session = SalesSession.query.get(order.session_id)
            if session:
                session.total_system = float(session.total_system) - float(order.total_amount)

        # B. KEMBALIKAN STOK (Jika Belum Cancel)
        # Jika status 'cancelled', stok sudah dikembalikan saat void, jadi skip langkah ini.
        if order.status != 'cancelled':
            for item in order.items:
                recipes = Recipe.query.filter_by(product_id=item.product_id).all()
                for r in recipes:
                    ingredient = r.ingredient
                    restore_qty = r.quantity_needed * item.quantity
                    ingredient.current_stock += restore_qty # Balikin stok

        # C. HAPUS DATA PERMANEN
        # Hapus item dulu (child), baru order (parent)
        OrderItem.query.filter_by(order_id=order.id).delete()
        db.session.delete(order)
        db.session.commit()

        return jsonify({'message': 'Data transaksi berhasil dihapus permanen.'}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Gagal hapus: {str(e)}'}), 500