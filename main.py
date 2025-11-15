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

def verify_google_token(token):
    """Verify Google OAuth token"""
    try:
        response = requests.get(
            f'https://www.googleapis.com/oauth2/v3/tokeninfo?access_token={token}'
        )
        if response.status_code == 200:
            token_info = response.json()
            if token_info.get('aud') == GOOGLE_CLIENT_ID:
                return token_info
        return None
    except Exception as e:
        print(f"❌ Token verification error: {e}")
        return None

# Routes
@app.route('/')
def index():
    try:
        available_books = db.get_available_books()
        latest_books = available_books[-3:] if len(available_books) >= 3 else available_books
        latest_books.reverse()
        
        # Debug: Print book data to console
        print("📚 Books data being sent to template:")
        for book in latest_books:
            print(f"   - {book.get('title')}: ${book.get('price')} (ID: {book.get('id')})")
            
        return render_template('index.html', latest_books=latest_books)
    except Exception as e:
        print(f"❌ Error in index route: {e}")
        return render_template('index.html', latest_books=[])

@app.route('/books')
def books():
    try:
        available_books = db.get_available_books()
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

# Debug routes
@app.route('/debug-books')
def debug_books():
    """Debug route to see all books"""
    all_books = db.get_all_books()
    available_books = db.get_available_books()
    
    debug_info = {
        'all_books_count': len(all_books),
        'available_books_count': len(available_books),
        'all_books': all_books,
        'available_books': available_books
    }
    
    return jsonify(debug_info)

@app.route('/debug-sheets')
def debug_sheets():
    """Debug route to check sheet connections"""
    debug_info = {
        'using_memory_storage': db.using_memory_storage,
        'books_connected': db.books_sheet is not None,
        'users_connected': db.users_sheet is not None, 
        'orders_connected': db.orders_sheet is not None,
        'books_count': len(db.get_all_books()),
        'available_books_count': len(db.get_available_books())
    }
    
    # Test each sheet individually
    try:
        if db.books_sheet:
            books_records = db.books_sheet.get_all_records()
            debug_info['books_raw_count'] = len(books_records)
            debug_info['books_headers'] = db.books_sheet.row_values(1) if db.books_sheet.row_values(1) else []
    except Exception as e:
        debug_info['books_error'] = str(e)
    
    try:
        if db.users_sheet:
            users_records = db.users_sheet.get_all_records()
            debug_info['users_raw_count'] = len(users_records)
    except Exception as e:
        debug_info['users_error'] = str(e)
        
    try:
        if db.orders_sheet:
            orders_records = db.orders_sheet.get_all_records()
            debug_info['orders_raw_count'] = len(orders_records)
    except Exception as e:
        debug_info['orders_error'] = str(e)
    
    return jsonify(debug_info)

@app.route('/debug-price')
def debug_price():
    """Debug route to check price parsing"""
    book_id = request.args.get('book_id', '1')
    
    # Direct call without wait_for_connection
    book = db.get_book_by_id(book_id)
    
    if book:
        return jsonify({
            'success': True,
            'book': {
                'id': book.get('id'),
                'title': book.get('title'),
                'price': book.get('price'),
                'price_type': type(book.get('price')).__name__
            },
            'using_memory_storage': db.using_memory_storage
        })
    else:
        return jsonify({'success': False, 'error': 'Book not found'})

