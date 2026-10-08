import os
from app import create_app

app = create_app()

if __name__ == '__main__':
    # Run development server on http://127.0.0.1:5000
    debug_mode = os.getenv('FLASK_DEBUG', '1') == '1'
    app.run(host='127.0.0.1', port=5000, debug=debug_mode)
