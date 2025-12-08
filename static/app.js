document.addEventListener('DOMContentLoaded', () => {
    // --- 1. تحديد العناصر الرئيسية في DOM ---

    const productsContainer = document.querySelector('#products-container .products-grid');
    const cartCountElement = document.getElementById('cart-count');
    const favoritesCountElement = document.getElementById('favorites-count');
    const cartDisplay = document.getElementById('cart-display');
    const cartItemsList = document.getElementById('cart-items-list');
    const cartTotalElement = document.getElementById('cart-total');
    const searchInput = document.getElementById('search-input');
    const filterButtons = document.querySelectorAll('.filter-btn');
    const viewCartButton = document.getElementById('view-cart-btn');
    const clearCartButton = document.getElementById('clear-cart-btn');

    // --- 2. حالة التطبيق (Global State) ---

    // استخدام Flask Session لإدارة السلة والمفضلة (نقوم بتحديثها عبر الـ API)
    // لكن للاعتماد على حالة مبدئية عند التحميل، نعتمد على ما يجلبه الـ API
    
    // سنستخدم وظيفة مساعدة لجلب حالة المفضلة والسلة عند التحميل:

    async function fetchInitialState() {
        // جلب حالة السلة
        const cartResponse = await fetch('/cart');
        const cartData = await cartResponse.json();
        cartCountElement.textContent = cartData.count;

        // جلب حالة المفضلة
        const favResponse = await fetch('/favorites');
        const favData = await favResponse.json();
        favoritesCountElement.textContent = favData.length;

        // تخزين قائمة IDs المفضلة محليًا للمقارنة في عرض المنتجات
        const favoritesIds = favData.items ? favData.items.map(p => p.id) : favData.map(p => p.id);
        sessionStorage.setItem('current_favorites', JSON.stringify(favoritesIds));
    }


    // --- 3. وظائف جلب وعرض البيانات ---

    /**
     * جلب المنتجات من الخادم باستخدام مسار الـ API المصحح: /api/products
     * @param {string} categoryId - فلتر حسب ID الفئة.
     * @param {string} searchTerm - فلتر حسب مصطلح البحث.
     */
    async function fetchProducts(categoryId = '', searchTerm = '') {
        productsContainer.innerHTML = '<p style="width: 100%; text-align: center;">جاري تحميل المنتجات...</p>';
        
        // 🛑 المسار المصحح الذي يحل مشكلة الـ 404
        let url = `/api/products?query=${encodeURIComponent(searchTerm)}`;
        if (categoryId) {
            url += `&category_id=${categoryId}`;
        }
        
        try {
            const response = await fetch(url);

            if (!response.ok) {
                // عرض رسالة الخطأ في حال كانت الاستجابة غير ناجحة (مثل 500)
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            
            const products = await response.json();
            renderProducts(products);

        } catch (error) {
            console.error('Error fetching products:', error);
            productsContainer.innerHTML = '<h2 style="width: 100%; color: red;">عفواً، حدث خطأ أثناء تحميل المنتجات.</h2>';
        }
    }


    /**
     * عرض قائمة المنتجات في واجهة المستخدم.
     */
    function renderProducts(products) {
        productsContainer.innerHTML = '';
        if (products.length === 0) {
            productsContainer.innerHTML = '<p style="width: 100%;">لا توجد منتجات تطابق المعايير المختارة.</p>';
            return;
        }
        
        const favoritesIds = JSON.parse(sessionStorage.getItem('current_favorites') || '[]');

        products.forEach(product => {
            const productCard = document.createElement('div');
            productCard.className = 'product-card';
            
            // حالة زر المفضلة
            const isFavorite = favoritesIds.includes(product.id);
            const favIcon = isFavorite ? '❤️ إزالة' : '🤍 أضف للمفضلة';
            const favClass = isFavorite ? 'remove-favorite-btn' : 'add-favorite-btn';

            productCard.innerHTML = `
                <a href="/product/${product.id}"> 
                    <img src="${product.image_url}" alt="${product.name}" onerror="this.src='/static/placeholder.png'">
                </a>
                <h3><a href="/product/${product.id}">${product.name}</a></h3>
                <p style="font-size: 0.9em; color: #6c757d;">الفئة: ${product.category_name}</p>
                <p><strong>السعر: ${product.price}</strong></p>
                <p style="font-size: 0.9em;">
                    ${product.stock > 0 ? `متوفر: ${product.stock}` : 'نفد المخزون'}
                </p>
                
                <div class="product-actions">
                    ${product.stock > 0 
                        ? `<button class="add-to-cart-btn" data-id="${product.id}">أضف إلى السلة</button>`
                        : `<button disabled style="background-color: #6c757d; cursor: not-allowed;">نفد المخزون</button>`
                    }
                    
                    <button class="toggle-favorite-btn ${favClass}" data-id="${product.id}">
                        ${favIcon}
                    </button>
                </div>
            `;
            productsContainer.appendChild(productCard);
        });

        // يجب إضافة مستمعي الأحداث هنا بعد بناء البطاقات
        setupProductEventListeners();
    }

    /**
     * عرض محتويات السلة بعد جلبها من الـ API.
     */
    async function fetchCartAndRender() {
        try {
            const response = await fetch('/cart');
            const cartData = await response.json();
            
            const items = cartData.items;
            const total = cartData.total;

            cartCountElement.textContent = cartData.count;

                cartItemsList.innerHTML = '';
            if (items.length === 0) {
                cartItemsList.innerHTML = '<p>سلة المشتريات فارغة.</p>';
                cartTotalElement.textContent = '$0.00';
                return;
            }

            items.forEach(item => {
                const itemDiv = document.createElement('div');
                itemDiv.className = 'cart-item';
                const itemTotalDisplay = item.item_total_display || (item.item_total ? `$${item.item_total.toFixed(2)}` : '$0.00');
                itemDiv.innerHTML = `
                    <span>${item.name} (x${item.quantity})</span>
                    <span>${itemTotalDisplay}</span>
                    `;
                cartItemsList.appendChild(itemDiv);
            });

            cartTotalElement.textContent = (cartData.total_display || (total ? `$${total.toFixed(2)}` : '$0.00'));

        } catch (error) {
            console.error('Error fetching cart:', error);
            alert('حدث خطأ أثناء جلب محتويات السلة.');
        }
    }


    // --- 4. وظائف الإجراءات (Actions) ---

    /**
     * إضافة منتج إلى السلة عبر الـ API.
     */
    async function addToCart(productId) {
        try {
            const response = await fetch(`/cart/add/${productId}`);
            const data = await response.json();
            
            if (response.ok) {
                alert(data.message);
                cartCountElement.textContent = data.cart_count;
            } else {
                alert(`فشل الإضافة: ${data.message}`);
            }

        } catch (error) {
            console.error('Error adding to cart:', error);
            alert('فشل الاتصال بالخادم لإضافة المنتج.');
        }
    }

    /**
     * تفريغ السلة عبر الـ API.
     */
    async function clearCart() {
        if (!confirm('هل أنت متأكد من تفريغ سلة المشتريات؟')) return;

        try {
            const response = await fetch('/cart/clear');
            const data = await response.json();

            alert(data.message);
            cartCountElement.textContent = data.cart_count;
            
            // تحديث العرض إذا كانت السلة مفتوحة
            if (!cartDisplay.classList.contains('hidden')) {
                fetchCartAndRender();
            }

        } catch (error) {
            console.error('Error clearing cart:', error);
            alert('فشل الاتصال بالخادم لتفريغ السلة.');
        }
    }

    /**
     * التبديل بين إضافة وإزالة منتج من المفضلة عبر الـ API.
     */
    async function toggleFavorite(productId, buttonElement) {
        try {
            const response = await fetch(`/favorites/toggle/${productId}`);
            const data = await response.json();
            
            if (response.ok) {
                alert(data.message);
                favoritesCountElement.textContent = data.count;

                // تحديث حالة الزر مرئيًا
                if (data.is_added) {
                    buttonElement.textContent = '❤️ إزالة';
                    buttonElement.classList.remove('add-favorite-btn');
                    buttonElement.classList.add('remove-favorite-btn');
                } else {
                    buttonElement.textContent = '🤍 أضف للمفضلة';
                    buttonElement.classList.remove('remove-favorite-btn');
                    buttonElement.classList.add('add-favorite-btn');
                }

                // تحديث حالة المفضلة المحلية
                await fetchInitialState();

            } else {
                alert(`فشل العملية: ${data.message}`);
            }

        } catch (error) {
            console.error('Error toggling favorite:', error);
            alert('فشل الاتصال بالخادم لتحديث المفضلة.');
        }
    }


    // --- 5. وظيفة إعداد مستمعي الأحداث ---

    /**
     * إعداد مستمعي الأحداث لأزرار السلة والمفضلة بعد عرض المنتجات.
     */
    function setupProductEventListeners() {
        document.querySelectorAll('.add-to-cart-btn').forEach(button => {
            button.addEventListener('click', (e) => {
                const productId = e.target.getAttribute('data-id');
                addToCart(productId);
            });
        });

        document.querySelectorAll('.toggle-favorite-btn').forEach(button => {
            button.addEventListener('click', (e) => {
                const productId = e.target.getAttribute('data-id');
                toggleFavorite(productId, e.target);
            });
        });
    }

    // --- 6. وظيفة التهيئة (Initialization) ---

    viewCartButton.addEventListener('click', () => {
        fetchCartAndRender(); // جلب البيانات قبل العرض
        cartDisplay.classList.toggle('hidden');
    });

    clearCartButton.addEventListener('click', clearCart);

    // معالج أزرار الفلترة حسب الفئة
    filterButtons.forEach(button => {
        button.addEventListener('click', () => {
            filterButtons.forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');

            const categoryId = button.dataset.id;
            const searchTerm = searchInput.value;
            fetchProducts(categoryId, searchTerm);
        });
    });

    // معالج زر البحث
    document.getElementById('search-button').addEventListener('click', () => {
        const searchTerm = searchInput.value;
        const activeFilter = document.querySelector('.filter-btn.active');
        const categoryId = activeFilter ? activeFilter.dataset.id : '';
        fetchProducts(categoryId, searchTerm);
    });

    // تشغيل وظائف التهيئة والبدء في جلب البيانات
    fetchInitialState();
    fetchProducts();
});
