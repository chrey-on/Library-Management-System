from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.routes.auth import librarian_required
from app.db import query_all, query_one, execute_db

authors_bp = Blueprint('authors', __name__, url_prefix='/authors')

@authors_bp.route('/', methods=['GET'])
@librarian_required
def list_authors():
    # Fetch all authors along with count of books written
    authors = query_all(
        "SELECT a.author_id, a.first_name, a.last_name, "
        "       COUNT(ba.book_id) AS book_count "
        "FROM authors a "
        "LEFT JOIN book_authors ba ON ba.author_id = a.author_id "
        "GROUP BY a.author_id, a.first_name, a.last_name "
        "ORDER BY a.last_name ASC, a.first_name ASC"
    )
    return render_template('authors/list.html', authors=authors)


@authors_bp.route('/create', methods=['POST'])
@librarian_required
def create_author():
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()

    if not first_name or not last_name:
        flash('Both first name and last name are required.', 'danger')
        return redirect(url_for('authors.list_authors'))

    # Check for duplicate author name
    existing = query_one(
        "SELECT author_id FROM authors WHERE first_name = %s AND last_name = %s",
        (first_name, last_name)
    )
    if existing:
        flash(f'Author "{first_name} {last_name}" already exists.', 'warning')
        return redirect(url_for('authors.list_authors'))

    execute_db(
        "INSERT INTO authors (first_name, last_name) VALUES (%s, %s)",
        (first_name, last_name)
    )
    flash(f'Author "{first_name} {last_name}" created successfully.', 'success')
    return redirect(url_for('authors.list_authors'))


@authors_bp.route('/edit/<int:author_id>', methods=['POST'])
@librarian_required
def edit_author(author_id):
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()

    if not first_name or not last_name:
        flash('Both first name and last name are required.', 'danger')
        return redirect(url_for('authors.list_authors'))

    execute_db(
        "UPDATE authors SET first_name = %s, last_name = %s WHERE author_id = %s",
        (first_name, last_name, author_id)
    )
    flash('Author updated successfully.', 'success')
    return redirect(url_for('authors.list_authors'))


@authors_bp.route('/delete/<int:author_id>', methods=['POST'])
@librarian_required
def delete_author(author_id):
    # Check if author has linked books
    book_count = query_one(
        "SELECT COUNT(*) AS total FROM book_authors WHERE author_id = %s",
        (author_id,)
    )['total']

    if book_count > 0:
        flash(f'Cannot delete author. Linked to {book_count} book(s).', 'danger')
        return redirect(url_for('authors.list_authors'))

    execute_db("DELETE FROM authors WHERE author_id = %s", (author_id,))
    flash('Author deleted successfully.', 'success')
    return redirect(url_for('authors.list_authors'))
