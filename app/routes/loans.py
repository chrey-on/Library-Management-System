from flask import Blueprint, render_template
from app.routes.auth import librarian_required

loans_bp = Blueprint('loans', __name__, url_prefix='/loans')

@loans_bp.route('/')
@librarian_required
def list_loans():
    return render_template('loans/list.html')

@loans_bp.route('/issue')
@librarian_required
def issue_loan():
    return render_template('loans/issue.html')

@loans_bp.route('/return')
@librarian_required
def return_loan():
    return render_template('loans/return.html')

@loans_bp.route('/fines')
@librarian_required
def list_fines():
    return render_template('loans/fines.html')
