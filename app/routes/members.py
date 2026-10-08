from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort
from werkzeug.security import generate_password_hash
from app.routes.auth import librarian_required, member_required, login_required
from app.db import query_all, query_one, execute_db, get_db

members_bp = Blueprint('members', __name__, url_prefix='/members')

@members_bp.route('/', methods=['GET'])
@librarian_required
def list_members():
    q = request.args.get('q', '').strip()
    course_id = request.args.get('course_id', '')
    status_filter = request.args.get('status', 'all')  # 'all', 'active', 'inactive'

    sql = """
        SELECT 
            m.member_id,
            m.student_no,
            m.year_level,
            m.contact_no,
            u.user_id,
            u.username,
            u.first_name,
            u.last_name,
            u.email,
            u.is_active,
            c.course_id,
            c.course_code,
            c.course_name,
            (SELECT COUNT(*) FROM loans l WHERE l.member_id = m.member_id AND l.returned_at IS NULL) AS active_loans,
            (SELECT COALESCE(SUM(f.amount), 0) FROM fines f 
             JOIN loans l ON l.loan_id = f.loan_id 
             WHERE l.member_id = m.member_id AND f.is_paid = 0) AS unpaid_fines
        FROM members m
        JOIN users u ON u.user_id = m.user_id
        JOIN courses c ON c.course_id = m.course_id
        WHERE 1=1
    """
    params = []

    if status_filter == 'active':
        sql += " AND u.is_active = 1"
    elif status_filter == 'inactive':
        sql += " AND u.is_active = 0"

    if course_id and course_id.isdigit():
        sql += " AND m.course_id = %s"
        params.append(int(course_id))

    if q:
        sql += " AND (m.student_no LIKE %s OR u.username LIKE %s OR u.first_name LIKE %s OR u.last_name LIKE %s OR u.email LIKE %s)"
        like_term = f"%{q}%"
        params.extend([like_term, like_term, like_term, like_term, like_term])

    sql += " ORDER BY u.last_name ASC, u.first_name ASC"
    members = query_all(sql, params)
    courses = query_all("SELECT course_id, course_code, course_name FROM courses ORDER BY course_code ASC")

    return render_template(
        'members/list.html',
        members=members,
        courses=courses,
        q=q,
        course_id=course_id,
        status_filter=status_filter
    )


@members_bp.route('/create', methods=['GET', 'POST'])
@librarian_required
def create_member():
    if request.method == 'POST':
        student_no = request.form.get('student_no', '').strip()
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        course_id = request.form.get('course_id')
        year_level = request.form.get('year_level')
        contact_no = request.form.get('contact_no', '').strip()
        password = request.form.get('password', '').strip()

        # Validate required fields
        if not student_no or not username or not email or not first_name or not last_name or not course_id or not year_level or not password:
            flash('All required fields must be filled out.', 'danger')
            courses = query_all("SELECT course_id, course_code, course_name FROM courses ORDER BY course_code ASC")
            return render_template('members/form.html', courses=courses, member=None)

        # Check unique constraints
        if query_one("SELECT user_id FROM users WHERE username = %s", (username,)):
            flash(f'Username "{username}" is already taken.', 'danger')
            courses = query_all("SELECT course_id, course_code, course_name FROM courses ORDER BY course_code ASC")
            return render_template('members/form.html', courses=courses, member=None)

        if query_one("SELECT user_id FROM users WHERE email = %s", (email,)):
            flash(f'Email address "{email}" is already registered.', 'danger')
            courses = query_all("SELECT course_id, course_code, course_name FROM courses ORDER BY course_code ASC")
            return render_template('members/form.html', courses=courses, member=None)

        if query_one("SELECT member_id FROM members WHERE student_no = %s", (student_no,)):
            flash(f'Student Number "{student_no}" is already registered.', 'danger')
            courses = query_all("SELECT course_id, course_code, course_name FROM courses ORDER BY course_code ASC")
            return render_template('members/form.html', courses=courses, member=None)

        db = get_db()
        try:
            # 1. Create user account
            pw_hash = generate_password_hash(password)
            user_res = execute_db(
                "INSERT INTO users (username, password_hash, role, first_name, last_name, email, is_active) "
                "VALUES (%s, %s, 'member', %s, %s, %s, 1)",
                (username, pw_hash, first_name, last_name, email),
                autocommit=False
            )
            new_user_id = user_res['last_id']

            # 2. Create member profile
            member_res = execute_db(
                "INSERT INTO members (user_id, student_no, course_id, year_level, contact_no) "
                "VALUES (%s, %s, %s, %s, %s)",
                (new_user_id, student_no, int(course_id), int(year_level), contact_no or None),
                autocommit=False
            )
            new_member_id = member_res['last_id']

            db.commit()
            flash(f'Member "{first_name} {last_name}" ({student_no}) registered successfully.', 'success')
            return redirect(url_for('members.detail', member_id=new_member_id))
        except Exception as e:
            db.rollback()
            flash(f'Error registering member: {str(e)}', 'danger')

    courses = query_all("SELECT course_id, course_code, course_name FROM courses ORDER BY course_code ASC")
    return render_template('members/form.html', courses=courses, member=None)


