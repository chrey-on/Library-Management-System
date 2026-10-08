from flask import Blueprint, render_template
from app.routes.auth import librarian_required

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')

@reports_bp.route('/')
@librarian_required
def reports_home():
    return render_template('reports/index.html')
