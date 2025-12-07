document.addEventListener('DOMContentLoaded', () => {
    const productsContainer = document.getElementById('products-container');
    const cartDisplay = document.getElementById('cart-display');
    const cartCountSpan = document.getElementById('cart-count');
    const cartItemsList = document.getElementById('cart-items-list');
    const cartTotalStrong = document.getElementById('cart-total');
    const viewCartBtn = document.getElementById('view-cart-btn');
    const clearCartBtn = document.getElementById('clear-cart-btn');

    // جلب المنتجات وعرضها
    async function fetchProducts() {
        try {
            const response = await fetch('/products');
            const products = await response.json();
            displayProducts(products);
        } catch (error) {
            productsContainer.innerHTML = '<h2>عفواً، حدث خطأ في تحميل المنتجات.</h2>';
            console.error('Error fetching products:', error);
        }
    }

    // جلب بيانات السلة وعرضها
    async function fetchCartAndDisplay() {
        try {
            const response = await fetch('/cart');
            const cartData = await response.json();
            
            cartCountSpan.textContent = cartData.count;
            displayCart(cartData);
        } catch (error) {
            console.error('Error fetching cart:', error);
        }
    }

    // إضافة منتج للسلة
    async function addToCart(productId) {
        try {
            const response = await fetch(`/cart/add/${productId}`);
            const data = await response.json();
            
            cartCountSpan.textContent = data.cart_count;
            alert(data.message); 
            
            if (!cartDisplay.classList.contains('hidden')) {
                fetchCartAndDisplay();
            }
        } catch (error) {
            console.error('Error adding to cart:', error);
            alert('حدث خطأ أثناء إضافة المنتج للسلة.');
        }
    }
    
    // تفريغ السلة
    async function clearCart() {
        if (!confirm('هل أنت متأكد من تفريغ سلة المشتريات؟')) return;
        
        try {
            const response = await fetch('/cart/clear');
            const data = await response.json();
            
            cartCountSpan.textContent = data.cart_count;
            cartItemsList.innerHTML = '<p>السلة فارغة حالياً.</p>';
            cartTotalStrong.textContent = '$0.00';
            alert(data.message);
        } catch (error) {
            console.error('Error clearing cart:', error);
        }
    }

    // عرض المنتجات وتفعيل أزرار الإضافة للسلة
    function displayProducts(products) {
        productsContainer.innerHTML = '<h2>منتجاتنا:</h2>';
        
        const productsGrid = document.createElement('div');
        productsGrid.className = 'products-grid';

        products.forEach(product => {
            const productCard = document.createElement('div');
            productCard.className = 'product-card';
            
            productCard.innerHTML = `
                <h3>${product.name}</h3>
                <p>${product.description}</p>
                <p><strong>السعر: $${product.price}</strong></p>
                <button class="add-to-cart-btn" data-id="${product.id}">أضف إلى السلة</button>
            `;
            productsGrid.appendChild(productCard);
        });
        
        productsContainer.appendChild(productsGrid);
        
        document.querySelectorAll('.add-to-cart-btn').forEach(button => {
            button.addEventListener('click', (e) => {
                const productId = e.target.getAttribute('data-id');
                addToCart(productId);
            });
        });
    }

    // عرض محتويات السلة
    function displayCart(cartData) {
        cartItemsList.innerHTML = '';
        if (cartData.items.length === 0) {
            cartItemsList.innerHTML = '<p>السلة فارغة حالياً.</p>';
        } else {
            const list = document.createElement('ul');
            cartData.items.forEach(item => {
                const listItem = document.createElement('li');
                listItem.textContent = `${item.name} x ${item.quantity} - $${item.item_total.toFixed(2)}`;
                list.appendChild(listItem);
            });
            cartItemsList.appendChild(list);

            // إضافة زر إنهاء الطلب
            const checkoutBtn = document.createElement('a');
            checkoutBtn.href = '/checkout';
            checkoutBtn.textContent = 'الانتقال لإنهاء الطلب';
            checkoutBtn.style.cssText = 'display: block; text-align: center; margin-top: 20px; padding: 10px; background-color: #ff9800; color: white; text-decoration: none; border-radius: 5px;';
            cartDisplay.appendChild(checkoutBtn);
        }
        
        cartTotalStrong.textContent = `$${cartData.total.toFixed(2)}`;
    }
    
    // مستمعات الأحداث
    viewCartBtn.addEventListener('click', () => {
        cartDisplay.classList.toggle('hidden');
        if (!cartDisplay.classList.contains('hidden')) {
            fetchCartAndDisplay();
        }
    });
    
    clearCartBtn.addEventListener('click', clearCart);

    // التحميل الأولي
    fetchProducts();
    fetchCartAndDisplay();
});