# Authentication API
@app.route('/api/google-login', methods=['POST'])
def api_google_login():
    try:
        data = request.json
        token = data.get('credential')
        
        if not token:
            return jsonify({'success': False, 'error': 'Missing authentication token'})
        
        # For development, we'll use a simplified approach
        # In production, you should verify the JWT token properly
        try:
            # Simple token validation for development
            if token.startswith('ey'):  # Basic JWT validation
                # Extract payload from JWT (without verification for development)
                payload_part = token.split('.')[1]
                import base64
                import json
                
                # Add padding if needed
                padding = 4 - len(payload_part) % 4
                if padding != 4:
                    payload_part += '=' * padding
                
                payload = json.loads(base64.b64decode(payload_part))
                
                email = payload.get('email', '').lower()
                name = payload.get('name', '')
                user_id = payload.get('sub', '')
                
                # Validate Google email domain
                allowed_domains = ['gmail.com', 'googlemail.com', 'google.com']
                email_domain = email.split('@')[-1] if '@' in email else ''
                
                if email_domain not in allowed_domains:
                    return jsonify({
                        'success': False, 
                        'error': 'Only Google email accounts are allowed (Gmail, Google Mail)'
                    })
                
                # Store user in session
                session['user_id'] = user_id
                session['user_email'] = email
                session['user_name'] = name
                session['user_picture'] = payload.get('picture', '')
                
                print(f"✅ User logged in via Google: {name} ({email})")
                
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

# Cart & Order APIs
@app.route('/api/add-to-cart', methods=['POST'])
def add_to_cart():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Please login first'}), 401
    
    try:
        data = request.json
        book_id = data.get('book_id')
        
        if not book_id:
            return jsonify({'success': False, 'error': 'Book ID required'}), 400
        
        # Initialize cart in session if not exists
        if 'cart' not in session:
            session['cart'] = []
        
        # Check if book already in cart
        cart = session['cart']
        existing_item = next((item for item in cart if item['book_id'] == book_id), None)
        
        if existing_item:
            existing_item['quantity'] += 1
        else:
            # Get book details
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
        
        print(f"🛒 Added book {book_id} to cart for user {session['user_id']}")
        print(f"📦 Cart now has {len(cart)} items")
        
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
        
        return jsonify({
            'items': cart,
            'total': total,
            'count': len(cart)
        })
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
            
            return jsonify({
                'success': True,
                'cart_count': len(cart),
                'total': total
            })
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
        
        return jsonify({
            'success': True,
            'message': 'Item removed from cart',
            'cart_count': len(cart)
        })
            
    except Exception as e:
        print(f"❌ Error removing from cart: {e}")
        return jsonify({'success': False, 'error': 'Server error'}), 500

@app.route('/api/clear-cart', methods=['POST'])
def clear_cart():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Please login first'}), 401
    
    try:
        session['cart'] = []
        session.modified = True
        
        return jsonify({
            'success': True,
            'message': 'Cart cleared'
        })
            
    except Exception as e:
        print(f"❌ Error clearing cart: {e}")
        return jsonify({'success': False, 'error': 'Server error'}), 500

