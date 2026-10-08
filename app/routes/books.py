from flask import Blueprint, render_template
from app.routes.auth import librarian_required, login_required

books_bp = Blueprint('books', __name__, url_prefix='/books')

@books_bp.route('/')
@librarian_required
def list_books():
    return render_template('books/list.html')

@books_bp.route('/browse')
@login_required
def browse():
    return render_template('books/browse.html')
