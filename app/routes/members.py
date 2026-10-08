from flask import Blueprint, render_template
from app.routes.auth import librarian_required, member_required

members_bp = Blueprint('members', __name__, url_prefix='/members')

@members_bp.route('/')
@librarian_required
def list_members():
    return render_template('members/list.html')

@members_bp.route('/my-loans')
@member_required
def my_loans():
    return render_template('members/my_loans.html')

@members_bp.route('/my-fines')
@member_required
def my_fines():
    return render_template('members/my_fines.html')
