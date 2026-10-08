from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.routes.auth import librarian_required, login_required
from app.db import query_all, query_one, execute_db, get_db

books_bp = Blueprint('books', __name__, url_prefix='/books')

def generate_accession_no():
    """Generates the next sequential accession number, e.g., ACC-0028."""
    last_copy = query_one(
        "SELECT accession_no FROM book_copies WHERE accession_no LIKE %s "
        "ORDER BY copy_id DESC LIMIT 1",
        ('ACC-%',)
    )
    if last_copy:
        try:
            num = int(last_copy['accession_no'].replace('ACC-', ''))
            return f"ACC-{num + 1:04d}"
        except ValueError:
            pass
    total = query_one("SELECT COUNT(*) AS total FROM book_copies")['total']
    return f"ACC-{total + 1:04d}"


@books_bp.route('/', methods=['GET'])
@librarian_required
def list_books():
    q = request.args.get('q', '').strip()
    category_id = request.args.get('category_id', '')
    status_filter = request.args.get('status', 'active')  # 'active', 'archived', 'all'

    sql = "SELECT * FROM vw_book_catalog WHERE 1=1"
    params = []

    if status_filter == 'active':
        sql += " AND is_archived = 0"
    elif status_filter == 'archived':
        sql += " AND is_archived = 1"

    if category_id and category_id.isdigit():
        sql += " AND category_id = %s"
        params.append(int(category_id))

    if q:
        sql += " AND (title LIKE %s OR isbn LIKE %s OR authors LIKE %s)"
        like_term = f"%{q}%"
        params.extend([like_term, like_term, like_term])

    sql += " ORDER BY title ASC"
    books = query_all(sql, params)
    categories = query_all("SELECT category_id, name FROM categories ORDER BY name ASC")

    return render_template(
        'books/list.html',
        books=books,
        categories=categories,
        q=q,
        category_id=category_id,
        status_filter=status_filter
    )


@books_bp.route('/create', methods=['GET', 'POST'])
@librarian_required
def create_book():
    if request.method == 'POST':
        isbn = request.form.get('isbn', '').strip()
        title = request.form.get('title', '').strip()
        category_id = request.form.get('category_id')
        author_ids = request.form.getlist('author_ids')
        publisher = request.form.get('publisher', '').strip()
        publication_year = request.form.get('publication_year', '').strip()
        description = request.form.get('description', '').strip()
        initial_copies = int(request.form.get('initial_copies', 1) or 1)

        # Basic validations
        if not isbn or not title or not category_id or not author_ids:
            flash('ISBN, Title, Category, and at least one Author are required.', 'danger')
            categories = query_all("SELECT category_id, name FROM categories ORDER BY name ASC")
            authors = query_all("SELECT author_id, first_name, last_name FROM authors ORDER BY last_name ASC")
            return render_template('books/form.html', categories=categories, authors=authors, book=None)

        # Check for unique ISBN
        existing = query_one("SELECT book_id FROM books WHERE isbn = %s", (isbn,))
        if existing:
            flash(f'A book with ISBN "{isbn}" already exists.', 'danger')
            categories = query_all("SELECT category_id, name FROM categories ORDER BY name ASC")
            authors = query_all("SELECT author_id, first_name, last_name FROM authors ORDER BY last_name ASC")
            return render_template('books/form.html', categories=categories, authors=authors, book=None)

        db = get_db()
        try:
            # 1. Insert into books table
            res = execute_db(
                "INSERT INTO books (isbn, title, category_id, publisher, publication_year, description) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (isbn, title, category_id, publisher or None, int(publication_year) if publication_year else None, description or None),
                autocommit=False
            )
            new_book_id = res['last_id']

            # 2. Insert into book_authors junction table
            for aid in author_ids:
                execute_db(
                    "INSERT INTO book_authors (book_id, author_id) VALUES (%s, %s)",
                    (new_book_id, int(aid)),
                    autocommit=False
                )

            # 3. Create initial physical copies
            for _ in range(max(1, min(initial_copies, 50))):
                acc_no = generate_accession_no()
                execute_db(
                    "INSERT INTO book_copies (book_id, accession_no, status, acquired_date) "
                    "VALUES (%s, %s, 'available', CURDATE())",
                    (new_book_id, acc_no),
                    autocommit=False
                )

            db.commit()
            flash(f'Book "{title}" added successfully with {initial_copies} initial cop(ies).', 'success')
            return redirect(url_for('books.detail', book_id=new_book_id))
        except Exception as e:
            db.rollback()
            flash(f'Error creating book: {str(e)}', 'danger')

    categories = query_all("SELECT category_id, name FROM categories ORDER BY name ASC")
    authors = query_all("SELECT author_id, first_name, last_name FROM authors ORDER BY last_name ASC, first_name ASC")
    return render_template('books/form.html', categories=categories, authors=authors, book=None)


