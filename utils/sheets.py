import gspread
import os
from datetime import datetime
import json
import threading
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
        self.using_memory_storage = True
        self.connection_attempted = False
        
        # Initialize empty storage
        self._init_memory_storage()
        
        # Try to connect in background (non-blocking)
        self._connect_to_sheets_async()
    
    def _init_memory_storage(self):
        """Initialize empty memory storage"""
        print("🔄 Initializing memory storage...")
        self.books_storage = []
        self.users_storage = []
        self.orders_storage = []
        print("✅ Memory storage initialized (empty)")

    def _connect_to_sheets_async(self):
        """Connect to Google Sheets in background thread"""
        def connect_thread():
            print("\n" + "="*50)
            print("🔍 Attempting to connect to Google Sheets...")
            print("="*50)
            
            try:
                # Check credentials file
                if not os.path.exists('credentials.json'):
                    print("❌ credentials.json NOT FOUND - Using memory storage")
                    print("💡 To use Google Sheets, download credentials.json from:")
                    print("   https://console.cloud.google.com/apis/credentials")
                    self.connection_attempted = True
                    return
                
                print("✅ credentials.json found")
                
                # Verify credentials file
                try:
                    with open('credentials.json', 'r') as f:
                        creds = json.load(f)
                        if 'type' not in creds or creds['type'] != 'service_account':
                            print("❌ Invalid credentials.json - Using memory storage")
                            self.connection_attempted = True
                            return
                    print("✅ credentials.json is valid")
                except json.JSONDecodeError:
                    print("❌ credentials.json is not valid JSON - Using memory storage")
                    self.connection_attempted = True
                    return
                
                # Create API client with timeout
                try:
                    import gspread
                    self.client = gspread.service_account(filename='credentials.json')
                    print("✅ Google Sheets API client created")
                except Exception as e:
                    print(f"❌ Failed to create API client: {e}")
                    print("💡 Using memory storage")
                    self.connection_attempted = True
                    return
                
                # Connect to each sheet with timeout handling
                sheets_config = [
                    (self.books_sheet_name, 'books_sheet'),
                    (self.users_sheet_name, 'users_sheet'), 
                    (self.orders_sheet_name, 'orders_sheet')
                ]
                
                all_connected = True
                
                for sheet_name, attr_name in sheets_config:
                    try:
                        print(f"🔍 Connecting to '{sheet_name}'...")
                        # Add timeout for sheet connection
                        spreadsheet = self.client.open(sheet_name)
                        setattr(self, attr_name, spreadsheet.sheet1)
                        
                        # Test read access quickly
                        try:
                            records = getattr(self, attr_name).get_all_records()
                            print(f"✅ Connected to '{sheet_name}' ({len(records)} records)")
                        except Exception as e:
                            print(f"⚠️  Connected but read test failed for '{sheet_name}': {e}")
                            all_connected = False
                        
                    except gspread.SpreadsheetNotFound:
                        print(f"❌ Sheet '{sheet_name}' NOT FOUND")
                        print(f"💡 Please create: {sheet_name} and share with service account")
                        all_connected = False
                    except gspread.exceptions.APIError as e:
                        print(f"❌ API Error for '{sheet_name}': {e}")
                        all_connected = False
                    except Exception as e:
                        print(f"❌ Error connecting to '{sheet_name}': {e}")
                        all_connected = False
                
                if all_connected:
                    self.using_memory_storage = False
                    print("\n🎉 ALL GOOGLE SHEETS CONNECTED SUCCESSFULLY!")
                    print("="*50)
                    self.setup_headers()
                else:
                    print("\n⚠️  Some sheets failed - Using memory storage")
                    print("="*50)
                
                self.connection_attempted = True
                    
            except Exception as e:
                print(f"❌ Unexpected error in sheet connection: {e}")
                print("💡 Using memory storage")
                self.connection_attempted = True
        
        # Start connection in background thread
        thread = threading.Thread(target=connect_thread)
        thread.daemon = True
        thread.start()
        
        # Wait a bit for initial connection attempt
        time.sleep(2)
    
    def setup_headers(self):
        """Setup column headers for all sheets"""
        if self.using_memory_storage:
            return
        
        try:
            # Books sheet headers
            if self.books_sheet:
                all_values = self.books_sheet.get_all_values()
                if not all_values or len(all_values) == 0:
                    headers = ['id', 'title', 'author', 'price', 'condition', 'isbn', 
                              'description', 'category', 'status', 'stock_quantity', 'timestamp', 'image_url']
                    self.books_sheet.append_row(headers)
                    print("✅ Books sheet headers created")
            
            # Users sheet headers
            if self.users_sheet:
                all_values = self.users_sheet.get_all_values()
                if not all_values or len(all_values) == 0:
                    headers = ['user_id', 'email', 'name', 'phone', 'address_line1', 
                              'address_line2', 'city', 'state', 'zip_code', 'created_at', 'updated_at']
                    self.users_sheet.append_row(headers)
                    print("✅ Users sheet headers created")
            
            # Orders sheet headers
            if self.orders_sheet:
                all_values = self.orders_sheet.get_all_values()
                if not all_values or len(all_values) == 0:
                    headers = ['order_id', 'user_id', 'user_email', 'book_id', 'book_title', 
                              'quantity', 'total_price', 'full_name', 'phone', 'address_line1', 
                              'address_line2', 'city', 'state', 'zip_code', 'payment_method', 
                              'status', 'created_at']
                    self.orders_sheet.append_row(headers)
                    print("✅ Orders sheet headers created")
                
        except Exception as e:
            print(f"❌ Error setting up headers: {e}")

    def get_all_books(self):
        """Get all books"""
        if self.using_memory_storage:
            print("📚 Using memory storage")
            return self.books_storage
        
        try:
            if not self.books_sheet:
                print("❌ Books sheet not connected")
                return []
            
            all_values = self.books_sheet.get_all_values()
            
            if len(all_values) <= 1:
                print("📚 No books in Google Sheet")
                return []
            
            headers = all_values[0]
            books = []
            
            for row_index, row in enumerate(all_values[1:], start=2):
                if not row or len(row) < 4:
                    continue
                
                # Create book dict
                book = {}
                for i, header in enumerate(headers):
                    book[header] = row[i] if i < len(row) else ''
                
                # Parse price
                try:
                    price = float(str(book.get('price', '0')).replace('₹', '').replace(',', '').strip())
                except:
                    price = 0.0
                
                # Parse stock quantity
                try:
                    stock_qty = int(str(book.get('stock_quantity', '1')).strip())
                except:
                    stock_qty = 1
                
                # Get image URL
                image_url = book.get('image_url', '').strip()

                book_data = {
                    'id': str(book.get('id', '')).strip(),
                    'title': book.get('title', 'Unknown Book'),
                    'author': book.get('author', 'Unknown Author'),
                    'price': price,
                    'condition': book.get('condition', 'Good'),
                    'isbn': book.get('isbn', ''),
                    'description': book.get('description', ''),
                    'category': book.get('category', ''),
                    'status': book.get('status', 'Available'),
                    'stock_quantity': stock_qty,
                    'timestamp': book.get('timestamp', ''),
                    'image_url': image_url
                }
                
                books.append(book_data)
            
            print(f"✅ Loaded {len(books)} books from Google Sheets")
            return books
            
        except Exception as e:
            print(f"❌ Error loading books: {e}")
            return []

    def get_available_books(self):
        """Get only available books"""
        all_books = self.get_all_books()
        available = [book for book in all_books 
                    if book.get('status', '').lower() == 'available' 
                    and book.get('stock_quantity', 0) > 0]
        print(f"📚 Available books: {len(available)}")
        return available
    
    def get_book_by_id(self, book_id):
        """Get specific book by ID"""
        all_books = self.get_all_books()
        book_id_str = str(book_id).strip()
        
        for book in all_books:
            if str(book.get('id', '')).strip() == book_id_str:
                return book
        
        return None
    
    def update_book_status(self, book_id, new_status):
        """Update book status"""
        if self.using_memory_storage:
            for book in self.books_storage:
                if str(book.get('id')).strip() == str(book_id).strip():
                    book['status'] = new_status
                    return True
            return False
        
        try:
            if not self.books_sheet:
                return False
            
            all_values = self.books_sheet.get_all_values()
            headers = all_values[0]
            status_col_index = headers.index('status') + 1 if 'status' in headers else 9
            
            for row_index, row in enumerate(all_values[1:], start=2):
                if len(row) > 0 and str(row[0]).strip() == str(book_id).strip():
                    self.books_sheet.update_cell(row_index, status_col_index, new_status)
                    return True
            
            return False
        except Exception as e:
            print(f"❌ Error updating status: {e}")
            return False
    
    def decrease_book_stock(self, book_id, quantity=1):
        """Decrease book stock"""
        if self.using_memory_storage:
            for book in self.books_storage:
                if str(book.get('id')).strip() == str(book_id).strip():
                    current_stock = book.get('stock_quantity', 1)
                    new_stock = max(0, current_stock - quantity)
                    book['stock_quantity'] = new_stock
                    
                    if new_stock == 0:
                        book['status'] = 'Sold Out'
                    return True
            return False
        
        try:
            if not self.books_sheet:
                return False
            
            all_values = self.books_sheet.get_all_values()
            headers = all_values[0]
            
            stock_col_index = headers.index('stock_quantity') + 1 if 'stock_quantity' in headers else 10
            status_col_index = headers.index('status') + 1 if 'status' in headers else 9
            
            for row_index, row in enumerate(all_values[1:], start=2):
                if len(row) > 0 and str(row[0]).strip() == str(book_id).strip():
                    try:
                        current_stock = int(row[stock_col_index - 1]) if len(row) >= stock_col_index else 1
                    except:
                        current_stock = 1
                    
                    new_stock = max(0, current_stock - quantity)
                    
                    self.books_sheet.update_cell(row_index, stock_col_index, new_stock)
                    
                    if new_stock == 0:
                        self.books_sheet.update_cell(row_index, status_col_index, 'Sold Out')
                    
                    return True
            
            return False
        except Exception as e:
            print(f"❌ Error decreasing stock: {e}")
            return False
    
    def save_user_info(self, user_data):
        """Save or update user information"""
        if self.using_memory_storage:
            self.users_storage = [u for u in self.users_storage 
                                 if u.get('email') != user_data.get('email')]
            self.users_storage.append(user_data)
            return True
        
        try:
            if not self.users_sheet:
                return False
            
            all_values = self.users_sheet.get_all_values()
            user_email = user_data.get('email')
            user_exists = False
            row_index = None
            
            for i, row in enumerate(all_values[1:], start=2):
                if len(row) > 1 and row[1] == user_email:
                    user_exists = True
                    row_index = i
                    break
            
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
                self.users_sheet.update(f'A{row_index}:K{row_index}', [row_data])
            else:
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
            return next((r for r in records if r.get('email') == user_email), None)
        except Exception as e:
            print(f"❌ Error getting user: {e}")
            return None
    
    def add_order(self, order_data):
        """Add a new order"""
        if self.using_memory_storage:
            self.orders_storage.append(order_data)
            return True
        
        try:
            if not self.orders_sheet:
                return False
            
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
            
            self.orders_sheet.append_row(row_data)
            return True
            
        except Exception as e:
            print(f"❌ Error adding order: {e}")
            return False
    
    def get_user_orders(self, user_email):
        """Get orders by user email"""
        if self.using_memory_storage:
            orders = [o for o in self.orders_storage if o.get('user_email') == user_email]
            return sorted(orders, key=lambda x: x.get('created_at', ''), reverse=True)
        
        try:
            if not self.orders_sheet:
                return []
            
            records = self.orders_sheet.get_all_records()
            user_orders = [r for r in records if r.get('user_email') == user_email]
            return sorted(user_orders, key=lambda x: x.get('created_at', ''), reverse=True)
        except Exception as e:
            print(f"❌ Error getting orders: {e}")
            return []

# Global instance - this will now start without blocking
db = GoogleSheetsDB()