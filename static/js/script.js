// Mobile menu functionality
document.addEventListener('DOMContentLoaded', function() {
    const mobileMenuButton = document.getElementById('mobile-menu-button');
    const mobileMenu = document.getElementById('mobile-menu');

    if (mobileMenuButton && mobileMenu) {
        mobileMenuButton.addEventListener('click', function() {
            const isHidden = mobileMenu.classList.contains('hidden');
            
            if (isHidden) {
                mobileMenu.classList.remove('hidden');
                mobileMenu.classList.add('block');
            } else {
                mobileMenu.classList.add('hidden');
                mobileMenu.classList.remove('block');
            }
        });
    }

    // Close mobile menu when clicking outside
    document.addEventListener('click', function(event) {
        if (!event.target.closest('#mobile-menu') && !event.target.closest('#mobile-menu-button')) {
            if (mobileMenu && !mobileMenu.classList.contains('hidden')) {
                mobileMenu.classList.add('hidden');
                mobileMenu.classList.remove('block');
            }
        }
    });
});

// Toast notification function
function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `fixed top-4 right-4 p-4 rounded-lg shadow-lg text-white font-semibold z-50 ${
        type === 'success' ? 'bg-emerald-500' : 'bg-red-500'
    }`;
    toast.textContent = message;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.remove();
    }, 3000);
}

function logout() {
    fetch('/api/logout')
        .then(() => window.location.href = '/');
}

// Cart functionality
function updateCartCount() {
    if (!document.getElementById('cartCount')) return;
    
    fetch('/api/get-cart')
        .then(response => response.json())
        .then(data => {
            const cartCount = document.getElementById('cartCount');
            if (data.count > 0) {
                cartCount.textContent = data.count;
                cartCount.classList.remove('hidden');
            } else {
                cartCount.classList.add('hidden');
            }
        })
        .catch(error => {
            console.error('Error updating cart count:', error);
        });
}

function addToCart(bookId) {
    console.log("🛒 Adding to cart:", bookId);
    
    fetch('/api/add-to-cart', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            book_id: bookId
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast(data.message, 'success');
            updateCartCount();
        } else {
            showToast(data.error, 'error');
        }
    })
    .catch(error => {
        console.error('Error adding to cart:', error);
        showToast('Network error. Please try again.', 'error');
    });
}

// Update cart count when page loads
document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('cartCount')) {
        updateCartCount();
    }
});