@books_bp.route('/edit/<int:book_id>', methods=['GET', 'POST'])
@librarian_required
def edit_book(book_id):
    book = query_one("SELECT * FROM books WHERE book_id = %s", (book_id,))
    if not book:
        flash('Book not found.', 'danger')
        return redirect(url_for('books.list_books'))

    if request.method == 'POST':
        isbn = request.form.get('isbn', '').strip()
        title = request.form.get('title', '').strip()
        category_id = request.form.get('category_id')
        author_ids = request.form.getlist('author_ids')
        publisher = request.form.get('publisher', '').strip()
        publication_year = request.form.get('publication_year', '').strip()
        description = request.form.get('description', '').strip()

        if not isbn or not title or not category_id or not author_ids:
            flash('ISBN, Title, Category, and at least one Author are required.', 'danger')
            return redirect(url_for('books.edit_book', book_id=book_id))

        # Check ISBN collision with other books
        existing = query_one(
            "SELECT book_id FROM books WHERE isbn = %s AND book_id != %s",
            (isbn, book_id)
        )
        if existing:
            flash(f'Another book is already using ISBN "{isbn}".', 'danger')
            return redirect(url_for('books.edit_book', book_id=book_id))

        db = get_db()
        try:
            # Update book metadata
            execute_db(
                "UPDATE books SET isbn = %s, title = %s, category_id = %s, publisher = %s, "
                "publication_year = %s, description = %s WHERE book_id = %s",
                (isbn, title, category_id, publisher or None, int(publication_year) if publication_year else None, description or None, book_id),
                autocommit=False
            )

            # Re-sync authors junction table
            execute_db("DELETE FROM book_authors WHERE book_id = %s", (book_id,), autocommit=False)
            for aid in author_ids:
                execute_db(
                    "INSERT INTO book_authors (book_id, author_id) VALUES (%s, %s)",
                    (book_id, int(aid)),
                    autocommit=False
                )

            db.commit()
            flash('Book details updated successfully.', 'success')
            return redirect(url_for('books.detail', book_id=book_id))
        except Exception as e:
            db.rollback()
            flash(f'Error updating book: {str(e)}', 'danger')

    categories = query_all("SELECT category_id, name FROM categories ORDER BY name ASC")
    authors = query_all("SELECT author_id, first_name, last_name FROM authors ORDER BY last_name ASC, first_name ASC")
    current_author_ids = [row['author_id'] for row in query_all("SELECT author_id FROM book_authors WHERE book_id = %s", (book_id,))]

    return render_template(
        'books/form.html',
        categories=categories,
        authors=authors,
        book=book,
        current_author_ids=current_author_ids
    )


@books_bp.route('/detail/<int:book_id>', methods=['GET'])
@librarian_required
def detail(book_id):
    book = query_one("SELECT * FROM vw_book_catalog WHERE book_id = %s", (book_id,))
    if not book:
        flash('Book not found.', 'danger')
        return redirect(url_for('books.list_books'))

    # Retrieve all physical copies and their current loan status
    copies = query_all(
        "SELECT bc.copy_id, bc.accession_no, bc.status, bc.acquired_date, "
        "       l.loan_id, l.member_id, m.student_no, CONCAT(u.first_name, ' ', u.last_name) AS borrower_name, "
        "       l.due_date "
        "FROM book_copies bc "
        "LEFT JOIN loans l ON l.copy_id = bc.copy_id AND l.returned_at IS NULL "
        "LEFT JOIN members m ON m.member_id = l.member_id "
        "LEFT JOIN users u ON u.user_id = m.user_id "
        "WHERE bc.book_id = %s "
        "ORDER BY bc.accession_no ASC",
        (book_id,)
    )

    next_accession = generate_accession_no()
    return render_template('books/detail.html', book=book, copies=copies, next_accession=next_accession)


