from flask import Flask, jsonify, render_template, request, session, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import or_, func
import os 
from werkzeug.utils import secure_filename 

# --- إعدادات التطبيق ---
ADMIN_USERNAME = 'hossam_admin'
ADMIN_PASSWORD = 'strong_password123' 
# ------------------------

# إعدادات رفع الملفات
UPLOAD_FOLDER = 'static/product_images' 
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'} 

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_super_secret_key_12345' 
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db = SQLAlchemy(app)

# --- وظائف مساعدة لرفع الملفات (كما هي) ---
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def handle_image_upload(file):
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])
            
        file.save(filepath)
        
        return '/' + filepath.replace('\\', '/') 
    
    return '/static/placeholder.png' 

# --- نماذج قاعدة البيانات (Models) ---

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    products = db.relationship('Product', backref='category', lazy=True)

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=True)
    reviewer_name = db.Column(db.String(100), default='Anonymous')
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'rating': self.rating,
            'comment': self.comment,
            'reviewer_name': self.reviewer_name,
            'date_posted': self.date_posted.strftime('%Y-%m-%d')
        }

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=True)
    stock = db.Column(db.Integer, default=0)
    image_url = db.Column(db.String(200), default='/static/placeholder.png') 
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    reviews = db.relationship('Review', backref='product', lazy='dynamic') 

    def get_rating_info(self):
        avg_rating = db.session.query(func.avg(Review.rating)).filter(Review.product_id == self.id).scalar()
        review_count = self.reviews.count()
        
        return {
            'average': round(avg_rating, 2) if avg_rating else 0,
            'count': review_count
        }

    def to_dict(self):
        rating_info = self.get_rating_info() 
        return {
            'id': self.id,
            'name': self.name,
            'price': self.price,
            'description': self.description,
            'stock': self.stock,
            'image_url': self.image_url,
            'category_name': self.category.name if self.category else 'N/A',
            'rating': rating_info
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

# --- وظائف مساعدة للسلة والمفضلة (كما هي) ---

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

def get_favorites_details():
    favorites_ids = [int(id) for id in session.get('favorites', [])]
    favorite_products = Product.query.filter(Product.id.in_(favorites_ids)).all()
    
    return [p.to_dict() for p in favorite_products]

# --- مسارات المتجر العام (Frontend Routes) ---

@app.route('/')
def home():
    categories = Category.query.all()
    favorites_count = len(session.get('favorites', []))
    return render_template('index.html', categories=categories, favorites_count=favorites_count) 

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    reviews = Review.query.filter_by(product_id=product.id).order_by(Review.date_posted.desc()).all()
    rating_info = product.get_rating_info() 
    
    return render_template('product_detail.html', product=product, reviews=reviews, rating_info=rating_info)

# --- مسارات التقييمات (Review Routes) ---

@app.route('/review/submit/<int:product_id>', methods=['POST'])
def submit_review(product_id):
    rating = request.form.get('rating', type=int)
    comment = request.form.get('comment')
    reviewer_name = request.form.get('reviewer_name') or 'Anonymous'

    if rating is None or not 1 <= rating <= 5:
        flash('يجب اختيار تقييم من 1 إلى 5 نجوم.', 'error')
        return redirect(url_for('product_detail', product_id=product_id))

    new_review = Review(
        product_id=product_id,
        rating=rating,
        comment=comment,
        reviewer_name=reviewer_name
    )
    
    db.session.add(new_review)
    db.session.commit()
    flash('تم إرسال تقييمك بنجاح!', 'success')
    return redirect(url_for('product_detail', product_id=product_id))

# --- مسارات API (لجلب البيانات بواسطة JavaScript) ---

@app.route('/api/products')
def get_products():
    query = request.args.get('query') 
    category_id = request.args.get('category_id')
    
    products_query = Product.query
    
    if query:
        products_query = products_query.filter(or_(
            Product.name.contains(query),
            Product.description.contains(query)
        ))
    
    if category_id and category_id.isdigit():
        products_query = products_query.filter_by(category_id=int(category_id))

    products = products_query.all()
    return jsonify([p.to_dict() for p in products])

# --- مسارات المفضلة (Wishlist Routes) ---

@app.route('/favorites')
def favorites_view(): # 📌 تم التأكد من وجود هذه الدالة
    favorite_products = get_favorites_details()
    return render_template('favorites.html', products=favorite_products)

@app.route('/favorites/toggle/<int:product_id>')
def toggle_favorite(product_id):
    if 'favorites' not in session:
        session['favorites'] = []
    
    favorites_list = [int(id) for id in session['favorites']]
    
    product = Product.query.get(product_id)
    if not product:
        return jsonify({"message": "المنتج غير موجود"}), 404

    if product_id in favorites_list:
        session['favorites'].remove(product_id)
        message = f"تم إزالة {product.name} من المفضلة."
        is_added = False
    else:
        session['favorites'].append(product_id)
        message = f"تم إضافة {product.name} إلى المفضلة."
        is_added = True
        
    session.modified = True
    
    return jsonify({
        "message": message, 
        "count": len(session['favorites']),
        "is_added": is_added
    })
    
# --- مسارات السلة (Cart, Checkout) (كما هي) ---

@app.route('/cart/add/<int:product_id>')
def add_to_cart(product_id):
    product = Product.query.get(product_id)
    if not product or product.stock <= 0:
        return jsonify({"message": "المنتج غير متوفر أو نفد مخزونه"}), 404

    cart = session.get('cart', {})
    product_id_str = str(product_id)
    
    current_quantity = cart.get(product_id_str, 0)
    if current_quantity >= product.stock:
        return jsonify({"message": f"لا يمكن إضافة المزيد، الحد الأقصى للمخزون هو {product.stock}"}), 400
        
    cart[product_id_str] = current_quantity + 1
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
        flash("السلة فارغة، يرجى إضافة منتجات أولاً.")
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
            product = Product.query.get(item['product_id'])
            if product and product.stock >= item['quantity']:
                product.stock -= item['quantity']
            
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

# --- مسارات الإدارة والمصادقة (Admin & Auth Routes) (كما هي) ---

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login(): 
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['is_admin'] = True
            return redirect(url_for('admin_panel', message='مرحباً أيها المشرف!'))
        else:
            return render_template('admin_login.html', error='خطأ في اسم المستخدم أو كلمة المرور.')
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('is_admin', None)
    return redirect(url_for('admin_login'))

@app.route('/admin')
def admin_panel():
    if session.get('is_admin') != True:
        return redirect(url_for('admin_login'))

    products = Product.query.all()
    orders = Order.query.order_by(Order.date_placed.desc()).all() 
    categories = Category.query.all()
    success_message = request.args.get('message')
    
    return render_template('admin.html', products=products, orders=orders, categories=categories, success_message=success_message) 

# ... (بقية مسارات الإدارة: add_product, edit_product, delete_product, update_order_status, order_details, add_category, delete_category) ...

@app.route('/add_product', methods=['POST'])
def add_product():
    if session.get('is_admin') != True: return redirect(url_for('admin_login'))
    
    name = request.form.get('name')
    price = request.form.get('price')
    description = request.form.get('description')
    stock = request.form.get('stock')
    category_id = request.form.get('category_id')

    image_file = request.files.get('image_file') 
    image_url = '/static/placeholder.png' 
    
    if image_file and image_file.filename != '':
        image_url = handle_image_upload(image_file)


    if not all([name, price, stock, category_id]):
        return redirect(url_for('admin_panel', message='خطأ: يجب توفير جميع الحقول المطلوبة للمنتج!'))
    
    try:
        new_product = Product(
            name=name,
            price=float(price),
            description=description,
            stock=int(stock),
            image_url=image_url, 
            category_id=int(category_id)
        )
        db.session.add(new_product)
        db.session.commit()
        return redirect(url_for('admin_panel', message=f'تمت إضافة المنتج {name} بنجاح!'))
    except ValueError:
        return redirect(url_for('admin_panel', message='خطأ: يجب أن يكون السعر ورصيد المخزون أرقاماً صحيحة!'))


@app.route('/edit_product/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    if session.get('is_admin') != True: return redirect(url_for('admin_login'))
    product = Product.query.get_or_404(product_id)
    categories = Category.query.all()

    if request.method == 'POST':
        try:
            image_file = request.files.get('image_file')
            image_url = product.image_url 

            if image_file and image_file.filename != '':
                image_url = handle_image_upload(image_file)
            
            product.name = request.form.get('name')
            product.price = float(request.form.get('price'))
            product.description = request.form.get('description')
            product.stock = int(request.form.get('stock'))
            product.image_url = image_url 
            product.category_id = int(request.form.get('category_id'))
            
            db.session.commit()
            return redirect(url_for('admin_panel', message=f'تم تعديل المنتج {product.name} بنجاح!'))
        except:
            db.session.rollback()
            return redirect(url_for('admin_panel', message='خطأ أثناء التعديل!'))

    return render_template('edit_product.html', product=product, categories=categories)


@app.route('/delete_product/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    if session.get('is_admin') != True: return redirect(url_for('admin_login'))
    product = Product.query.get_or_404(product_id)
    product_name = product.name
    
    db.session.delete(product)
    db.session.commit()
    
    return redirect(url_for('admin_panel', message=f'تم حذف المنتج {product_name} بنجاح.'))

@app.route('/update_order_status/<int:order_id>', methods=['POST'])
def update_order_status(order_id):
    if session.get('is_admin') != True: return redirect(url_for('admin_login'))
    order = Order.query.get_or_404(order_id)
    new_status = request.form.get('status')
    
    if new_status in ['New', 'Processing', 'Shipped', 'Delivered']:
        order.status = new_status
        db.session.commit()
        return redirect(url_for('admin_panel', message=f'تم تحديث حالة الطلب #{order_id} إلى {new_status}.'))
        
    return "حالة طلب غير صالحة", 400

@app.route('/order_details/<int:order_id>')
def order_details(order_id):
    if session.get('is_admin') != True: return redirect(url_for('admin_login'))
    order = Order.query.get_or_404(order_id)
    return render_template('order_details.html', order=order)

@app.route('/add_category', methods=['POST'])
def add_category():
    if session.get('is_admin') != True: return redirect(url_for('admin_login'))
    name = request.form.get('name')
    if name:
        new_category = Category(name=name)
        db.session.add(new_category)
        db.session.commit()
        return redirect(url_for('admin_panel', message=f'تمت إضافة الفئة {name} بنجاح.'))
    return redirect(url_for('admin_panel', message='خطأ: يجب توفير اسم للفئة.'))

@app.route('/delete_category/<int:category_id>', methods=['POST'])
def delete_category(category_id):
    if session.get('is_admin') != True: return redirect(url_for('admin_login'))
    category = Category.query.get_or_404(category_id)
    
    if category.products:
        return redirect(url_for('admin_panel', message=f'لا يمكن حذف الفئة {category.name}. يجب نقل أو حذف المنتجات المرتبطة أولاً.'))
    
    db.session.delete(category)
    db.session.commit()
    return redirect(url_for('admin_panel', message=f'تم حذف الفئة {category.name} بنجاح.'))


# --- التشغيل والإعداد الأولي ---

if __name__ == '__main__':
    with app.app_context():
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])
            
        db.create_all() 
        
        # إضافة بيانات تجريبية (فئات)
        if Category.query.count() == 0:
            tech = Category(name="Electronics")
            books = Category(name="Books")
            db.session.add_all([tech, books])
            db.session.commit()

        # إضافة بيانات تجريبية (منتجات)
        if Product.query.count() == 0:
            tech = Category.query.filter_by(name="Electronics").first()
            books = Category.query.filter_by(name="Books").first()

            if tech and books:
                db.session.add(Product(name="Laptop Pro", price=1200.0, description="Powerful machine for development and gaming.", stock=10, image_url="/static/placeholder.png", category_id=tech.id))
                db.session.add(Product(name="Wireless Mouse", price=25.0, description="Ergonomic design with high precision sensor.", stock=50, image_url="/static/placeholder.png", category_id=tech.id))
                db.session.add(Product(name="Python Guide", price=50.0, description="Beginner's guide to Python and Flask.", stock=20, image_url="/static/placeholder.png", category_id=books.id))
                db.session.commit()
    
    app.run(debug=True, host='0.0.0.0', port=5000)
