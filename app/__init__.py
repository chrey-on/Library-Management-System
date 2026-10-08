from flask import Flask, render_template, session, redirect, url_for, g
from config import Config
from app.db import close_db, query_one

def create_app(config_class=Config):
    """Application factory for Library Management System."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.books import books_bp
    from app.routes.categories import categories_bp
    from app.routes.authors import authors_bp
    from app.routes.members import members_bp
    from app.routes.loans import loans_bp
    from app.routes.reports import reports_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(books_bp)
    app.register_blueprint(categories_bp)
    app.register_blueprint(authors_bp)
    app.register_blueprint(members_bp)
    app.register_blueprint(loans_bp)
    app.register_blueprint(reports_bp)

    # Teardown DB connection at end of each request
    app.teardown_appcontext(close_db)

    # Global context processor to make current user and system settings accessible to templates
    @app.context_processor
    def inject_user():
        current_user = None
        if 'user_id' in session:
            current_user = query_one(
                "SELECT user_id, username, role, first_name, last_name, email "
                "FROM users WHERE user_id = %s AND is_active = 1",
                (session['user_id'],)
            )
        return dict(current_user=current_user)

    # Custom Error Handlers
    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        return render_template('errors/500.html'), 500

    # Default root route redirecting to dashboard or login
    @app.route('/')
    def index():
        if 'user_id' in session:
            if session.get('role') == 'librarian':
                return redirect(url_for('dashboard.librarian_dashboard'))
            else:
                return redirect(url_for('dashboard.member_dashboard'))
        return redirect(url_for('auth.login'))

    return app
