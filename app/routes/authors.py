from flask import Blueprint, render_template
from app.routes.auth import librarian_required

authors_bp = Blueprint('authors', __name__, url_prefix='/authors')

@authors_bp.route('/')
@librarian_required
def list_authors():
    return render_template('authors/list.html')
