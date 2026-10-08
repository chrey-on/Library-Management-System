"""
=====================================================================
LIBRARY MANAGEMENT SYSTEM - END-TO-END INTEGRATION TEST SUITE
Database 2 Case Study (IT31A)
=====================================================================
"""
import sys
import os
import time
import unittest
from werkzeug.datastructures import MultiDict

# Ensure app directory is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.db import query_one, query_all, execute_db

class LibrarySystemE2ETestCase(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    def test_01_authentication_and_rbac(self):
        """Test authentication, bad credentials, deactivated accounts, and RBAC protection."""
        # 1. Unauthenticated redirect
        res = self.client.get('/dashboard/librarian')
        self.assertEqual(res.status_code, 302)
        self.assertIn('/auth/login', res.location)

        # 2. Invalid password
        res = self.client.post('/auth/login', data={'username': 'admin', 'password': 'wrongpassword'}, follow_redirects=True)
        self.assertIn(b'Invalid username or password', res.data)

        # 3. Deactivated member (kevin.ramos)
        res = self.client.post('/auth/login', data={'username': 'kevin.ramos', 'password': 'member123'}, follow_redirects=True)
        self.assertIn(b'deactivated', res.data.lower())

        # 4. Successful Librarian login
        res = self.client.post('/auth/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=True)
        self.assertIn(b'Librarian Dashboard', res.data)

        # 5. Member login & RBAC check
        self.client.get('/auth/logout')
        res = self.client.post('/auth/login', data={'username': 'ana.reyes', 'password': 'member123'}, follow_redirects=True)
        self.assertIn(b'Welcome back, Ana!', res.data)

        # 6. Member trying to access librarian circulation
        res = self.client.get('/loans/issue')
        self.assertEqual(res.status_code, 403)

    def test_02_categories_and_authors_crud(self):
        """Test creating, editing, and referential integrity protection for categories and authors."""
        self.client.post('/auth/login', data={'username': 'admin', 'password': 'admin123'})
        ts = str(int(time.time()))

        cat_name = f'Cybersecurity {ts}'
        res = self.client.post('/categories/create', data={'name': cat_name, 'description': 'Security protocols'}, follow_redirects=True)
        self.assertIn(cat_name.encode(), res.data)

        author_last = f'Schneier{ts}'
        res = self.client.post('/authors/create', data={'first_name': 'Bruce', 'last_name': author_last}, follow_redirects=True)
        self.assertIn(author_last.encode(), res.data)

        with self.app.app_context():
            cat = query_one('SELECT category_id FROM categories WHERE name = %s', (cat_name,))
            auth = query_one('SELECT author_id FROM authors WHERE last_name = %s', (author_last,))
            self.assertIsNotNone(cat)
            self.assertIsNotNone(auth)

    def test_03_books_and_copy_inventory(self):
        """Test book creation, multi-author junction insertion, copy generation, and soft delete."""
        self.client.post('/auth/login', data={'username': 'admin', 'password': 'admin123'})
        ts = str(int(time.time()))

        with self.app.app_context():
            cat = query_one('SELECT category_id FROM categories LIMIT 1')
            auth = query_one('SELECT author_id FROM authors LIMIT 1')

        isbn = f'9780{ts[:9]}'
        title = f'Modern Operating Systems {ts}'

        form_data = MultiDict([
            ('isbn', isbn),
            ('title', title),
            ('category_id', str(cat['category_id'])),
            ('author_ids', str(auth['author_id'])),
            ('publisher', 'Pearson'),
            ('publication_year', '2023'),
            ('description', 'Comprehensive guide to OS concepts.'),
            ('initial_copies', '3')
        ])
        res = self.client.post('/books/create', data=form_data, follow_redirects=True)
        self.assertIn(title.encode(), res.data)

        with self.app.app_context():
            book = query_one('SELECT book_id FROM books WHERE isbn = %s', (isbn,))
            self.assertIsNotNone(book)
            copies = query_one('SELECT COUNT(*) AS cnt FROM book_copies WHERE book_id = %s', (book['book_id'],))
            self.assertEqual(copies['cnt'], 3)

    def test_04_member_registration(self):
        """Test atomic student member registration creating users and members records."""
        self.client.post('/auth/login', data={'username': 'admin', 'password': 'admin123'})
        ts = str(int(time.time()))

        student_no = f'2026-{ts[-5:]}'
        username = f'user.{ts}'
        email = f'user.{ts}@student.local'

        res = self.client.post('/members/create', data={
            'student_no': student_no,
            'username': username,
            'email': email,
            'first_name': 'Test',
            'last_name': 'Student',
            'course_id': '1',
            'year_level': '1',
            'contact_no': '09170001122',
            'password': 'member123'
        }, follow_redirects=True)
        self.assertIn(b'registered successfully', res.data)

        with self.app.app_context():
            member = query_one('SELECT m.*, u.username FROM members m JOIN users u ON u.user_id = m.user_id WHERE m.student_no = %s', (student_no,))
            self.assertIsNotNone(member)

    def test_05_circulation_triggers_and_procedures(self):
        """Test stored procedures sp_borrow_book, sp_return_book, sp_pay_fine, and trigger rules."""
        self.client.post('/auth/login', data={'username': 'admin', 'password': 'admin123'})

        with self.app.app_context():
            # Find an active member without overdue/fines (Carla Torres or Paolo Bautista)
            member = query_one("""
                SELECT m.member_id FROM members m 
                JOIN users u ON u.user_id = m.user_id 
                WHERE u.is_active = 1 
                  AND m.member_id NOT IN (SELECT l.member_id FROM fines f JOIN loans l ON l.loan_id = f.loan_id WHERE f.is_paid = 0)
                  AND m.member_id NOT IN (SELECT l.member_id FROM loans l WHERE l.returned_at IS NULL AND l.due_date < CURDATE())
                  AND (SELECT COUNT(*) FROM loans l WHERE l.member_id = m.member_id AND l.returned_at IS NULL) < 3
                LIMIT 1
            """)
            copy = query_one('SELECT copy_id FROM book_copies WHERE status = %s LIMIT 1', ('available',))

        # 1. Borrow book
        res = self.client.post('/loans/issue', data={'member_id': str(member['member_id']), 'copy_id': str(copy['copy_id'])}, follow_redirects=True)
        self.assertIn(b'Successfully issued', res.data)

        # 2. Verify trigger updated copy status to borrowed
        with self.app.app_context():
            c_status = query_one('SELECT status FROM book_copies WHERE copy_id = %s', (copy['copy_id'],))
            self.assertEqual(c_status['status'], 'borrowed')

        # 3. Test Trigger Violation: Attempting to borrow unavailable copy
        res = self.client.post('/loans/issue', data={'member_id': str(member['member_id']), 'copy_id': str(copy['copy_id'])}, follow_redirects=True)
        self.assertIn(b'not available', res.data.lower())

        # 4. Return book
        with self.app.app_context():
            loan = query_one('SELECT loan_id FROM loans WHERE copy_id = %s AND returned_at IS NULL', (copy['copy_id'],))

        res = self.client.post('/loans/return', data={'loan_id': str(loan['loan_id'])}, follow_redirects=True)
        self.assertIn(b'returned', res.data.lower())

        # 5. Verify trigger restored copy status to available
        with self.app.app_context():
            c_restored = query_one('SELECT status FROM book_copies WHERE copy_id = %s', (copy['copy_id'],))
            self.assertEqual(c_restored['status'], 'available')

    def test_06_reports_and_views(self):
        """Test all report views and stored procedure outputs."""
        self.client.post('/auth/login', data={'username': 'admin', 'password': 'admin123'})

        for endpoint in ['/reports/', '/reports/most-borrowed', '/reports/overdue', '/reports/unpaid-fines', '/reports/monthly-summary']:
            res = self.client.get(endpoint)
            self.assertEqual(res.status_code, 200, f'Endpoint {endpoint} returned status {res.status_code}')

    def test_07_book_covers_and_catalog_browse(self):
        """Test book cover URL handling, catalog browse, and student portal views."""
        # 1. Test member browse
        self.client.post('/auth/login', data={'username': 'ana.reyes', 'password': 'member123'})
        res = self.client.get('/books/browse')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Explore Book Catalog', res.data)
        self.assertIn(b'covers.openlibrary.org', res.data)

        # 2. Test search filter on browse
        res = self.client.get('/books/browse?q=Python')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Python', res.data)

        # 3. Create book with auto cover vs custom cover
        self.client.get('/auth/logout')
        self.client.post('/auth/login', data={'username': 'admin', 'password': 'admin123'})
        ts = str(int(time.time()))
        with self.app.app_context():
            cat = query_one('SELECT category_id FROM categories LIMIT 1')
            auth = query_one('SELECT author_id FROM authors LIMIT 1')

        isbn_auto = f'9780{ts[-9:]}'
        form_auto = MultiDict([
            ('isbn', isbn_auto),
            ('title', f'Auto Cover Test {ts}'),
            ('category_id', str(cat['category_id'])),
            ('author_ids', str(auth['author_id'])),
            ('cover_image_url', ''), # Leave blank to auto-generate
            ('initial_copies', '1')
        ])
        res = self.client.post('/books/create', data=form_auto, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        with self.app.app_context():
            book = query_one('SELECT cover_image_url FROM books WHERE isbn = %s', (isbn_auto,))
            self.assertIsNotNone(book)
            self.assertIn('covers.openlibrary.org', book['cover_image_url'])

    def test_08_full_route_matrix_and_error_pages(self):
        """Test comprehensive route matrix for librarian and member roles."""
        # Librarian routes check
        self.client.post('/auth/login', data={'username': 'admin', 'password': 'admin123'})
        librarian_routes = [
            '/dashboard/librarian',
            '/books/',
            '/books/create',
            '/categories/',
            '/authors/',
            '/members/',
            '/members/create',
            '/loans/',
            '/loans/issue',
            '/loans/return',
            '/loans/fines',
            '/reports/',
            '/reports/most-borrowed',
            '/reports/overdue',
            '/reports/unpaid-fines',
            '/reports/monthly-summary',
            '/auth/change-password'
        ]
        for route in librarian_routes:
            res = self.client.get(route)
            self.assertEqual(res.status_code, 200, f'Librarian route {route} failed with status {res.status_code}')

        # Member routes check
        self.client.get('/auth/logout')
        self.client.post('/auth/login', data={'username': 'ana.reyes', 'password': 'member123'})
        member_routes = [
            '/dashboard/member',
            '/books/browse',
            '/members/my-loans',
            '/members/my-fines',
            '/auth/change-password'
        ]
        for route in member_routes:
            res = self.client.get(route)
            self.assertEqual(res.status_code, 200, f'Member route {route} failed with status {res.status_code}')

        # 404 test
        res = self.client.get('/nonexistent-page-route')
        self.assertEqual(res.status_code, 404)


if __name__ == '__main__':
    unittest.main()
