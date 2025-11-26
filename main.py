from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import os
from datetime import datetime
import secrets
import requests
from utils.sheets import db

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', secrets.token_hex(32))

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', 'your-google-client-id')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', 'your-google-client-secret')

def generate_user_id():
    return f"user_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

# Routes
@app.route('/')
def index():
    try:
        available_books = db.get_available_books()
        latest_books = available_books[-3:] if len(available_books) >= 3 else available_books
        latest_books.reverse()
        return render_template('index.html', latest_books=latest_books)
    except Exception as e:
        print(f"❌ Error in index route: {e}")
        return render_template('index.html', latest_books=[])

@app.route('/books')
def books():
    try:
        available_books = db.get_available_books()
        print(f"📚 /books route: Showing {len(available_books)} books")
        return render_template('search.html', books=available_books)
    except Exception as e:
        print(f"❌ Error in books route: {e}")
        return render_template('search.html', books=[])

@app.route('/checkout')
def checkout():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('checkout.html')

@app.route('/cart')
def cart_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('cart.html')

@app.route('/login')
def login():
    return render_template('login.html', google_client_id=GOOGLE_CLIENT_ID)

@app.route('/manage')
def manage():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('manage.html')

# Authentication API
@app.route('/api/google-login', methods=['POST'])
def api_google_login():
    try:
        data = request.json
        token = data.get('credential')
        
        if not token:
            return jsonify({'success': False, 'error': 'Missing authentication token'})
        
        try:
            if token.startswith('ey'):
                payload_part = token.split('.')[1]
                import base64
                import json
                
                padding = 4 - len(payload_part) % 4
                if padding != 4:
                    payload_part += '=' * padding
                
                payload = json.loads(base64.b64decode(payload_part))
                
                email = payload.get('email', '').lower()
                name = payload.get('name', '')
                user_id = payload.get('sub', '')
                
                allowed_domains = ['gmail.com', 'googlemail.com', 'google.com']
                email_domain = email.split('@')[-1] if '@' in email else ''
                
                if email_domain not in allowed_domains:
                    return jsonify({
                        'success': False, 
                        'error': 'Only Google email accounts are allowed'
                    })
                
                session['user_id'] = user_id
                session['user_email'] = email
                session['user_name'] = name
                session['user_picture'] = payload.get('picture', '')
                
                print(f"✅ User logged in: {name} ({email})")
                
                return jsonify({
                    'success': True, 
                    'message': 'Login successful!',
                    'user': {
                        'id': user_id,
                        'email': email,
                        'name': name,
                        'picture': session['user_picture']
                    }
                })
            else:
                return jsonify({'success': False, 'error': 'Invalid token format'})
                
        except Exception as e:
            print(f"❌ JWT decode error: {e}")
            return jsonify({'success': False, 'error': 'Invalid authentication token'})
        
    except Exception as e:
        print(f"❌ Google login error: {e}")
        return jsonify({'success': False, 'error': 'Authentication failed'})

@app.route('/api/user')
def api_user():
    if 'user_id' in session:
        return jsonify({
            'logged_in': True,
            'user': {
                'id': session['user_id'],
                'email': session['user_email'],
                'name': session['user_name'],
                'picture': session.get('user_picture', '')
            }
        })
    return jsonify({'logged_in': False})

@app.route('/api/logout')
def api_logout():
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out'})

# Cart APIs
@app.route('/api/add-to-cart', methods=['POST'])
def add_to_cart():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Please login first'}), 401
    
    try:
        data = request.json
        book_id = data.get('book_id')
        
        if not book_id:
            return jsonify({'success': False, 'error': 'Book ID required'}), 400
        
        if 'cart' not in session:
            session['cart'] = []
        
        cart = session['cart']
        existing_item = next((item for item in cart if item['book_id'] == book_id), None)
        
        if existing_item:
            existing_item['quantity'] += 1
        else:
            book = db.get_book_by_id(book_id)
            if not book:
                return jsonify({'success': False, 'error': 'Book not found'}), 404
            
            cart_item = {
                'book_id': book_id,
                'title': book.get('title'),
                'author': book.get('author'),
                'price': float(book.get('price', 0)),
                'condition': book.get('condition'),
                'quantity': 1
            }
            cart.append(cart_item)
        
        session['cart'] = cart
        session.modified = True
        
        return jsonify({
            'success': True, 
            'message': 'Book added to cart!',
            'cart_count': len(cart)
        })
        
    except Exception as e:
        print(f"❌ Error adding to cart: {e}")
        return jsonify({'success': False, 'error': 'Server error'}), 500

