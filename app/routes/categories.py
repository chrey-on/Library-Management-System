from flask import Blueprint, render_template
from app.routes.auth import librarian_required, login_required

categories_bp = Blueprint('categories', __name__, url_prefix='/categories')

@categories_bp.route('/')
@librarian_required
def list_categories():
    return render_template('categories/list.html')
