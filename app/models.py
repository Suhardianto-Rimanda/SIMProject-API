from app.extensions import db
from datetime import datetime, timedelta  # <--- Tambahkan timedelta



def get_wib_now():
    return datetime.utcnow() + timedelta(hours=7)
# ==========================================
# 1. TABEL AKTOR (USER & AUTH)
# ==========================================
class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False) # Hash password
    role = db.Column(db.Enum('admin', 'cashier', 'kitchen'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relasi
    orders = db.relationship('Order', backref='cashier', lazy=True)
    inventory_logs = db.relationship('InventoryLog', backref='staff', lazy=True)

    def __repr__(self):
        return f"<User {self.username}>"

class TokenBlocklist(db.Model):
    __tablename__ = 'token_blocklist'
    
    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(36), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False)

# ==========================================
# 2. MODUL MANUFACTURING (BAHAN & RESEP)
# ==========================================
class Ingredient(db.Model):
    __tablename__ = 'ingredients'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    
    # 1. SATUAN DASAR (Dipakai di Resep & Stok Sistem)
    # Contoh: 'gr', 'ml', 'pcs'
    unit = db.Column(db.String(20), nullable=False) 
    
    # 2. SATUAN BELI (Tampilan saat Restock) [BARU]
    # Contoh: 'Karung', 'Botol', 'Karton'
    purchase_unit = db.Column(db.String(20), default='pcs') 
    
    # 3. RASIO KONVERSI [BARU]
    # Contoh: 1 Karung = 25000 gr. Maka isinya: 25000
    conversion_rate = db.Column(db.Numeric(10, 2), default=1) 

    current_stock = db.Column(db.Numeric(10, 2), default=0) # Disimpan dalam 'unit' (gr/ml)
    avg_cost = db.Column(db.Numeric(15, 2), default=0) # Harga per 'unit' (per gram)
    
    updated_at = db.Column(db.DateTime, default=get_wib_now, onupdate=get_wib_now)
    logs = db.relationship('InventoryLog', backref='ingredient', lazy=True)

class Product(db.Model):
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Numeric(15, 2), nullable=False) 
    category = db.Column(db.String(50)) 
    is_active = db.Column(db.Boolean, default=True)

    recipes = db.relationship('Recipe', backref='product', lazy=True)

class Recipe(db.Model):
    __tablename__ = 'recipes'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    ingredient_id = db.Column(db.Integer, db.ForeignKey('ingredients.id'), nullable=False)
    quantity_needed = db.Column(db.Numeric(10, 2), nullable=False)

    ingredient = db.relationship('Ingredient', backref='used_in_recipes', lazy=True)

class InventoryLog(db.Model):
    __tablename__ = 'inventory_logs'

    id = db.Column(db.Integer, primary_key=True)
    ingredient_id = db.Column(db.Integer, db.ForeignKey('ingredients.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    change_type = db.Column(db.Enum('purchase', 'production', 'waste', 'adjustment'), nullable=False)
    quantity_change = db.Column(db.Numeric(10, 2), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ==========================================
# 3. MODUL SALES (SHIFT & TRANSAKSI)
# ==========================================
class SalesSession(db.Model):
    __tablename__ = 'sales_sessions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime, nullable=True) 
    
    start_cash = db.Column(db.Numeric(15, 2), default=0) 
    end_cash_actual = db.Column(db.Numeric(15, 2), nullable=True) 
    total_system = db.Column(db.Numeric(15, 2), default=0)
    
    # Relasi ke Order
    orders = db.relationship('Order', backref='session', lazy=True)

class Order(db.Model):
    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True)
    invoice_no = db.Column(db.String(50), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Link ke Shift (Wajib ada untuk pelaporan shift)
    session_id = db.Column(db.Integer, db.ForeignKey('sales_sessions.id'), nullable=True)
    
    # === [BARU] STATUS ORDER UNTUK DAPUR ===
    # Default 'pending' saat kasir input. Nanti diubah jadi 'cooking' atau 'completed'
    status = db.Column(db.String(20), default='pending') 
    

    total_amount = db.Column(db.Numeric(15, 2), nullable=False)
    # Tambahkan 'pending' ke dalam Enum
    payment_method = db.Column(db.Enum('cash', 'qris', 'transfer', 'pending'), default='pending')
    customer_name = db.Column(db.String(100), default='Pelanggan Umum')
    transaction_date = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship('OrderItem', backref='order', lazy=True)
class OrderItem(db.Model):
    __tablename__ = 'order_items'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price_at_sale = db.Column(db.Numeric(15, 2), nullable=False)
    cogs_at_sale = db.Column(db.Numeric(15, 2), nullable=False) # HPP saat kejadian

    product = db.relationship('Product')

# ==========================================
# 4. MODUL ACCOUNTING (BIAYA LAIN)
# ==========================================
class OperationalExpense(db.Model):
    __tablename__ = 'operational_expenses'

    id = db.Column(db.Integer, primary_key=True)
    expense_name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Numeric(15, 2), nullable=False)
    expense_date = db.Column(db.Date, nullable=False)
    description = db.Column(db.Text)