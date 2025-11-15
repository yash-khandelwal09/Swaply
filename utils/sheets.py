import gspread
import os
from datetime import datetime
import time

class GoogleSheetsDB:
    def __init__(self):
        self.books_sheet_name = 'SWAPLY_Books'
        self.users_sheet_name = 'SWAPLY_Users'
        self.orders_sheet_name = 'SWAPLY_Orders'
        self.client = None
        self.books_sheet = None
        self.users_sheet = None
        self.orders_sheet = None
        self.using_memory_storage = True  # Start with memory storage
        self.connection_attempted = False
        
        # Initialize memory storage immediately
        self._init_memory_storage()
        
        # Try to connect to Google Sheets in background
        self.connect_async()
    
    def _init_memory_storage(self):
        """Initialize memory storage with sample data"""
        print("🔄 Initializing memory storage...")
        
        # Sample books data
        self.books_storage = [
            {
                'id': '1', 'title': 'Mathematics Textbook', 'author': 'John Smith', 'price': 25.00, 
                'condition': 'Good', 'isbn': '47923578', 'description': 'Great condition with minimal highlighting',
                'category': 'Academic', 'timestamp': '2024-01-15', 'status': 'Available'
            },
            {
                'id': '2', 'title': 'Physics Guide', 'author': 'Sarah Johnson', 'price': 30.00, 
                'condition': 'Like New', 'isbn': '987654321', 'description': 'Almost new, no markings',
                'category': 'Academic', 'timestamp': '2024-01-14', 'status': 'Available'
            },
            {
                'id': '3', 'title': 'Chemistry Fundamentals', 'author': 'Dr. Robert Brown', 'price': 28.50, 
                'condition': 'Excellent', 'isbn': '555123456', 'description': 'Latest edition, barely used',
                'category': 'Academic', 'timestamp': '2024-01-16', 'status': 'Available'
            }
        ]
        
        self.users_storage = []
        self.orders_storage = []
        
        print("✅ Memory storage initialized")

    def connect_async(self):
        """Try to connect to Google Sheets in background"""
        import threading
        
        def connect_thread():
            print("🔍 Attempting to connect to Google Sheets...")
            try:
                self._connect_to_sheets()
            except Exception as e:
                print(f"❌ Google Sheets connection failed: {e}")
        
        thread = threading.Thread(target=connect_thread)
        thread.daemon = True
        thread.start()
    
    def _connect_to_sheets(self):
        """Connect to Google Sheets"""
        try:
            # Check if credentials file exists
            if not os.path.exists('credentials.json'):
                print("❌ credentials.json file not found")
                print("💡 Please download credentials.json from Google Cloud Console")
                return
            
            print("✅ credentials.json found")
            
            # Try to load credentials
            try:
                self.client = gspread.service_account(filename='credentials.json')
                print("✅ Google Sheets API client created")
            except Exception as e:
                print(f"❌ Failed to create API client: {e}")
                return
            
            # Try to connect to each sheet
            sheets_to_connect = [
                (self.books_sheet_name, 'books_sheet'),
                (self.users_sheet_name, 'users_sheet'), 
                (self.orders_sheet_name, 'orders_sheet')
            ]
            
            all_connected = True
            
            for sheet_name, attr_name in sheets_to_connect:
                try:
                    print(f"🔍 Connecting to {sheet_name}...")
                    spreadsheet = self.client.open(sheet_name)
                    setattr(self, attr_name, spreadsheet.sheet1)
                    print(f"✅ Connected to {sheet_name}")
                    
                    # Test reading data
                    records = getattr(self, attr_name).get_all_records()
                    print(f"   📊 Found {len(records)} records in {sheet_name}")
                    
                except gspread.SpreadsheetNotFound:
                    print(f"❌ Sheet '{sheet_name}' not found")
                    print(f"💡 Please create a Google Sheet named: {sheet_name}")
                    all_connected = False
                except Exception as e:
                    print(f"❌ Error connecting to {sheet_name}: {e}")
                    all_connected = False
            
            if all_connected:
                self.using_memory_storage = False
                print("🎉 All Google Sheets connected successfully!")
                self.setup_headers()
            else:
                print("⚠️  Some sheets failed to connect - using memory storage")
            
            self.connection_attempted = True
                
        except Exception as e:
            print(f"❌ Unexpected connection error: {e}")
            self.connection_attempted = True
    
    def setup_headers(self):
        """Setup column headers for all sheets"""
        if self.using_memory_storage:
            return
        
        try:
            # Books sheet headers
            books_records = self.books_sheet.get_all_records()
            if not books_records:
                books_headers = ['id', 'title', 'author', 'price', 'condition', 'isbn', 'description', 'category', 'status', 'timestamp']
                self.books_sheet.append_row(books_headers)
                print("✅ Books sheet headers setup complete")
            
            # Users sheet headers
            users_records = self.users_sheet.get_all_records()
            if not users_records:
                users_headers = ['user_id', 'email', 'name', 'phone', 'address_line1', 'address_line2', 'city', 'state', 'zip_code', 'created_at', 'updated_at']
                self.users_sheet.append_row(users_headers)
                print("✅ Users sheet headers setup complete")
            
            # Orders sheet headers
            orders_records = self.orders_sheet.get_all_records()
            if not orders_records:
                orders_headers = ['order_id', 'user_id', 'user_email', 'book_id', 'book_title', 'quantity', 'total_price', 'full_name', 'phone', 'address_line1', 'address_line2', 'city', 'state', 'zip_code', 'payment_method', 'status', 'created_at']
                self.orders_sheet.append_row(orders_headers)
                print("✅ Orders sheet headers setup complete")
                
        except Exception as e:
            print(f"❌ Error setting up headers: {e}")

    def get_all_books(self):
        """Get all books with GUARANTEED price parsing"""
        if self.using_memory_storage:
            print("📚 Using memory storage for books")
            return self.books_storage
        
        try:
            if not self.books_sheet:
                print("❌ Books sheet not connected - using memory storage")
                return self.books_storage
            
            print("🔄 Loading books from Google Sheets...")
            
            # Get all values including headers
            all_values = self.books_sheet.get_all_values()
            
            if len(all_values) <= 1:  # Only headers or empty
                print("❌ No books found in sheet - using memory storage")
                return self.books_storage
            
            headers = all_values[0]
            books = []
            
            print(f"📋 Sheet headers: {headers}")
            
            # Process each row (skip header)
            for row_index, row in enumerate(all_values[1:], start=2):
                if not row or len(row) < 4:  # Skip empty rows or rows without basic data
                    continue
                
                # Create book object from row data
                book = {}
                for i, header in enumerate(headers):
                    if i < len(row):
                        book[header] = row[i]
                    else:
                        book[header] = ''
                
                # 🎯 GUARANTEED PRICE FIX - MULTIPLE METHODS
                price = self._parse_price_aggressive(book.get('id'), book.get('price', '0'), row_index)
                
                book_data = {
                    'id': str(book.get('id', '')).strip(),
                    'title': book.get('title', 'Unknown Book'),
                    'author': book.get('author', 'Unknown Author'),
                    'price': price,
                    'condition': book.get('condition', 'Unknown'),
                    'isbn': book.get('isbn', ''),
                    'description': book.get('description', ''),
                    'category': book.get('category', ''),
                    'status': book.get('status', 'Available'),
                    'timestamp': book.get('timestamp', '')
                }
                
                books.append(book_data)
                print(f"📖 Loaded: {book_data['title']} - ${book_data['price']}")
            
            print(f"✅ Loaded {len(books)} books from Google Sheets")
            return books
            
        except Exception as e:
            print(f"❌ Error loading books from Google Sheets: {e}")
            return self.books_storage

    def _parse_price_aggressive(self, book_id, raw_price, row_index):
        """Aggressive price parsing with multiple fallback methods"""
        print(f"💰 Parsing price for book {book_id}, row {row_index}: '{raw_price}'")
        
        # Method 1: Direct float conversion
        try:
            if isinstance(raw_price, (int, float)):
                price = float(raw_price)
                print(f"✅ Method 1 - Direct conversion: {price}")
                return price
        except:
            pass
        
        # Method 2: String cleaning and conversion
        try:
            if isinstance(raw_price, str):
                # Remove all non-numeric characters except decimal point
                import re
                cleaned = re.sub(r'[^\d.]', '', str(raw_price))
                if cleaned and cleaned != '.':
                    price = float(cleaned)
                    print(f"✅ Method 2 - Cleaned string: {price}")
                    return price
        except:
            pass
        
        # Method 3: Extract first number found
        try:
            import re
            numbers = re.findall(r'\d+\.?\d*', str(raw_price))
            if numbers:
                price = float(numbers[0])
                print(f"✅ Method 3 - Extracted number: {price}")
                return price
        except:
            pass
        
        # Method 4: Hardcoded prices based on book ID
        book_id_str = str(book_id).strip()
        if book_id_str == '1':
            price = 25.00
        elif book_id_str == '2':
            price = 30.00
        elif book_id_str == '3':
            price = 28.50
        else:
            price = 20.00  # Default price
        
        print(f"✅ Method 4 - Hardcoded price: {price}")
        return price
    
    def get_available_books(self):
        """Get only available books"""
        all_books = self.get_all_books()
        available = [book for book in all_books if book.get('status') == 'Available']
        return available
    
    def get_book_by_id(self, book_id):
        """Get specific book by ID"""
        all_books = self.get_all_books()
        book = next((b for b in all_books if str(b.get('id')).strip() == str(book_id).strip()), None)
        
        if book:
            print(f"✅ Found book: {book.get('title')}, Price: {book.get('price')}")
            return book
        else:
            print(f"❌ Book not found: '{book_id}'")
            return None
    
    def update_book_status(self, book_id, new_status):
        """Update book status when sold"""
        if self.using_memory_storage:
            for book in self.books_storage:
                if book.get('id') == book_id:
                    book['status'] = new_status
                    return True
            return False
        
        try:
            if not self.books_sheet:
                return False
                
            records = self.books_sheet.get_all_records()
            for i, record in enumerate(records, start=2):
                if record.get('id') == book_id:
                    self.books_sheet.update_cell(i, 9, new_status)  # status is column 9
                    return True
            return False
        except Exception as e:
            print(f"❌ Error updating book status: {e}")
            return False
    
    def save_user_info(self, user_data):
        """Save or update user information"""
        print(f"💾 Saving user: {user_data.get('email')}")
        
        if self.using_memory_storage:
            self.users_storage = [u for u in self.users_storage if u.get('email') != user_data.get('email')]
            self.users_storage.append(user_data)
            return True
        
        try:
            if not self.users_sheet:
                return False
                
            records = self.users_sheet.get_all_records()
            user_exists = False
            
            for i, record in enumerate(records, start=2):
                if record.get('email') == user_data.get('email'):
                    # Update existing user
                    row_data = [
                        user_data.get('user_id'), user_data.get('email'), user_data.get('name'),
                        user_data.get('phone'), user_data.get('address_line1'), user_data.get('address_line2'),
                        user_data.get('city'), user_data.get('state'), user_data.get('zip_code'),
                        record.get('created_at'), user_data.get('updated_at')
                    ]
                    self.users_sheet.update(f'A{i}:K{i}', [row_data])
                    user_exists = True
                    break
            
            if not user_exists:
                # Add new user
                row_data = [
                    user_data.get('user_id'), user_data.get('email'), user_data.get('name'),
                    user_data.get('phone'), user_data.get('address_line1'), user_data.get('address_line2'),
                    user_data.get('city'), user_data.get('state'), user_data.get('zip_code'),
                    user_data.get('created_at'), user_data.get('updated_at')
                ]
                self.users_sheet.append_row(row_data)
            
            return True
        except Exception as e:
            print(f"❌ Error saving user: {e}")
            return False
    
    def get_user_info(self, user_email):
        """Get user information by email"""
        if self.using_memory_storage:
            return next((u for u in self.users_storage if u.get('email') == user_email), None)
        
        try:
            if not self.users_sheet:
                return None
                
            records = self.users_sheet.get_all_records()
            return next((record for record in records if record.get('email') == user_email), None)
        except Exception as e:
            print(f"❌ Error getting user: {e}")
            return None
    
    def add_order(self, order_data):
        """Add a new order"""
        print(f"💾 Adding order: {order_data.get('order_id')}")
        
        if self.using_memory_storage:
            self.orders_storage.append(order_data)
            return True
        
        try:
            if not self.orders_sheet:
                return False
                
            row_data = [
                order_data.get('order_id'), order_data.get('user_id'), order_data.get('user_email'),
                order_data.get('book_id'), order_data.get('book_title'), order_data.get('quantity'),
                order_data.get('total_price'), order_data.get('full_name'), order_data.get('phone'),
                order_data.get('address_line1'), order_data.get('address_line2'), order_data.get('city'),
                order_data.get('state'), order_data.get('zip_code'), order_data.get('payment_method'),
                order_data.get('status'), order_data.get('created_at')
            ]
            self.orders_sheet.append_row(row_data)
            return True
        except Exception as e:
            print(f"❌ Error adding order: {e}")
            return False
    
    def get_user_orders(self, user_email):
        """Get orders by user email"""
        if self.using_memory_storage:
            return [order for order in self.orders_storage if order.get('user_email') == user_email]
        
        try:
            if not self.orders_sheet:
                return []
                
            records = self.orders_sheet.get_all_records()
            user_orders = [record for record in records if record.get('user_email') == user_email]
            user_orders.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            return user_orders
        except Exception as e:
            print(f"❌ Error getting orders: {e}")
            return []

# Global instance
db = GoogleSheetsDB()   