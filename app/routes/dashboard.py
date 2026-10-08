from flask import Blueprint, render_template, session
from app.routes.auth import login_required, librarian_required, member_required

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

@dashboard_bp.route('/librarian')
@librarian_required
def librarian_dashboard():
    return render_template('dashboard/librarian.html')

@dashboard_bp.route('/member')
@member_required
def member_dashboard():
    return render_template('dashboard/member.html')