@books_bp.route('/<int:book_id>/copies/add', methods=['POST'])
@librarian_required
def add_copy(book_id):
    accession_no = request.form.get('accession_no', '').strip()
    if not accession_no:
        accession_no = generate_accession_no()

    # Check for duplicate accession number
    existing = query_one("SELECT copy_id FROM book_copies WHERE accession_no = %s", (accession_no,))
    if existing:
        flash(f'Accession number "{accession_no}" is already registered.', 'danger')
        return redirect(url_for('books.detail', book_id=book_id))

    execute_db(
        "INSERT INTO book_copies (book_id, accession_no, status, acquired_date) VALUES (%s, %s, 'available', CURDATE())",
        (book_id, accession_no)
    )
    flash(f'Copy {accession_no} added successfully.', 'success')
    return redirect(url_for('books.detail', book_id=book_id))


@books_bp.route('/copies/<int:copy_id>/status', methods=['POST'])
@librarian_required
def update_copy_status(copy_id):
    new_status = request.form.get('status')
    copy = query_one("SELECT copy_id, book_id, status FROM book_copies WHERE copy_id = %s", (copy_id,))

    if not copy:
        flash('Copy not found.', 'danger')
        return redirect(url_for('books.list_books'))

    if copy['status'] == 'borrowed' and new_status != 'borrowed':
        flash('Cannot manually change status while book copy is actively borrowed. Please process return first.', 'warning')
        return redirect(url_for('books.detail', book_id=copy['book_id']))

    if new_status in ['available', 'lost', 'damaged']:
        execute_db("UPDATE book_copies SET status = %s WHERE copy_id = %s", (new_status, copy_id))
        flash(f'Copy status updated to "{new_status}".', 'success')

    return redirect(url_for('books.detail', book_id=copy['book_id']))


@books_bp.route('/archive/<int:book_id>', methods=['POST'])
@librarian_required
def toggle_archive(book_id):
    book = query_one("SELECT book_id, title, is_archived FROM books WHERE book_id = %s", (book_id,))
    if not book:
        flash('Book not found.', 'danger')
        return redirect(url_for('books.list_books'))

    # If archiving, check if active loans exist for this book
    if not book['is_archived']:
        active_loans = query_one(
            "SELECT COUNT(*) AS total FROM loans l "
            "JOIN book_copies bc ON bc.copy_id = l.copy_id "
            "WHERE bc.book_id = %s AND l.returned_at IS NULL",
            (book_id,)
        )['total']

        if active_loans > 0:
            flash(f'Cannot archive "{book["title"]}". There are currently {active_loans} active loan(s) for this book.', 'danger')
            return redirect(url_for('books.list_books'))

    new_state = 0 if book['is_archived'] else 1
    execute_db("UPDATE books SET is_archived = %s WHERE book_id = %s", (new_state, book_id))
    action_text = 'restored' if new_state == 0 else 'archived'
    flash(f'Book "{book["title"]}" has been {action_text}.', 'info')
    return redirect(url_for('books.list_books'))


@books_bp.route('/browse', methods=['GET'])
@login_required
def browse():
    q = request.args.get('q', '').strip()
    category_id = request.args.get('category_id', '')

    sql = "SELECT * FROM vw_book_catalog WHERE is_archived = 0"
    params = []

    if category_id and category_id.isdigit():
        sql += " AND category_id = %s"
        params.append(int(category_id))

    if q:
        sql += " AND (title LIKE %s OR isbn LIKE %s OR authors LIKE %s)"
        like_term = f"%{q}%"
        params.extend([like_term, like_term, like_term])

    sql += " ORDER BY title ASC"
    books = query_all(sql, params)
    categories = query_all("SELECT category_id, name FROM categories ORDER BY name ASC")

    return render_template('books/browse.html', books=books, categories=categories, q=q, category_id=category_id)