@app.route('/api/get-cart')
def get_cart():
    if 'user_id' not in session:
        return jsonify({'error': 'Please login first'}), 401
    
    try:
        cart = session.get('cart', [])
        total = sum(item['price'] * item['quantity'] for item in cart)
        return jsonify({'items': cart, 'total': total, 'count': len(cart)})
    except Exception as e:
        print(f"❌ Error getting cart: {e}")
        return jsonify({'items': [], 'total': 0, 'count': 0})

@app.route('/api/update-cart-item', methods=['POST'])
def update_cart_item():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Please login first'}), 401
    
    try:
        data = request.json
        book_id = data.get('book_id')
        quantity = data.get('quantity')
        
        if not book_id or quantity is None:
            return jsonify({'success': False, 'error': 'Book ID and quantity required'}), 400
        
        cart = session.get('cart', [])
        item = next((item for item in cart if item['book_id'] == book_id), None)
        
        if item:
            if quantity <= 0:
                cart.remove(item)
            else:
                item['quantity'] = quantity
            
            session['cart'] = cart
            session.modified = True
            total = sum(item['price'] * item['quantity'] for item in cart)
            
            return jsonify({'success': True, 'cart_count': len(cart), 'total': total})
        else:
            return jsonify({'success': False, 'error': 'Item not found in cart'}), 404
            
    except Exception as e:
        print(f"❌ Error updating cart: {e}")
        return jsonify({'success': False, 'error': 'Server error'}), 500

@app.route('/api/remove-from-cart', methods=['POST'])
def remove_from_cart():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Please login first'}), 401
    
    try:
        data = request.json
        book_id = data.get('book_id')
        
        if not book_id:
            return jsonify({'success': False, 'error': 'Book ID required'}), 400
        
        cart = session.get('cart', [])
        cart = [item for item in cart if item['book_id'] != book_id]
        session['cart'] = cart
        session.modified = True
        
        return jsonify({'success': True, 'message': 'Item removed from cart', 'cart_count': len(cart)})
            
    except Exception as e:
        print(f"❌ Error removing from cart: {e}")
        return jsonify({'success': False, 'error': 'Server error'}), 500

