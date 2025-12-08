from flask import Flask, jsonify, render_template, request, session, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime
from sqlalchemy import or_, func
import os
from werkzeug.utils import secure_filename

# ===== إعدادات التطبيق =====
ADMIN_USERNAME_DEFAULT = 'hossam_admin'
ADMIN_PASSWORD_DEFAULT = 'strong_password123'
LOW_STOCK_THRESHOLD = 5

# إعدادات رفع الملفات
UPLOAD_FOLDER = 'static/product_images'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# ===== تكوين Flask و SQLAlchemy =====
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_super_secret_key_12345'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# إعدادات العملات (قاعدة الأسعار مخزنة افتراضياً بوحدة USD)
app.config['CURRENCY_RATES'] = {
    'USD': 1.0,
    'SAR': 3.75
}
app.config['CURRENCY_SYMBOLS'] = {
    'USD': '$',
    'SAR': 'ر.س'
}
app.config['CURRENCY_POSITION'] = {
    'USD': 'prefix',
    'SAR': 'suffix'
}
app.config['DEFAULT_CURRENCY'] = 'USD'

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# ===== نماذج قاعدة البيانات =====

class AdminUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    
    # الصلاحيات
    can_manage_products = db.Column(db.Boolean, default=False)
    can_manage_orders = db.Column(db.Boolean, default=False)
    can_manage_reviews = db.Column(db.Boolean, default=False)
    can_manage_admins = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)

    def verify_password(self, password):
        return self.password_hash == password

    def set_password(self, password):
        self.password_hash = password


