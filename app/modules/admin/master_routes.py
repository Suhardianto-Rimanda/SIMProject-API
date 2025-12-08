from flask import request, jsonify
from app.extensions import db  
from app.models import Ingredient, Product, Recipe
from app.decorators import admin_required
from . import admin_bp

# =====================================================
# 1. CRUD BAHAN BAKU (INGREDIENTS) - UPDATED (MULTI-UNIT)
# =====================================================

@admin_bp.route('/ingredients', methods=['POST'])
@admin_required()
def create_ingredient():
    data = request.get_json()
    if not data.get('name') or not data.get('unit'):
        return jsonify({'message': 'Nama dan Satuan Dasar wajib diisi!'}), 400

    if Ingredient.query.filter_by(name=data['name']).first():
        return jsonify({'message': f"Bahan '{data['name']}' sudah ada!"}), 409

    # Simpan data konversi (Default ke satuan dasar jika kosong)
    new_ing = Ingredient(
        name=data['name'],
        unit=data['unit'],                                       # Satuan Resep (Gram)
        purchase_unit=data.get('purchase_unit', data['unit']),   # Satuan Beli (Karung)
        conversion_rate=data.get('conversion_rate', 1),          # 1 Karung = X Gram
        current_stock=0,
        avg_cost=0
    )
    db.session.add(new_ing)
    db.session.commit()
    return jsonify({'message': 'Bahan baku berhasil ditambahkan', 'id': new_ing.id}), 201

@admin_bp.route('/ingredients', methods=['GET'])
@admin_required()
def get_ingredients():
    items = Ingredient.query.order_by(Ingredient.name).all()
    return jsonify([{
        'id': i.id, 
        'name': i.name, 
        'unit': i.unit, 
        # Gunakan 'or' untuk memberi nilai default jika database NULL
        'purchase_unit': i.purchase_unit or i.unit, 
        'conversion_rate': float(i.conversion_rate or 1), 
        'stock': float(i.current_stock or 0), 
        'avg_cost': float(i.avg_cost or 0)
    } for i in items]), 200

@admin_bp.route('/ingredients/<int:id>', methods=['PUT'])
@admin_required()
def update_ingredient(id):
    ing = Ingredient.query.get_or_404(id)
    data = request.get_json()
    
    if 'name' in data: ing.name = data['name']
    if 'unit' in data: ing.unit = data['unit']
    if 'purchase_unit' in data: ing.purchase_unit = data['purchase_unit']
    if 'conversion_rate' in data: ing.conversion_rate = data['conversion_rate']
    
    db.session.commit()
    return jsonify({'message': 'Bahan diperbarui'}), 200

@admin_bp.route('/ingredients/<int:id>', methods=['DELETE'])
@admin_required()
def delete_ingredient(id):
    ing = Ingredient.query.get_or_404(id)
    # Cek ketergantungan resep
    if Recipe.query.filter_by(ingredient_id=id).first():
        return jsonify({'message': 'Gagal! Bahan ini dipakai di sebuah Resep.'}), 400
    db.session.delete(ing)
    db.session.commit()
    return jsonify({'message': 'Bahan dihapus'}), 200
# =====================================================
# 2. CRUD PRODUK / MENU (PRODUCTS)
# =====================================================

@admin_bp.route('/products', methods=['POST'])
@admin_required()
def create_product():
    data = request.get_json()
    if not data.get('name') or not data.get('price'):
        return jsonify({'message': 'Nama Menu dan Harga Jual wajib diisi!'}), 400

    new_prod = Product(
        name=data['name'],
        price=data['price'],
        category=data.get('category', 'Food'),
        is_active=True
    )
    db.session.add(new_prod)
    db.session.commit()
    return jsonify({'message': f"Menu '{new_prod.name}' siap dijual!", 'id': new_prod.id}), 201

@admin_bp.route('/products', methods=['GET'])
@admin_required()
def get_products():
    products = Product.query.all()
    output = []
    for p in products:
        output.append({
            'id': p.id,
            'name': p.name,
            'price': float(p.price),
            'category': p.category,
            'is_active': p.is_active
        })
    return jsonify(output), 200

@admin_bp.route('/products/<int:id>', methods=['PUT'])
@admin_required()
def update_product(id):
    prod = Product.query.get_or_404(id)
    data = request.get_json()
    if 'name' in data: prod.name = data['name']
    if 'price' in data: prod.price = data['price']
    if 'category' in data: prod.category = data['category']
    if 'is_active' in data: prod.is_active = data['is_active']
    db.session.commit()
    return jsonify({'message': 'Data menu diperbarui', 'name': prod.name}), 200

@admin_bp.route('/products/<int:id>', methods=['DELETE'])
@admin_required()
def delete_product(id):
    prod = Product.query.get_or_404(id)
    db.session.delete(prod)
    db.session.commit()
    return jsonify({'message': 'Menu dihapus permanen'}), 200


# =====================================================
# 3. MANAJEMEN RESEP (RECIPES)
# =====================================================

@admin_bp.route('/recipes', methods=['POST'])
@admin_required()
def add_recipe_item():
    data = request.get_json()
    if not data.get('product_id') or not data.get('ingredient_id') or not data.get('quantity_needed'):
        return jsonify({'message': 'Data tidak lengkap (product_id, ingredient_id, quantity_needed)'}), 400
        
    prod = Product.query.get(data['product_id'])
    ing = Ingredient.query.get(data['ingredient_id'])
    
    if not prod: return jsonify({'message': 'Menu tidak ditemukan'}), 404
    if not ing: return jsonify({'message': 'Bahan tidak ditemukan'}), 404

    new_recipe = Recipe(
        product_id=data['product_id'],
        ingredient_id=data['ingredient_id'],
        quantity_needed=data['quantity_needed']
    )
    db.session.add(new_recipe)
    db.session.commit()
    
    return jsonify({
        'message': 'Item resep ditambahkan',
        'detail': f"{prod.name} menggunakan {data['quantity_needed']} {ing.unit} {ing.name}"
    }), 201

@admin_bp.route('/recipes/<int:product_id>', methods=['GET'])
@admin_required()
def get_product_recipe(product_id):
    product = Product.query.get_or_404(product_id)
    recipes = Recipe.query.filter_by(product_id=product_id).all()
    
    recipe_list = []
    for r in recipes:
        recipe_list.append({
            'recipe_id': r.id,
            'ingredient_id': r.ingredient.id,
            'ingredient_name': r.ingredient.name,
            'quantity': float(r.quantity_needed),
            'unit': r.ingredient.unit
        })
        
    return jsonify({
        'product_name': product.name,
        'recipe_items': recipe_list
    }), 200

@admin_bp.route('/recipes/<int:recipe_id>', methods=['DELETE'])
@admin_required()
def delete_recipe_item(recipe_id):
    item = Recipe.query.get_or_404(recipe_id)
    db.session.delete(item)
    db.session.commit()
    return jsonify({'message': 'Item resep dihapus'}), 200