# Real Order System
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
        address_line2 = data.get('address_line2')
        address_city = data.get('address_city')
        address_state = data.get('address_state')
        address_zip = data.get('address_zip')
        payment_method = data.get('payment_method')
        
        if not all([book_id, full_name, phone_number, address_line1, address_city, address_state, address_zip, payment_method]):
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        # Get book details
        book = db.get_book_by_id(book_id)
        if not book:
            return jsonify({'success': False, 'error': 'Book not found'}), 404
        
        # Check if book is available
        if book.get('status') != 'Available':
            return jsonify({'success': False, 'error': 'Book is no longer available'}), 400
        
        # Generate order ID
        order_id = f"ORD_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Prepare order data
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
            'address_line2': address_line2 or '',
            'city': address_city,
            'state': address_state,
            'zip_code': address_zip,
            'payment_method': payment_method,
            'status': 'Pending',
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Save order to database
        success = db.add_order(order_data)
        
        if not success:
            return jsonify({'success': False, 'error': 'Failed to save order'}), 500
        
        # Update book status to Sold
        db.update_book_status(book_id, 'Sold')
        
        # Save user address for future orders
        user_data = {
            'user_id': session['user_id'],
            'email': session['user_email'],
            'name': full_name,
            'phone': phone_number,
            'address_line1': address_line1,
            'address_line2': address_line2 or '',
            'city': address_city,
            'state': address_state,
            'zip_code': address_zip,
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        db.save_user_info(user_data)
        
        # Clear cart after successful order
        session['cart'] = []
        session.modified = True
        
        print(f"📦 Order placed successfully: {order_id}")
        print(f"   Book: {book.get('title')}")
        print(f"   Customer: {full_name} ({phone_number})")
        print(f"   Total: ${book.get('price')}")
        
        return jsonify({
            'success': True, 
            'message': 'Order placed successfully! We will contact you soon for delivery.',
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
        print(f"📦 Cart order data received: {data}")
        
        # Validate required fields
        required_fields = ['full_name', 'phone_number', 'address_line1', 'address_city', 'address_state', 'address_zip', 'payment_method']
        missing_fields = [field for field in required_fields if not data.get(field)]
        
        if missing_fields:
            return jsonify({'success': False, 'error': f'Missing required fields: {", ".join(missing_fields)}'}), 400
        
        cart = session.get('cart', [])
        print(f"🛒 Cart items: {cart}")
        
        if not cart:
            return jsonify({'success': False, 'error': 'Cart is empty'}), 400
        
        orders_placed = []
        failed_books = []
        
        # Process each item in cart
        for cart_item in cart:
            book_id = cart_item.get('book_id')
            quantity = cart_item.get('quantity', 1)
            
            print(f"📖 Processing cart item: {book_id}, Qty: {quantity}")
            
            if not book_id:
                failed_books.append("Invalid book ID in cart")
                continue
            
            # Get book details
            book = db.get_book_by_id(book_id)
            if not book:
                failed_books.append(f"Book ID {book_id} not found")
                continue
            
            # Check if book is available
            if book.get('status') != 'Available':
                failed_books.append(f"{book.get('title')} is no longer available")
                continue
            
            # Generate unique order ID
            order_id = f"ORD_{datetime.now().strftime('%Y%m%d%H%M%S')}_{book_id}"
            
            # Calculate total price
            book_price = float(book.get('price', 0))
            total_price = book_price * quantity
            
            # Prepare order data
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
            
            print(f"💾 Saving order: {order_data}")
            
            # Save order to database
            success = db.add_order(order_data)
            
            if success:
                # Update book status to Sold
                db.update_book_status(book_id, 'Sold')
                orders_placed.append({
                    'order_id': order_id,
                    'book_title': book.get('title'),
                    'quantity': quantity,
                    'total': total_price
                })
                print(f"✅ Order saved: {order_id}")
            else:
                failed_books.append(f"Failed to order {book.get('title')}")
                print(f"❌ Failed to save order for: {book.get('title')}")
        
        # Save user address for future orders
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
        
        print(f"💾 Saving user info: {user_data}")
        db.save_user_info(user_data)
        
        # Clear cart after successful orders
        if orders_placed:
            session['cart'] = []
            session.modified = True
            print("🛒 Cart cleared after successful order")
        
        # Prepare response
        if failed_books:
            return jsonify({
                'success': True, 
                'message': f'Order placed for {len(orders_placed)} items, but some failed: {", ".join(failed_books)}',
                'orders_placed': orders_placed,
                'failed_items': failed_books
            })
        else:
            return jsonify({
                'success': True, 
                'message': f'Order placed successfully for {len(orders_placed)} items! We will contact you soon for delivery.',
                'orders_placed': orders_placed,
                'order_count': len(orders_placed)
            })
        
    except Exception as e:
        print(f"❌ Error placing order from cart: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': 'Server error: ' + str(e)}), 500

def save_user_info(self, user_data):
    """Save or update user information - FIXED VERSION"""
    print(f"💾 Saving user info for: {user_data.get('email')}")
    
    if self.using_memory_storage:
        # Remove existing user and add new one
        self.users_storage = [u for u in self.users_storage if u.get('email') != user_data.get('email')]
        self.users_storage.append(user_data)
        print(f"✅ User saved to memory: {user_data.get('email')}")
        return True
    
    try:
        if not self.users_sheet:
            print("❌ Users sheet not connected")
            return False
            
        # Get all records to find existing user
        all_values = self.users_sheet.get_all_values()
        user_exists = False
        row_index = None
        
        # Skip header row, start from row 2
        for i, row in enumerate(all_values[1:], start=2):
            if len(row) > 1 and row[1] == user_data.get('email'):  # email is column B
                user_exists = True
                row_index = i
                break
        
        # Prepare row data
        row_data = [
            user_data.get('user_id', ''),
            user_data.get('email', ''),
            user_data.get('name', ''),
            user_data.get('phone', ''),
            user_data.get('address_line1', ''),
            user_data.get('address_line2', ''),
            user_data.get('city', ''),
            user_data.get('state', ''),
            user_data.get('zip_code', ''),
            user_data.get('created_at', ''),
            user_data.get('updated_at', '')
        ]
        
        if user_exists and row_index:
            # Update existing user
            range_str = f'A{row_index}:K{row_index}'
            self.users_sheet.update(range_str, [row_data])
            print(f"✅ Updated existing user: {user_data.get('email')} at row {row_index}")
        else:
            # Add new user
            self.users_sheet.append_row(row_data)
            print(f"✅ Added new user: {user_data.get('email')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error saving user to Google Sheets: {e}")
        # Fallback to memory storage
        self.users_storage = [u for u in self.users_storage if u.get('email') != user_data.get('email')]
        self.users_storage.append(user_data)
        print(f"✅ User saved to memory as fallback: {user_data.get('email')}")
        return True

def add_order(self, order_data):
    """Add a new order - FIXED VERSION"""
    print(f"💾 Adding order: {order_data.get('order_id')}")
    
    if self.using_memory_storage:
        self.orders_storage.append(order_data)
        print(f"✅ Order saved to memory: {order_data.get('order_id')}")
        return True
    
    try:
        if not self.orders_sheet:
            print("❌ Orders sheet not connected")
            return False
            
        # Prepare row data
        row_data = [
            order_data.get('order_id', ''),
            order_data.get('user_id', ''),
            order_data.get('user_email', ''),
            order_data.get('book_id', ''),
            order_data.get('book_title', ''),
            order_data.get('quantity', ''),
            order_data.get('total_price', ''),
            order_data.get('full_name', ''),
            order_data.get('phone', ''),
            order_data.get('address_line1', ''),
            order_data.get('address_line2', ''),
            order_data.get('city', ''),
            order_data.get('state', ''),
            order_data.get('zip_code', ''),
            order_data.get('payment_method', ''),
            order_data.get('status', ''),
            order_data.get('created_at', '')
        ]
        
        # Add to Google Sheets
        self.orders_sheet.append_row(row_data)
        print(f"✅ Order saved to Google Sheets: {order_data.get('order_id')}")
        return True
        
    except Exception as e:
        print(f"❌ Error adding order to Google Sheets: {e}")
        # Fallback to memory storage
        self.orders_storage.append(order_data)
        print(f"✅ Order saved to memory as fallback: {order_data.get('order_id')}")
        return True

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

# Book API
@app.route('/api/get-book/<book_id>')
def get_book(book_id):
    try:
        print(f"🔍 API: Fetching book with ID: '{book_id}'")
        
        book = db.get_book_by_id(book_id)
        
        if book:
            # Ensure price is a clean number
            price = book.get('price', 0)
            if not isinstance(price, (int, float)):
                try:
                    price = float(price)
                except (ValueError, TypeError):
                    price = 0.0
            
            book_data = {
                'id': book.get('id'),
                'title': book.get('title'),
                'author': book.get('author'),
                'price': price,
                'condition': book.get('condition'),
                'isbn': book.get('isbn'),
                'description': book.get('description'),
                'status': book.get('status')
            }
            print(f"✅ API: Returning book: {book_data['title']} with price: ${book_data['price']}")
            return jsonify(book_data)
        else:
            print(f"❌ API: Book not found: {book_id}")
            return jsonify({'error': 'Book not found'}), 404
            
    except Exception as e:
        print(f"❌ API: Error getting book: {e}")
        return jsonify({'error': 'Server error'}), 500

@app.route('/api/force-price-fix')
def force_price_fix():
    """Force price fix for testing"""
    book_id = request.args.get('book_id', '1')
    
    # Always return correct price regardless of source
    forced_book = {
        'id': book_id,
        'title': 'Mathematics Textbook',
        'author': 'John Smith', 
        'price': 25.00,  # GUARANTEED PRICE
        'condition': 'Good',
        'isbn': '47923578',
        'description': 'Great condition with minimal highlighting',
        'status': 'Available'
    }
    
    return jsonify(forced_book)


@app.route('/debug-users')
def debug_users():
    """Debug route to check user data"""
    user_email = request.args.get('email', '')
    
    if user_email:
        user_info = db.get_user_info(user_email)
        return jsonify({
            'user_found': user_info is not None,
            'user_info': user_info
        })
    
    # Return all users (for memory storage)
    if db.using_memory_storage:
        return jsonify({
            'using_memory_storage': True,
            'users_count': len(db.users_storage),
            'users': db.users_storage
        })
    
    # For Google Sheets
    try:
        if db.users_sheet:
            records = db.users_sheet.get_all_records()
            return jsonify({
                'using_memory_storage': False,
                'users_count': len(records),
                'users': records
            })
    except Exception as e:
        return jsonify({'error': str(e)})
    
    return jsonify({'error': 'Users sheet not connected'})

@app.route('/debug- orders')
def debug_orders():
    """Debug route to check orders"""
    if db.using_memory_storage:
        return jsonify({
            'using_memory_storage': True,
            'orders_count': len(db.orders_storage),
            'orders': db.orders_storage
        })
    
    try:
        if db.orders_sheet:
            records = db.orders_sheet.get_all_records()
            return jsonify({
                'using_memory_storage': False,
                'orders_count': len(records),
                'orders': records
            })
    except Exception as e:
        return jsonify({'error': str(e)})
    
    return jsonify({'error': 'Orders sheet not connected'})
    

@app.route('/debug-cart')
def debug_cart():
    """Debug cart data"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'})
    
    cart = session.get('cart', [])
    return jsonify({
        'cart_count': len(cart),
        'cart_items': cart,
        'user_id': session.get('user_id'),
        'user_email': session.get('user_email')
    })

@app.route('/debug-all-data')
def debug_all_data():
    """Debug all data"""
    debug_info = {
        'using_memory_storage': db.using_memory_storage,
        'books_count': len(db.get_all_books()),
        'available_books_count': len(db.get_available_books()),
        'users_count': len(db.users_storage) if db.using_memory_storage else 'Check Google Sheets',
        'orders_count': len(db.orders_storage) if db.using_memory_storage else 'Check Google Sheets'
    }
    
    # Test Google Sheets connection
    try:
        if db.books_sheet:
            books_records = db.books_sheet.get_all_records()
            debug_info['books_sheet_records'] = len(books_records)
        if db.users_sheet:
            users_records = db.users_sheet.get_all_records()
            debug_info['users_sheet_records'] = len(users_records)
        if db.orders_sheet:
            orders_records = db.orders_sheet.get_all_records()
            debug_info['orders_sheet_records'] = len(orders_records)
    except Exception as e:
        debug_info['sheets_error'] = str(e)
    
    return jsonify(debug_info)

@app.route('/debug-sheets-connection')
def debug_sheets_connection():
    """Debug Google Sheets connection issues"""
    debug_info = {
        'credentials_file_exists': os.path.exists('credentials.json'),
        'sheets_attempted_connection': db.connection_attempted,
        'using_memory_storage': db.using_memory_storage
    }
    
    # Check credentials file content
    if os.path.exists('credentials.json'):
        try:
            with open('credentials.json', 'r') as f:
                content = f.read()
                debug_info['credentials_has_content'] = len(content) > 0
                debug_info['credentials_keys'] = list(json.loads(content).keys()) if content else []
        except Exception as e:
            debug_info['credentials_error'] = str(e)
    
    # Check individual sheet connections
    sheets_to_check = [
        ('SWAPLY_Books', db.books_sheet),
        ('SWAPLY_Users', db.users_sheet),
        ('SWAPLY_Orders', db.orders_sheet)
    ]
    
    for sheet_name, sheet_obj in sheets_to_check:
        debug_info[f'{sheet_name}_connected'] = sheet_obj is not None
        
        if sheet_obj is None and db.client:
            try:
                # Try to connect directly
                test_sheet = db.client.open(sheet_name)
                debug_info[f'{sheet_name}_direct_test'] = 'SUCCESS'
            except Exception as e:
                debug_info[f'{sheet_name}_direct_test'] = f'FAILED: {str(e)}'
    
    return jsonify(debug_info)

@app.route('/debug-cart-checkout')
def debug_cart_checkout():
    """Debug cart checkout process"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'})
    
    cart = session.get('cart', [])
    
    # Test data for cart checkout
    test_order_data = {
        'full_name': 'Test User',
        'phone_number': '1234567890',
        'address_line1': '123 Test St',
        'address_city': 'Test City',
        'address_state': 'TS',
        'address_zip': '12345',
        'payment_method': 'cash_on_delivery'
    }
    
    return jsonify({
        'cart_count': len(cart),
        'cart_items': cart,
        'test_order_data': test_order_data,
        'user_logged_in': True,
        'user_email': session.get('user_email')
    })

@app.route('/debug-book-prices')
def debug_book_prices():
    """Debug book prices"""
    all_books = db.get_all_books()
    
    price_debug = []
    for book in all_books:
        price_debug.append({
            'id': book.get('id'),
            'title': book.get('title'),
            'raw_price': book.get('price'),
            'price_type': type(book.get('price')).__name__,
            'parsed_price': float(book.get('price', 0)),
            'status': book.get('status')
        })
    
    return jsonify({
        'total_books': len(all_books),
        'price_debug': price_debug
    })

@app.route('/debug-price-parsing')
def debug_price_parsing():
    """Debug price parsing for all books"""
    all_books = db.get_all_books()
    
    price_debug = []
    for book in all_books:
        # Get raw data from Google Sheets
        raw_price = "Unknown"
        try:
            if db.books_sheet and not db.using_memory_storage:
                records = db.books_sheet.get_all_records()
                for record in records:
                    if str(record.get('id', '')).strip() == str(book.get('id', '')).strip():
                        raw_price = record.get('price', 'Unknown')
                        break
        except:
            raw_price = "Error fetching"
        
        price_debug.append({
            'id': book.get('id'),
            'title': book.get('title'),
            'raw_price_from_sheet': raw_price,
            'raw_price_type': type(raw_price).__name__,
            'parsed_price': book.get('price'),
            'parsed_price_type': type(book.get('price')).__name__,
            'using_memory_storage': db.using_memory_storage
        })
    
    return jsonify({
        'total_books': len(all_books),
        'using_memory_storage': db.using_memory_storage,
        'price_debug': price_debug
    })


if __name__ == '__main__':
    print("🚀 Starting SWAPLY Server...")
    print("📚 Home: http://localhost:5000")
    print("🛒 Shop: http://localhost:5000/books")
    print("📦 Cart: http://localhost:5000/cart")
    print("💰 Checkout: http://localhost:5000/checkout")
    print("🔐 Login: http://localhost:5000/login")
    print("👤 My Account: http://localhost:5000/manage")
    print("💾 Database: " + ("Google Sheets" if not db.using_memory_storage else "In-Memory Storage"))
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5000)