@members_bp.route('/edit/<int:member_id>', methods=['GET', 'POST'])
@librarian_required
def edit_member(member_id):
    member = query_one(
        "SELECT m.*, u.username, u.first_name, u.last_name, u.email, u.is_active "
        "FROM members m "
        "JOIN users u ON u.user_id = m.user_id "
        "WHERE m.member_id = %s",
        (member_id,)
    )
    if not member:
        flash('Member not found.', 'danger')
        return redirect(url_for('members.list_members'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        course_id = request.form.get('course_id')
        year_level = request.form.get('year_level')
        contact_no = request.form.get('contact_no', '').strip()
        new_password = request.form.get('new_password', '').strip()

        if not email or not first_name or not last_name or not course_id or not year_level:
            flash('Required fields cannot be empty.', 'danger')
            return redirect(url_for('members.edit_member', member_id=member_id))

        # Check unique email collision
        existing_email = query_one(
            "SELECT user_id FROM users WHERE email = %s AND user_id != %s",
            (email, member['user_id'])
        )
        if existing_email:
            flash(f'Email address "{email}" is already used by another account.', 'danger')
            return redirect(url_for('members.edit_member', member_id=member_id))

        db = get_db()
        try:
            # Update user table
            if new_password:
                pw_hash = generate_password_hash(new_password)
                execute_db(
                    "UPDATE users SET first_name = %s, last_name = %s, email = %s, password_hash = %s WHERE user_id = %s",
                    (first_name, last_name, email, pw_hash, member['user_id']),
                    autocommit=False
                )
            else:
                execute_db(
                    "UPDATE users SET first_name = %s, last_name = %s, email = %s WHERE user_id = %s",
                    (first_name, last_name, email, member['user_id']),
                    autocommit=False
                )

            # Update member table
            execute_db(
                "UPDATE members SET course_id = %s, year_level = %s, contact_no = %s WHERE member_id = %s",
                (int(course_id), int(year_level), contact_no or None, member_id),
                autocommit=False
            )

            db.commit()
            flash('Member profile updated successfully.', 'success')
            return redirect(url_for('members.detail', member_id=member_id))
        except Exception as e:
            db.rollback()
            flash(f'Error updating member: {str(e)}', 'danger')

    courses = query_all("SELECT course_id, course_code, course_name FROM courses ORDER BY course_code ASC")
    return render_template('members/form.html', courses=courses, member=member)


@members_bp.route('/toggle-status/<int:member_id>', methods=['POST'])
@librarian_required
def toggle_status(member_id):
    member = query_one(
        "SELECT m.member_id, m.user_id, u.first_name, u.last_name, u.is_active "
        "FROM members m JOIN users u ON u.user_id = m.user_id WHERE m.member_id = %s",
        (member_id,)
    )
    if not member:
        flash('Member not found.', 'danger')
        return redirect(url_for('members.list_members'))

    # If deactivating, check if active loans exist
    if member['is_active']:
        active_loans = query_one(
            "SELECT COUNT(*) AS total FROM loans WHERE member_id = %s AND returned_at IS NULL",
            (member_id,)
        )['total']
        if active_loans > 0:
            flash(f'Cannot deactivate {member["first_name"]} {member["last_name"]}. They currently have {active_loans} unreturned book(s).', 'danger')
            return redirect(url_for('members.detail', member_id=member_id))

    new_state = 0 if member['is_active'] else 1
    execute_db("UPDATE users SET is_active = %s WHERE user_id = %s", (new_state, member['user_id']))
    action_text = 'activated' if new_state == 1 else 'deactivated'
    flash(f'Member account has been {action_text}.', 'info')
    return redirect(url_for('members.detail', member_id=member_id))


@members_bp.route('/detail/<int:member_id>', methods=['GET'])
@librarian_required
def detail(member_id):
    member = query_one(
        "SELECT m.*, u.user_id, u.username, u.first_name, u.last_name, u.email, u.is_active, u.created_at AS member_since, "
        "       c.course_code, c.course_name "
        "FROM members m "
        "JOIN users u ON u.user_id = m.user_id "
        "JOIN courses c ON c.course_id = m.course_id "
        "WHERE m.member_id = %s",
        (member_id,)
    )
    if not member:
        flash('Member not found.', 'danger')
        return redirect(url_for('members.list_members'))

    # Loans for this member
    loans = query_all(
        "SELECT * FROM vw_loan_details WHERE member_id = %s ORDER BY borrowed_at DESC",
        (member_id,)
    )

    # Fine summary
    fines = query_all(
        "SELECT f.*, l.borrowed_at, l.due_date, l.returned_at, b.title, bc.accession_no "
        "FROM fines f "
        "JOIN loans l ON l.loan_id = f.loan_id "
        "JOIN book_copies bc ON bc.copy_id = l.copy_id "
        "JOIN books b ON b.book_id = bc.book_id "
        "WHERE l.member_id = %s "
        "ORDER BY f.created_at DESC",
        (member_id,)
    )

    unpaid_total = sum(f['amount'] for f in fines if not f['is_paid'])
    active_loans_count = sum(1 for l in loans if l['returned_at'] is None)

    return render_template(
        'members/detail.html',
        member=member,
        loans=loans,
        fines=fines,
        unpaid_total=unpaid_total,
        active_loans_count=active_loans_count
    )


# ---------------------------------------------------------------------
# Student Self-Service Portal Routes
# ---------------------------------------------------------------------

@members_bp.route('/my-loans', methods=['GET'])
@member_required
def my_loans():
    member_id = session.get('member_id')
    if not member_id:
        flash('Member account record not found.', 'danger')
        return redirect(url_for('auth.login'))

    loans = query_all(
        "SELECT * FROM vw_loan_details WHERE member_id = %s ORDER BY borrowed_at DESC",
        (member_id,)
    )
    return render_template('members/my_loans.html', loans=loans)


@members_bp.route('/my-fines', methods=['GET'])
@member_required
def my_fines():
    member_id = session.get('member_id')
    if not member_id:
        flash('Member account record not found.', 'danger')
        return redirect(url_for('auth.login'))

    fines = query_all(
        "SELECT f.*, l.borrowed_at, l.due_date, l.returned_at, b.title, bc.accession_no "
        "FROM fines f "
        "JOIN loans l ON l.loan_id = f.loan_id "
        "JOIN book_copies bc ON bc.copy_id = l.copy_id "
        "JOIN books b ON b.book_id = bc.book_id "
        "WHERE l.member_id = %s "
        "ORDER BY f.created_at DESC",
        (member_id,)
    )
    unpaid_total = sum(f['amount'] for f in fines if not f['is_paid'])
    return render_template('members/my_fines.html', fines=fines, unpaid_total=unpaid_total)
