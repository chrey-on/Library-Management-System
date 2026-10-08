from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g, abort
from werkzeug.security import check_password_hash, generate_password_hash
from app.db import query_one, execute_db

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

def login_required(view):
    """Decorator to require an authenticated session."""
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        return view(*args, **kwargs)
    return wrapped_view

def librarian_required(view):
    """Decorator to restrict access exclusively to librarians / administrators."""
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        if session.get('role') != 'librarian':
            abort(403)
        return view(*args, **kwargs)
    return wrapped_view

def member_required(view):
    """Decorator to restrict access exclusively to student members."""
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        if session.get('role') != 'member':
            abort(403)
        return view(*args, **kwargs)
    return wrapped_view


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # If user is already logged in, redirect to respective dashboard
    if 'user_id' in session:
        if session.get('role') == 'librarian':
            return redirect(url_for('dashboard.librarian_dashboard'))
        return redirect(url_for('dashboard.member_dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        remember = request.form.get('remember')

        if not username or not password:
            flash('Please enter both username and password.', 'danger')
            return render_template('auth/login.html', username=username)

        user = query_one(
            "SELECT user_id, username, password_hash, role, first_name, last_name, email, is_active "
            "FROM users WHERE username = %s",
            (username,)
        )

        if not user or not check_password_hash(user['password_hash'], password):
            flash('Invalid username or password.', 'danger')
            return render_template('auth/login.html', username=username)

        if not user['is_active']:
            flash('Your account has been deactivated. Please contact the librarian.', 'danger')
            return render_template('auth/login.html', username=username)

        # Successful authentication: establish session
        session.clear()
        session['user_id'] = user['user_id']
        session['username'] = user['username']
        session['role'] = user['role']
        session['full_name'] = f"{user['first_name']} {user['last_name']}"

        # Retrieve member_id if the user is a member
        if user['role'] == 'member':
            member = query_one("SELECT member_id, student_no FROM members WHERE user_id = %s", (user['user_id'],))
            if member:
                session['member_id'] = member['member_id']
                session['student_no'] = member['student_no']

        if remember:
            session.permanent = True

        flash(f"Welcome back, {user['first_name']}!", 'success')

        next_page = request.args.get('next')
        if next_page and next_page.startswith('/'):
            return redirect(next_page)

        if user['role'] == 'librarian':
            return redirect(url_for('dashboard.librarian_dashboard'))
        else:
            return redirect(url_for('dashboard.member_dashboard'))

    return render_template('auth/login.html')


@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('You have been successfully logged out.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not current_password or not new_password or not confirm_password:
            flash('All password fields are required.', 'danger')
            return render_template('auth/change_password.html')

        if new_password != confirm_password:
            flash('New password and confirmation password do not match.', 'danger')
            return render_template('auth/change_password.html')

        if len(new_password) < 6:
            flash('New password must be at least 6 characters long.', 'danger')
            return render_template('auth/change_password.html')

        user = query_one(
            "SELECT password_hash FROM users WHERE user_id = %s",
            (session['user_id'],)
        )

        if not user or not check_password_hash(user['password_hash'], current_password):
            flash('Current password is incorrect.', 'danger')
            return render_template('auth/change_password.html')

        # Update password hash in database
        new_hash = generate_password_hash(new_password)
        execute_db(
            "UPDATE users SET password_hash = %s WHERE user_id = %s",
            (new_hash, session['user_id'])
        )

        flash('Your password has been changed successfully.', 'success')
        if session.get('role') == 'librarian':
            return redirect(url_for('dashboard.librarian_dashboard'))
        return redirect(url_for('dashboard.member_dashboard'))

    return render_template('auth/change_password.html')
