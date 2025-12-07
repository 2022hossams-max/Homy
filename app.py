from flask import Flask, jsonify, render_template, request, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
# مفتاح سري إلزامي للجلسات
app.config['SECRET_KEY'] = 'your_super_secret_key_12345' 
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- نماذج قاعدة البيانات (Models) ---

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=True)
    stock = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'price': self.price,
            'description': self.description,
            'stock': self.stock
        }

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(100), nullable=False)
    customer_email = db.Column(db.String(100), nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    date_placed = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    status = db.Column(db.String(20), default='New')
    items = db.relationship('OrderItem', backref='order', lazy=True)

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)

# --- وظائف مساعدة للسلة ---

def get_cart_details():
    if 'cart' not in session:
        session['cart'] = {}
    
    cart_items = []
    total_price = 0
    
    for product_id, quantity in session['cart'].items():
        product = Product.query.get(int(product_id))
        if product:
            item_total = product.price * quantity
            total_price += item_total
            cart_items.append({
                'product_id': product.id,
                'name': product.name,
                'price': product.price,
                'quantity': quantity,
                'item_total': item_total
            })
    
    return cart_items, total_price

# --- مسارات المتجر العام (Frontend Routes) ---

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/products')
def get_products():
    products = Product.query.all()
    return jsonify([p.to_dict() for p in products])

@app.route('/cart/add/<int:product_id>')
def add_to_cart(product_id):
    product = Product.query.get(product_id)
    if not product:
        return jsonify({"message": "المنتج غير موجود"}), 404

    cart = session.get('cart', {})
    product_id_str = str(product_id)
    cart[product_id_str] = cart.get(product_id_str, 0) + 1
    session['cart'] = cart
    session.modified = True 
    return jsonify({"message": f"تمت إضافة {product.name} إلى السلة", "cart_count": sum(cart.values())})

@app.route('/cart')
def view_cart():
    cart_items, total_price = get_cart_details()
    return jsonify({
        'items': cart_items,
        'total': total_price,
        'count': sum(session.get('cart', {}).values())
    })

@app.route('/cart/clear')
def clear_cart():
    session['cart'] = {}
    session.modified = True
    return jsonify({"message": "تم تفريغ السلة بنجاح", "cart_count": 0})

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    cart_items, total_price = get_cart_details()

    if not cart_items:
        return redirect(url_for('home'))

    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')

        new_order = Order(
            customer_name=name,
            customer_email=email,
            total_price=total_price
        )
        db.session.add(new_order)
        db.session.commit()
        
        for item in cart_items:
            order_item = OrderItem(
                order_id=new_order.id,
                product_name=item['name'],
                price=item['price'],
                quantity=item['quantity']
            )
            db.session.add(order_item)
            
        db.session.commit()

        session['cart'] = {}
        session.modified = True
        
        return redirect(url_for('order_success', order_id=new_order.id))

    return render_template('checkout.html', cart_items=cart_items, total_price=total_price)

@app.route('/order_success/<int:order_id>')
def order_success(order_id):
    return render_template('order_success.html', order_id=order_id)

# --- مسارات الإدارة (Admin Routes) ---

@app.route('/admin')
def admin_panel():
    products = Product.query.all()
    orders = Order.query.order_by(Order.date_placed.desc()).all() 
    success_message = request.args.get('message')
    
    return render_template('admin.html', products=products, orders=orders, success_message=success_message) 

@app.route('/add_product', methods=['POST'])
def add_product():
    name = request.form.get('name')
    price = request.form.get('price')
    description = request.form.get('description')
    stock = request.form.get('stock')
    
    if not name or not price:
        return "خطأ: يجب توفير اسم وسعر للمنتج.", 400
    
    try:
        new_product = Product(
            name=name,
            price=float(price),
            description=description,
            stock=int(stock)
        )
        db.session.add(new_product)
        db.session.commit()
        return redirect(url_for('admin_panel', message=f'تمت إضافة المنتج {name} بنجاح!'))
    except ValueError:
        return "خطأ: يجب أن يكون السعر ورصيد المخزون أرقاماً.", 400

@app.route('/edit_product/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    
    if request.method == 'POST':
        product.name = request.form.get('name')
        product.price = float(request.form.get('price'))
        product.description = request.form.get('description')
        product.stock = int(request.form.get('stock'))
        
        try:
            db.session.commit()
            return redirect(url_for('admin_panel', message=f'تم تعديل المنتج {product.name} بنجاح!'))
        except:
            db.session.rollback()
            return "خطأ أثناء التعديل", 500

    return render_template('edit_product.html', product=product)

@app.route('/delete_product/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    product_name = product.name
    
    db.session.delete(product)
    db.session.commit()
    
    return redirect(url_for('admin_panel', message=f'تم حذف المنتج {product_name} بنجاح.'))

@app.route('/update_order_status/<int:order_id>', methods=['POST'])
def update_order_status(order_id):
    order = Order.query.get_or_404(order_id)
    new_status = request.form.get('status')
    
    if new_status in ['New', 'Processing', 'Shipped', 'Delivered']:
        order.status = new_status
        db.session.commit()
        return redirect(url_for('admin_panel', message=f'تم تحديث حالة الطلب #{order_id} إلى {new_status}.'))
        
    return "حالة طلب غير صالحة", 400

@app.route('/order_details/<int:order_id>')
def order_details(order_id):
    order = Order.query.get_or_404(order_id)
    return render_template('order_details.html', order=order)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # إضافة بيانات تجريبية (إذا كانت قاعدة البيانات فارغة)
        if Product.query.count() == 0:
            db.session.add(Product(name="Laptop Pro", price=1200.0, description="Powerful machine.", stock=10))
            db.session.add(Product(name="Wireless Mouse", price=25.0, description="Ergonomic design.", stock=50))
            db.session.commit()
    
    app.run(debug=True, host='0.0.0.0', port=5000)
