from app import app
print("Starting Flask server...")
print("Open your browser and go to: http://127.0.0.1:5000")
print("Press Ctrl+C to stop the server")
app.run(host='127.0.0.1', port=5000, debug=True)

