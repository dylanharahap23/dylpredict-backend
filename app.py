from flask import Flask, jsonify, request
from flask_cors import CORS
from liquidation_hunter import analyze_symbol, POPULAR_SYMBOLS
import json
import os  # 🔥 TAMBAHIN INI!

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend

@app.route('/')
def home():
    return jsonify({
        "name": "DylPredict - Liquidation Hunter API",
        "version": "V14 - Conflict Resolution Engine",
        "status": "online",
        "endpoints": {
            "/analyze/<symbol>": "Analyze specific symbol (e.g., /analyze/BTCUSDT)",
            "/analyze": "Analyze all popular symbols",
            "/health": "Health check"
        }
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "timestamp": __import__('datetime').datetime.now().isoformat()})

@app.route('/analyze/<symbol>')
def analyze_single(symbol):
    """Analyze a single cryptocurrency symbol"""
    try:
        symbol = symbol.upper()
        result = analyze_symbol(symbol)
        
        if result:
            return jsonify({
                "success": True,
                "data": result,
                "symbol": symbol
            })
        else:
            return jsonify({
                "success": False,
                "error": f"Failed to fetch data for {symbol}",
                "symbol": symbol
            }), 400
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "symbol": symbol
        }), 500

@app.route('/analyze')
def analyze_all():
    """Analyze all popular symbols"""
    results = []
    
    for symbol in POPULAR_SYMBOLS:
        try:
            result = analyze_symbol(symbol)
            if result:
                results.append(result)
        except Exception as e:
            print(f"Error analyzing {symbol}: {e}")
    
    return jsonify({
        "success": True,
        "count": len(results),
        "data": results,
        "timestamp": __import__('datetime').datetime.now().isoformat()
    })

@app.route('/symbols')
def get_symbols():
    """Get list of popular symbols"""
    return jsonify({
        "success": True,
        "symbols": POPULAR_SYMBOLS
    })

if __name__ == '__main__':
    # 🔥 PRODUCTION SETUP FOR RENDER
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
