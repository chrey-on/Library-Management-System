import os
import socket
from app import create_app

app = create_app()

def get_local_ip():
    """Finds the LAN IP address of this machine."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

if __name__ == '__main__':
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', 5000))
    debug_mode = os.getenv('FLASK_DEBUG', '1') == '1'
    
    local_ip = get_local_ip()
    print("=" * 60)
    print(f"🚀 Library Management System is running!")
    print(f"   • On this PC:       http://localhost:{port}")
    print(f"   • On other devices: http://{local_ip}:{port}")
    print(f"   (Ensure other devices are connected to the same Wi-Fi)")
    print("=" * 60)
    
    app.run(host=host, port=port, debug=debug_mode)