# Order APIs
@app.route('/api/place-order', methods=['POST'])
def place_order():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Please login first'}), 401
    
    try:
        data = request.json
        book_id = data.get('book_id')
        full_name = data.get('full_name')
        phone_number = data.get('phone_number')
        address_line1 = data.get('address_line1')
        address_line2 = data.get('address_line2', '')
        address_city = data.get('address_city')
        address_state = data.get('address_state')
        address_zip = data.get('address_zip')
        payment_method = data.get('payment_method')
        
        if not all([book_id, full_name, phone_number, address_line1, address_city, address_state, address_zip, payment_method]):
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        book = db.get_book_by_id(book_id)
        if not book:
            return jsonify({'success': False, 'error': 'Book not found'}), 404
        
        # Check if book is available and in stock
        if book.get('status', '').lower() != 'available':
            return jsonify({'success': False, 'error': 'Book is no longer available'}), 400
        
        if book.get('stock_quantity', 0) <= 0:
            return jsonify({'success': False, 'error': 'Book is out of stock'}), 400
        
        order_id = f"ORD_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        order_data = {
            'order_id': order_id,
            'user_id': session['user_id'],
            'user_email': session['user_email'],
            'book_id': book_id,
            'book_title': book.get('title'),
            'quantity': 1,
            'total_price': float(book.get('price', 0)),
            'full_name': full_name,
            'phone': phone_number,
            'address_line1': address_line1,
            'address_line2': address_line2,
            'city': address_city,
            'state': address_state,
            'zip_code': address_zip,
            'payment_method': payment_method,
            'status': 'Pending',
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        success = db.add_order(order_data)
        
        if not success:
            return jsonify({'success': False, 'error': 'Failed to save order'}), 500
        
        # Decrease stock quantity instead of marking as Sold
        db.decrease_book_stock(book_id, quantity=1)
        
        user_data = {
            'user_id': session['user_id'],
            'email': session['user_email'],
            'name': full_name,
            'phone': phone_number,
            'address_line1': address_line1,
            'address_line2': address_line2,
            'city': address_city,
            'state': address_state,
            'zip_code': address_zip,
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        db.save_user_info(user_data)
        
        session['cart'] = []
        session.modified = True
        
        print(f"✅ Order placed: {order_id} - {book.get('title')} - ₹{book.get('price')}")
        
        return jsonify({
            'success': True, 
            'message': 'Order placed successfully!',
            'order_id': order_id
        })
        
    except Exception as e:
        print(f"❌ Error placing order: {e}")
        return jsonify({'success': False, 'error': 'Server error'}), 500

@app.route('/api/place-order-from-cart', methods=['POST'])
def place_order_from_cart():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Please login first'}), 401
    
    try:
        data = request.json
        required_fields = ['full_name', 'phone_number', 'address_line1', 'address_city', 'address_state', 'address_zip', 'payment_method']
        missing = [f for f in required_fields if not data.get(f)]
        
        if missing:
            return jsonify({'success': False, 'error': f'Missing: {", ".join(missing)}'}), 400
        
        cart = session.get('cart', [])
        
        if not cart:
            return jsonify({'success': False, 'error': 'Cart is empty'}), 400
        
        orders_placed = []
        failed_books = []
        
        for cart_item in cart:
            book_id = cart_item.get('book_id')
            quantity = cart_item.get('quantity', 1)
            
            if not book_id:
                failed_books.append("Invalid book ID")
                continue
            
            book = db.get_book_by_id(book_id)
            if not book:
                failed_books.append(f"Book {book_id} not found")
                continue
            
            # Check availability and stock
            if book.get('status', '').lower() != 'available':
                failed_books.append(f"{book.get('title')} not available")
                continue
            
            if book.get('stock_quantity', 0) < quantity:
                failed_books.append(f"{book.get('title')} - only {book.get('stock_quantity', 0)} in stock")
                continue
            
            order_id = f"ORD_{datetime.now().strftime('%Y%m%d%H%M%S')}_{book_id}"
            total_price = float(book.get('price', 0)) * quantity
            
            order_data = {
                'order_id': order_id,
                'user_id': session['user_id'],
                'user_email': session['user_email'],
                'book_id': book_id,
                'book_title': book.get('title'),
                'quantity': quantity,
                'total_price': total_price,
                'full_name': data.get('full_name'),
                'phone': data.get('phone_number'),
                'address_line1': data.get('address_line1'),
                'address_line2': data.get('address_line2', ''),
                'city': data.get('address_city'),
                'state': data.get('address_state'),
                'zip_code': data.get('address_zip'),
                'payment_method': data.get('payment_method'),
                'status': 'Pending',
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            if db.add_order(order_data):
                # Decrease stock by quantity ordered
                db.decrease_book_stock(book_id, quantity=quantity)
                orders_placed.append({
                    'order_id': order_id,
                    'book_title': book.get('title'),
                    'total': total_price
                })
            else:
                failed_books.append(f"Failed to order {book.get('title')}")
        
        user_data = {
            'user_id': session['user_id'],
            'email': session['user_email'],
            'name': data.get('full_name'),
            'phone': data.get('phone_number'),
            'address_line1': data.get('address_line1'),
            'address_line2': data.get('address_line2', ''),
            'city': data.get('address_city'),
            'state': data.get('address_state'),
            'zip_code': data.get('address_zip'),
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        db.save_user_info(user_data)
        
        if orders_placed:
            session['cart'] = []
            session.modified = True
        
        if failed_books:
            return jsonify({
                'success': True, 
                'message': f'Ordered {len(orders_placed)} items. Some failed.',
                'orders_placed': orders_placed,
                'failed_items': failed_books
            })
        else:
            return jsonify({
                'success': True, 
                'message': f'Order placed for {len(orders_placed)} items!',
                'orders_placed': orders_placed
            })
        
    except Exception as e:
        print(f"❌ Error placing cart order: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/get-orders')
def get_orders():
    if 'user_id' not in session:
        return jsonify({'error': 'Please login first'}), 401
    
    try:
        user_orders = db.get_user_orders(session['user_email'])
        return jsonify(user_orders)
    except Exception as e:
        print(f"❌ Error getting orders: {e}")
        return jsonify([])

@app.route('/api/get-user-address')
def get_user_address():
    if 'user_id' not in session:
        return jsonify({'error': 'Please login first'}), 401
    
    try:
        user_info = db.get_user_info(session['user_email'])
        return jsonify(user_info or {})
    except Exception as e:
        print(f"❌ Error getting user address: {e}")
        return jsonify({})

@app.route('/api/get-book/<book_id>')
def get_book(book_id):
    try:
        book = db.get_book_by_id(book_id)
        
        if book:
            return jsonify(book)
        else:
            return jsonify({'error': 'Book not found'}), 404
            
    except Exception as e:
        print(f"❌ Error getting book: {e}")
        return jsonify({'error': 'Server error'}), 500

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 SWAPLY SERVER STARTING")
    print("="*60)
    print("📚 Home: http://localhost:5000")
    print("🛒 Shop: http://localhost:5000/books")
    print("💾 Database Status:")
    print(f"   - Using: {'Google Sheets' if not db.using_memory_storage else 'Memory Storage'}")
    print(f"   - Books loaded: {len(db.get_all_books())}")
    print(f"   - Available books: {len(db.get_available_books())}")
    print("="*60 + "\n")
    app.run(debug=True, host='0.0.0.0', port=5000)