class AdminActivity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('admin_user.id'), nullable=False)
    action = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    products = db.relationship('Product', backref='category', lazy=True)


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
        avg_rating_result = db.session.query(func.avg(Review.rating)).filter(Review.product_id == self.id).scalar()
        avg_rating = avg_rating_result if avg_rating_result is not None else 0
        review_count = self.reviews.count()
        
        return {
            'average': round(avg_rating, 2),
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

# ===== وظائف مساعدة =====

def allowed_file(filename):
    """التحقق من أن الامتداد مسموح به."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def handle_image_upload(file):
    """حفظ ملف الصورة وإرجاع مساره النسبي."""
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])
            
        file.save(filepath)
        return '/' + filepath.replace('\\', '/')
    
    return '/static/placeholder.png'


def get_current_currency():
    return session.get('currency', app.config.get('DEFAULT_CURRENCY', 'USD'))


def convert_price(amount, to_currency):
    try:
        rate = app.config['CURRENCY_RATES'].get(to_currency, 1.0)
    except Exception:
        rate = 1.0
    return amount * rate


def format_price(amount):
    cur = get_current_currency()
    converted = convert_price(amount, cur)
    symbol = app.config['CURRENCY_SYMBOLS'].get(cur, '')
    pos = app.config['CURRENCY_POSITION'].get(cur, 'prefix')
    if pos == 'prefix':
        return f"{symbol}{converted:.2f}"
    return f"{converted:.2f} {symbol}"


@app.context_processor
def inject_currency_helpers():
    return {
        'format_price': format_price,
        'current_currency': get_current_currency
    }


@app.route('/set_currency/<currency_code>')
def set_currency(currency_code):
    if currency_code in app.config.get('CURRENCY_RATES', {}):
        session['currency'] = currency_code
    # If called via AJAX, return JSON; otherwise redirect back
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.args.get('ajax') == '1':
        return jsonify({'currency': session.get('currency')})
    return redirect(request.referrer or url_for('home'))


@app.route('/admin/pricing_data')
def admin_pricing_data():
    # Return formatted prices for products, orders and stats (used by admin UI for dynamic updates)
    if 'admin_id' not in session:
        return jsonify({'error': 'unauthenticated'}), 401

    # products
    products = Product.query.all()
    products_data = []
    for p in products:
        try:
            products_data.append({'id': p.id, 'price_display': format_price(p.price)})
        except Exception:
            products_data.append({'id': p.id, 'price_display': p.price})

    # orders
    orders = Order.query.all()
    orders_data = []
    for o in orders:
        try:
            orders_data.append({'id': o.id, 'total_display': format_price(o.total_price)})
        except Exception:
            orders_data.append({'id': o.id, 'total_display': o.total_price})

    # stats: compute total_sales similar to admin_panel
    total_sales_result = db.session.query(func.sum(Order.total_price)).filter_by(status='Delivered').scalar()
    total_sales = round(total_sales_result or 0, 2)
    try:
        total_sales_display = format_price(total_sales)
    except Exception:
        total_sales_display = total_sales

    return jsonify({
        'products': products_data,
        'orders': orders_data,
        'stats': {'total_sales_display': total_sales_display}
    })


def get_cart_details():
    """يحصل على تفاصيل سلة المشتريات من الجلسة."""
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
    """يحصل على تفاصيل المنتجات المفضلة من الجلسة."""
    favorites_ids = [int(id) for id in session.get('favorites', [])]
    favorite_products = Product.query.filter(Product.id.in_(favorites_ids)).all()
    
    return [p.to_dict() for p in favorite_products]

# ===== مسارات المتجر العام =====

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
    result = []
    for p in products:
        d = p.to_dict()
        # include both raw price and formatted price according to session currency
        try:
            d['price_raw'] = p.price
            d['price'] = format_price(p.price)
        except Exception:
            d['price_raw'] = p.price
            d['price'] = p.price
        result.append(d)
    return jsonify(result)

# ===== مسارات التقييمات =====

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


@app.route('/delete_review/<int:review_id>', methods=['POST'])
def delete_review(review_id):
    """مسار حذف التقييمات من لوحة المشرف."""
    if session.get('permissions', {}).get('reviews') != True:
        flash('ليس لديك صلاحية لإدارة التقييمات.', 'error')
        return redirect(url_for('admin_panel'))
        
    review = Review.query.get_or_404(review_id)
    db.session.delete(review)
    db.session.commit()
    flash('تم حذف التقييم بنجاح.', 'success')
    return redirect(url_for('admin_panel'))


@app.route('/reset_product_reviews/<int:product_id>', methods=['POST'])
def reset_product_reviews(product_id):
    """مسار إعادة تعيين جميع التقييمات لمنتج محدد."""
    if session.get('permissions', {}).get('reviews') != True:
        flash('ليس لديك صلاحية لإدارة التقييمات.', 'error')
        return redirect(url_for('admin_panel'))
        
    product = Product.query.get_or_404(product_id)
    
    Review.query.filter_by(product_id=product_id).delete()
    db.session.commit()
    
    flash(f'تمت إعادة تعيين جميع تقييمات المنتج {product.name} بنجاح.', 'warning')
    return redirect(url_for('admin_panel'))

# ===== مسارات المفضلة =====

@app.route('/favorites')
def favorites_view():
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

# ===== مسارات السلة =====

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
    # أضف تمثيلات الأسعار المحوّلة/المنسقة لكل عنصر وإجمالي السلة
    for it in cart_items:
        try:
            it['price_display'] = format_price(it.get('price', 0))
            it['item_total_display'] = format_price(it.get('item_total', 0))
        except Exception:
            it['price_display'] = it.get('price', 0)
            it['item_total_display'] = it.get('item_total', 0)

    try:
        total_display = format_price(total_price)
    except Exception:
        total_display = total_price

    return jsonify({
        'items': cart_items,
        'total': total_price,
        'total_display': total_display,
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

# ===== مسارات الإدارة والمصادقة =====

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = AdminUser.query.filter_by(username=username).first()
        
        if user and user.verify_password(password) and user.is_active:
            session['admin_id'] = user.id
            session['username'] = user.username
            session['permissions'] = {
                'products': user.can_manage_products,
                'orders': user.can_manage_orders,
                'reviews': user.can_manage_reviews,
                'admins': user.can_manage_admins
            }
            flash(f'مرحباً {user.username}، تم تسجيل الدخول بنجاح!', 'success')
            return redirect(url_for('admin_panel'))
        else:
            flash('خطأ في اسم المستخدم أو كلمة المرور.', 'error')
            return render_template('admin_login.html')
            
    return render_template('admin_login.html')


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_id', None)
    session.pop('username', None)
    session.pop('permissions', None)
    return redirect(url_for('admin_login'))


@app.route('/admin')
def admin_panel():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
        
    current_permissions = session.get('permissions', {})
    
    products = Product.query.all()
    orders = Order.query.order_by(Order.date_placed.desc()).all()
    categories = Category.query.all()
    all_reviews = Review.query.order_by(Review.date_posted.desc()).all()
    
    total_sales_result = db.session.query(func.sum(Order.total_price)).filter_by(status='Delivered').scalar()
    total_sales = round(total_sales_result or 0, 2)
    new_orders_count = Order.query.filter_by(status='New').count()
    low_stock_products = Product.query.filter(Product.stock <= LOW_STOCK_THRESHOLD).all()

    sales_labels = []
    sales_data = []
    for i in range(11, -1, -1):
        month_date = datetime.now()
        for _ in range(i):
            if month_date.month == 1:
                month_date = month_date.replace(year=month_date.year - 1, month=12)
            else:
                month_date = month_date.replace(month=month_date.month - 1)
        month_str = month_date.strftime('%Y-%m')
        sales_labels.append(month_str)
        month_sales = db.session.query(func.sum(Order.total_price)).filter(
            func.strftime('%Y-%m', Order.date_placed) == month_str,
            Order.status == 'Delivered'
        ).scalar() or 0
        sales_data.append(round(month_sales, 2))
    
    stats = {
        'total_sales': total_sales,
        'new_orders_count': new_orders_count,
        'low_stock_count': len(low_stock_products),
        'sales_labels': sales_labels,
        'sales_data': sales_data
    }
    
    admin_users = AdminUser.query.all()

    return render_template(
        'admin.html',
        products=products,
        orders=orders,
        categories=categories,
        all_reviews=all_reviews,
        stats=stats,
        low_stock_products=low_stock_products,
        admin_users=admin_users,
        permissions=current_permissions
    )


@app.route('/manage_admins', methods=['GET'])
def manage_admins():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    current_admin = AdminUser.query.get(session['admin_id'])
    if not current_admin or not current_admin.can_manage_admins:
        flash('ليس لديك صلاحية إدارة المشرفين', 'danger')
        return redirect(url_for('admin_panel'))
    admins = AdminUser.query.all()
    activities_raw = AdminActivity.query.order_by(AdminActivity.timestamp.desc()).limit(20).all()
    activities = []
    for act in activities_raw:
        admin = AdminUser.query.get(act.admin_id)
        activities.append({
            'timestamp': act.timestamp,
            'admin_name': admin.username if admin else f'ID {act.admin_id}',
            'action': act.action
        })
    return render_template('manage_admins.html', admins=admins, activities=activities)


@app.route('/add_admin', methods=['POST'])
def add_admin():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    current_admin = AdminUser.query.get(session['admin_id'])
    if not current_admin or not current_admin.can_manage_admins:
        flash('ليس لديك صلاحية إضافة مشرفين', 'danger')
        return redirect(url_for('manage_admins'))
    username = request.form.get('username')
    admins = AdminUser.query.order_by(AdminUser.username).all()

    # فلترة النشاطات عبر معلمات GET
    q = AdminActivity.query
    admin_filter = request.args.get('admin_id')
    action_filter = request.args.get('action')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    try:
        page = int(request.args.get('page', 1))
    except ValueError:
        page = 1
    per_page = 20

    if admin_filter:
        try:
            q = q.filter(AdminActivity.admin_id == int(admin_filter))
        except ValueError:
            pass
    if action_filter:
        q = q.filter(AdminActivity.action.ilike(f"%{action_filter}%"))
    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from)
            q = q.filter(AdminActivity.timestamp >= dt_from)
        except Exception:
            pass
    if date_to:
        try:
            dt_to = datetime.fromisoformat(date_to)
            q = q.filter(AdminActivity.timestamp <= dt_to)
        except Exception:
            pass

    total_count = q.count()
    offset = (page - 1) * per_page
    activities_raw = q.order_by(AdminActivity.timestamp.desc()).offset(offset).limit(per_page).all()

    activities = []
    for act in activities_raw:
        admin = AdminUser.query.get(act.admin_id)
        activities.append({
            'timestamp': act.timestamp,
            'admin_name': admin.username if admin else f'ID {act.admin_id}',
            'action': act.action
        })

    has_next = offset + per_page < total_count
    has_prev = page > 1

    return render_template('manage_admins.html', admins=admins, activities=activities,
                           filters={'admin_id': admin_filter or '', 'action': action_filter or '',
                                    'date_from': date_from or '', 'date_to': date_to or '',
                                    'page': page},
                           pagination={'has_next': has_next, 'has_prev': has_prev, 'page': page})


@app.route('/manage_admins/export')
def manage_admins_export():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    current_admin = AdminUser.query.get(session['admin_id'])
    if not current_admin or not current_admin.can_manage_admins:
        flash('ليس لديك صلاحية تصدير سجلات المشرفين', 'danger')
        return redirect(url_for('manage_admins'))

    q = AdminActivity.query
    admin_filter = request.args.get('admin_id')
    action_filter = request.args.get('action')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')

    if admin_filter:
        try:
            q = q.filter(AdminActivity.admin_id == int(admin_filter))
        except ValueError:
            pass
    if action_filter:
        q = q.filter(AdminActivity.action.ilike(f"%{action_filter}%"))
    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from)
            q = q.filter(AdminActivity.timestamp >= dt_from)
        except Exception:
            pass
    if date_to:
        try:
            dt_to = datetime.fromisoformat(date_to)
            q = q.filter(AdminActivity.timestamp <= dt_to)
        except Exception:
            pass

    activities = q.order_by(AdminActivity.timestamp.desc()).all()

    import io, csv
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['timestamp', 'admin', 'action'])
    for act in activities:
        admin = AdminUser.query.get(act.admin_id)
        writer.writerow([act.timestamp.isoformat(), admin.username if admin else act.admin_id, act.action])

    resp = app.response_class(output.getvalue(), mimetype='text/csv')
    resp.headers['Content-Disposition'] = 'attachment; filename=admin_activities.csv'
    return resp
    new_admin = AdminUser(
        username=username,
        password_hash=password,
        can_manage_products=can_manage_products,
        can_manage_orders=can_manage_orders,
        can_manage_reviews=can_manage_reviews,
        can_manage_admins=can_manage_admins
    )
    db.session.add(new_admin)
    db.session.commit()
    flash('تمت إضافة المشرف بنجاح', 'success')
    return redirect(url_for('manage_admins'))


@app.route('/update_admin_permissions', methods=['POST'])
def update_admin_permissions():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    current_admin = AdminUser.query.get(session['admin_id'])
    if not current_admin or not current_admin.can_manage_admins:
        flash('ليس لديك صلاحية تعديل صلاحيات المشرفين', 'danger')
        return redirect(url_for('manage_admins'))
    admin_id = request.form.get('admin_id')
    admin = AdminUser.query.get(admin_id)
    if not admin:
        flash('المشرف غير موجود', 'warning')
        return redirect(url_for('manage_admins'))
    return render_template('edit_admin_permissions.html', admin=admin)


@app.route('/save_admin_permissions', methods=['POST'])
def save_admin_permissions():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    current_admin = AdminUser.query.get(session['admin_id'])
    if not current_admin or not current_admin.can_manage_admins:
        flash('ليس لديك صلاحية تعديل صلاحيات المشرفين', 'danger')
        return redirect(url_for('manage_admins'))
    admin_id = request.form.get('admin_id')
    admin = AdminUser.query.get(admin_id)
    if not admin:
        flash('المشرف غير موجود', 'warning')
        return redirect(url_for('manage_admins'))
    admin.can_manage_products = bool(request.form.get('can_manage_products'))
    admin.can_manage_orders = bool(request.form.get('can_manage_orders'))
    admin.can_manage_reviews = bool(request.form.get('can_manage_reviews'))
    admin.can_manage_admins = bool(request.form.get('can_manage_admins'))
    db.session.commit()
    flash('تم تحديث الصلاحيات بنجاح', 'success')
    return redirect(url_for('manage_admins'))


@app.route('/delete_admin', methods=['POST'])
def delete_admin():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    current_admin = AdminUser.query.get(session['admin_id'])
    if not current_admin or not current_admin.can_manage_admins:
        flash('ليس لديك صلاحية حذف المشرفين', 'danger')
        return redirect(url_for('manage_admins'))
    admin_id = request.form.get('admin_id')
    admin = AdminUser.query.get(admin_id)
    if not admin:
        flash('المشرف غير موجود', 'warning')
        return redirect(url_for('manage_admins'))
    if admin.id == current_admin.id:
        flash('لا يمكنك حذف نفسك!', 'danger')
        return redirect(url_for('manage_admins'))
    db.session.delete(admin)
    db.session.commit()
    flash('تم حذف المشرف بنجاح', 'success')
    return redirect(url_for('manage_admins'))


@app.route('/toggle_admin_active', methods=['POST'])
def toggle_admin_active():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    current_admin = AdminUser.query.get(session['admin_id'])
    if not current_admin or not current_admin.can_manage_admins:
        flash('ليس لديك صلاحية تغيير حالة المشرفين', 'danger')
        return redirect(url_for('manage_admins'))
    admin_id = request.form.get('admin_id')
    admin = AdminUser.query.get(admin_id)
    if not admin:
        flash('المشرف غير موجود', 'warning')
        return redirect(url_for('manage_admins'))
    admin.is_active = not admin.is_active
    db.session.commit()
    flash(f"تم تغيير حالة المشرف {admin.username} إلى {'مفعل' if admin.is_active else 'معطل'}", 'info')
    return redirect(url_for('manage_admins'))


@app.route('/change_admin_password', methods=['POST'])
def change_admin_password():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    admin = AdminUser.query.get(session['admin_id'])
    old_password = request.form.get('old_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    if not admin.verify_password(old_password):
        flash('كلمة المرور الحالية غير صحيحة', 'danger')
        return redirect(url_for('admin_panel'))
    if new_password != confirm_password:
        flash('كلمة المرور الجديدة غير متطابقة', 'warning')
        return redirect(url_for('admin_panel'))
    if len(new_password) < 6:
        flash('كلمة المرور الجديدة يجب أن تكون 6 أحرف على الأقل', 'warning')
        return redirect(url_for('admin_panel'))
    admin.set_password(new_password)
    db.session.commit()
    flash('تم تغيير كلمة المرور بنجاح', 'success')
    return redirect(url_for('admin_panel'))

# ===== مسارات إدارة المنتجات =====

@app.route('/add_product', methods=['POST'])
def add_product():
    """مسار إضافة منتج جديد."""
    if session.get('permissions', {}).get('products') != True:
        flash('ليس لديك صلاحية لإدارة المنتجات.', 'error')
        return redirect(url_for('admin_panel'))
    
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
        flash('خطأ: يجب توفير جميع الحقول المطلوبة للمنتج!', 'error')
        return redirect(url_for('admin_panel'))
    
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
        flash(f'✅ تم إضافة المنتج {name} بنجاح! (إشعار إداري)', 'info')
        return redirect(url_for('admin_panel'))
    except ValueError:
        flash('خطأ: يجب أن يكون السعر ورصيد المخزون أرقاماً صحيحة!', 'error')
        return redirect(url_for('admin_panel'))


@app.route('/edit_product/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    """مسار تعديل منتج موجود."""
    if session.get('permissions', {}).get('products') != True:
        flash('ليس لديك صلاحية لإدارة المنتجات.', 'error')
        return redirect(url_for('admin_panel'))
        
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
            flash(f'تم تعديل المنتج {product.name} بنجاح!', 'success')
            return redirect(url_for('admin_panel'))
        except:
            db.session.rollback()
            flash('خطأ أثناء التعديل!', 'error')
            return redirect(url_for('admin_panel'))

    return render_template('edit_product.html', product=product, categories=categories)


@app.route('/delete_product/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    """مسار حذف منتج."""
    if session.get('permissions', {}).get('products') != True:
        flash('ليس لديك صلاحية لإدارة المنتجات.', 'error')
        return redirect(url_for('admin_panel'))
        
    product = Product.query.get_or_404(product_id)
    product_name = product.name
    
    db.session.delete(product)
    db.session.commit()
    
    flash(f'⚠️ تم حذف المنتج {product_name} بنجاح! (إشعار إداري)', 'warning')
    return redirect(url_for('admin_panel'))

# ===== مسارات إدارة الفئات =====

@app.route('/add_category', methods=['POST'])
def add_category():
    """مسار إضافة فئة جديدة."""
    if session.get('permissions', {}).get('products') != True:
        flash('ليس لديك صلاحية لإدارة الفئات.', 'error')
        return redirect(url_for('admin_panel'))
        
    name = request.form.get('name')
    if name:
        new_category = Category(name=name)
        db.session.add(new_category)
        db.session.commit()
        flash(f'تمت إضافة الفئة {name} بنجاح.', 'success')
        return redirect(url_for('admin_panel'))
    flash('خطأ: يجب توفير اسم للفئة.', 'error')
    return redirect(url_for('admin_panel'))


@app.route('/delete_category/<int:category_id>', methods=['POST'])
def delete_category(category_id):
    """مسار حذف فئة."""
    if session.get('permissions', {}).get('products') != True:
        flash('ليس لديك صلاحية لإدارة الفئات.', 'error')
        return redirect(url_for('admin_panel'))
        
    category = Category.query.get_or_404(category_id)
    
    if category.products:
        flash(f'لا يمكن حذف الفئة {category.name}. يجب نقل أو حذف المنتجات المرتبطة أولاً.', 'error')
        return redirect(url_for('admin_panel'))
    
    db.session.delete(category)
    db.session.commit()
    flash(f'تم حذف الفئة {category.name} بنجاح.', 'success')
    return redirect(url_for('admin_panel'))

# ===== مسارات إدارة الطلبات =====

@app.route('/update_order_status/<int:order_id>', methods=['POST'])
def update_order_status(order_id):
    """مسار تحديث حالة الطلب."""
    if session.get('permissions', {}).get('orders') != True:
        flash('ليس لديك صلاحية لإدارة الطلبات.', 'error')
        return redirect(url_for('admin_panel'))
        
    order = Order.query.get_or_404(order_id)
    new_status = request.form.get('status')
    
    if new_status in ['New', 'Processing', 'Shipped', 'Delivered']:
        order.status = new_status
        db.session.commit()
        flash(f'تم تحديث حالة الطلب #{order_id} إلى {new_status}.', 'success')
        return redirect(url_for('admin_panel'))
        
    flash("حالة طلب غير صالحة", 'error')
    return redirect(url_for('admin_panel'))


@app.route('/order_details/<int:order_id>')
def order_details(order_id):
    """عرض تفاصيل الطلب."""
    if session.get('permissions', {}).get('orders') != True:
        flash('ليس لديك صلاحية لعرض الطلبات.', 'error')
        return redirect(url_for('admin_panel'))
        
    order = Order.query.get_or_404(order_id)
    return render_template('order_details.html', order=order)

# ===== التشغيل والإعداد الأولي =====

if __name__ == '__main__':
    with app.app_context():
        # التأكد من مجلد الرفع
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])
            
        db.create_all()

        # الإعداد الأولي: إضافة المشرف الرئيسي
        if AdminUser.query.count() == 0:
            initial_admin = AdminUser(
                username=ADMIN_USERNAME_DEFAULT,
                can_manage_products=True,
                can_manage_orders=True,
                can_manage_reviews=True,
                can_manage_admins=True
            )
            initial_admin.set_password(ADMIN_PASSWORD_DEFAULT)
            db.session.add(initial_admin)
            db.session.commit()
            print(f"تم إنشاء المشرف الرئيسي: {ADMIN_USERNAME_DEFAULT}")
            
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
