from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.routes.auth import librarian_required
from app.db import query_all, query_one, execute_db

categories_bp = Blueprint('categories', __name__, url_prefix='/categories')

@categories_bp.route('/', methods=['GET'])
@librarian_required
def list_categories():
    # Fetch all categories along with count of active books
    categories = query_all(
        "SELECT c.category_id, c.name, c.description, "
        "       COUNT(b.book_id) AS book_count "
        "FROM categories c "
        "LEFT JOIN books b ON b.category_id = c.category_id AND b.is_archived = 0 "
        "GROUP BY c.category_id, c.name, c.description "
        "ORDER BY c.name ASC"
    )
    return render_template('categories/list.html', categories=categories)


@categories_bp.route('/create', methods=['POST'])
@librarian_required
def create_category():
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()

    if not name:
        flash('Category name is required.', 'danger')
        return redirect(url_for('categories.list_categories'))

    # Check for duplicate category name
    existing = query_one("SELECT category_id FROM categories WHERE name = %s", (name,))
    if existing:
        flash(f'Category "{name}" already exists.', 'danger')
        return redirect(url_for('categories.list_categories'))

    execute_db(
        "INSERT INTO categories (name, description) VALUES (%s, %s)",
        (name, description or None)
    )
    flash(f'Category "{name}" created successfully.', 'success')
    return redirect(url_for('categories.list_categories'))


@categories_bp.route('/edit/<int:category_id>', methods=['POST'])
@librarian_required
def edit_category(category_id):
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()

    if not name:
        flash('Category name cannot be empty.', 'danger')
        return redirect(url_for('categories.list_categories'))

    existing = query_one(
        "SELECT category_id FROM categories WHERE name = %s AND category_id != %s",
        (name, category_id)
    )
    if existing:
        flash(f'Another category named "{name}" already exists.', 'danger')
        return redirect(url_for('categories.list_categories'))

    execute_db(
        "UPDATE categories SET name = %s, description = %s WHERE category_id = %s",
        (name, description or None, category_id)
    )
    flash('Category updated successfully.', 'success')
    return redirect(url_for('categories.list_categories'))


@categories_bp.route('/delete/<int:category_id>', methods=['POST'])
@librarian_required
def delete_category(category_id):
    # Check if category has linked books (Referential integrity check)
    book_count = query_one(
        "SELECT COUNT(*) AS total FROM books WHERE category_id = %s",
        (category_id,)
    )['total']

    if book_count > 0:
        flash(f'Cannot delete category. It is currently referenced by {book_count} book(s).', 'danger')
        return redirect(url_for('categories.list_categories'))

    execute_db("DELETE FROM categories WHERE category_id = %s", (category_id,))
    flash('Category deleted successfully.', 'success')
    return redirect(url_for('categories.list_categories'))
