from flask import Flask, jsonify, request
from flask_cors import CORS
from liquidation_hunter import analyze_symbol, POPULAR_SYMBOLS
import json
import os
import asyncio
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

# 🔥 IMPORT UNTUK TELEGRAM
from telethon import TelegramClient
from telethon.tl.types import PeerChannel
import re

app = Flask(__name__)
CORS(app)

# ==================== KONFIGURASI TELEGRAM ====================
# 🔥 Ambil dari environment variables (set di Koyeb)
TELEGRAM_CONFIG = {
    'api_id': int(os.environ.get('API_ID', 0)),  # GANTI DENGAN API_ID-mu via env var
    'api_hash': os.environ.get('API_HASH', ''),  # GANTI DENGAN API_HASH-mu via env var
    'channel_username': 'BinanceWhaleVolumeAlerts',
    'channel_id': None,  # Akan diisi otomatis
    'session_file': '/tmp/whale_scraper_session'  # 🔥 Pakai /tmp untuk writeable di Koyeb
}

# Inisialisasi client Telegram (akan di-start nanti)
telegram_client = None
whale_messages_cache = []
last_update_time = None

# Flag untuk inisialisasi sekali
app_initialized = False

# ==================== FUNGSI TELEGRAM SCRAPER ====================
async def init_telegram():
    """Inisialisasi koneksi Telegram"""
    global telegram_client, TELEGRAM_CONFIG
    
    # Cek apakah API credentials tersedia
    if not TELEGRAM_CONFIG['api_id'] or not TELEGRAM_CONFIG['api_hash']:
        print("⚠️ API_ID or API_HASH not set. Telegram features disabled.")
        return False
    
    try:
        print(f"🔄 Connecting to Telegram with API ID: {TELEGRAM_CONFIG['api_id']}")
        telegram_client = TelegramClient(
            TELEGRAM_CONFIG['session_file'], 
            TELEGRAM_CONFIG['api_id'], 
            TELEGRAM_CONFIG['api_hash']
        )
        await telegram_client.start()
        
        # Dapatkan entity channel
        entity = await telegram_client.get_entity(TELEGRAM_CONFIG['channel_username'])
        TELEGRAM_CONFIG['channel_id'] = entity.id
        print(f"✅ Telegram connected! Channel: {entity.title} (ID: {entity.id})")
        
        return True
    except Exception as e:
        print(f"❌ Telegram init failed: {e}")
        return False

async def fetch_whale_messages(limit=50):
    """Ambil pesan terbaru dari channel"""
    global telegram_client, whale_messages_cache, last_update_time
    
    if not telegram_client:
        print("⚠️ Telegram client not initialized")
        return []
    
    try:
        entity = await telegram_client.get_entity(TELEGRAM_CONFIG['channel_username'])
        messages = []
        
        # Iterasi pesan terbaru
        async for msg in telegram_client.iter_messages(entity, limit=limit):
            if msg.text and ('LONG' in msg.text or 'SHORT' in msg.text or '💰' in msg.text):
                # Parse pesan whale
                parsed = parse_whale_message(msg.text, msg.date)
                if parsed:
                    messages.append(parsed)
        
        whale_messages_cache = messages
        last_update_time = datetime.now()
        print(f"✅ Fetched {len(messages)} whale messages")
        return messages
        
    except Exception as e:
        print(f"❌ Fetch failed: {e}")
        return whale_messages_cache  # Return cache jika gagal

def parse_whale_message(text, date):
    """Parse format pesan whale"""
    try:
        # Extract pair
        pair_match = re.search(r'#(\w+)', text)
        # Extract type (LONG/SHORT)
        type_match = re.search(r'(LONG|SHORT)', text)
        # Extract volume
        volume_match = re.search(r'(?:Short|Long) Volume\s*:\s*\$(\d+k?)\s*\(%([\d.]+)\)', text)
        # Extract price
        price_match = re.search(r'Price\s*:\s*([\d.]+)', text)
        # Extract sequence
        seq_match = re.search(r'Sequence\s*:\s*(\d+)', text)
        
        if not pair_match or not type_match:
            return None
        
        # Hitung confidence dari emoji
        confidence = len(re.findall(r'[🔴🟢]', text))
        
        # Format price dengan benar
        price_val = float(price_match.group(1)) if price_match else 0
        if price_val > 1000:
            display_price = f"${price_val:,.2f}"
        elif price_val > 1:
            display_price = f"${price_val:.4f}"
        else:
            display_price = f"${price_val:.6f}"
        
        return {
            'id': abs(hash(text + str(date))) % (10**8),  # ID unik
            'pair': pair_match.group(1),
            'type': type_match.group(0),
            'volume': volume_match.group(1) if volume_match else 'N/A',
            'volume_percent': volume_match.group(2) if volume_match else 'N/A',
            'price': price_val,
            'sequence': int(seq_match.group(1)) if seq_match else 0,
            'confidence': confidence,
            'timestamp': date.isoformat() if date else datetime.now().isoformat(),
            'display_price': display_price,
            'raw': text[:100] + '...' if len(text) > 100 else text
        }
    except Exception as e:
        print(f"Parse error: {e}")
        return None

def run_async_fetch():
    """Wrapper untuk menjalankan async function"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(fetch_whale_messages(30))
    except Exception as e:
        print(f"⚠️ Scheduled fetch error: {e}")
    finally:
        loop.close()

# ==================== SCHEDULER UNTUK UPDATE OTOMATIS ====================
try:
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=run_async_fetch, trigger="interval", minutes=5)  # Update setiap 5 menit
    scheduler.start()
    print("✅ Scheduler started - will update every 5 minutes")
    
    # Shutdown scheduler saat app stop
    atexit.register(lambda: scheduler.shutdown())
except Exception as e:
    print(f"⚠️ Scheduler init failed: {e}")

# ==================== ROUTES YANG SUDAH ADA ====================
@app.route('/')
def home():
    return jsonify({
        "name": "DylPredict - Liquidation Hunter API",
        "version": "V14 - Conflict Resolution Engine + Whale Alerts",
        "status": "online",
        "telegram": "connected" if telegram_client else "disconnected (set API_ID & API_HASH)",
        "endpoints": {
            "/analyze/<symbol>": "Analyze specific symbol",
            "/analyze": "Analyze all popular symbols",
            "/whale-alerts": "Get latest whale alerts from Telegram",
            "/whale-alerts/latest": "Get most recent whale alert",
            "/symbols": "List all supported symbols",
            "/health": "Health check"
        }
    })

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy", 
        "timestamp": datetime.now().isoformat(),
        "telegram": "connected" if telegram_client else "disconnected",
        "whale_messages": len(whale_messages_cache),
        "last_update": last_update_time.isoformat() if last_update_time else None
    })

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
        "timestamp": datetime.now().isoformat()
    })

@app.route('/symbols')
def get_symbols():
    """Get list of popular symbols"""
    return jsonify({
        "success": True,
        "symbols": POPULAR_SYMBOLS
    })

# ==================== ROUTE BARU UNTUK WHALE ALERTS ====================
@app.route('/whale-alerts')
def get_whale_alerts():
    """Endpoint untuk mengambil whale alerts"""
    global whale_messages_cache
    
    # Parameter opsional
    limit = request.args.get('limit', default=20, type=int)
    
    # Filter berdasarkan pair jika ada
    pair = request.args.get('pair', default=None, type=str.upper)
    
    if pair:
        filtered = [msg for msg in whale_messages_cache if msg['pair'] == pair]
        data = filtered[:limit]
    else:
        data = whale_messages_cache[:limit]
    
    return jsonify({
        "success": True,
        "count": len(data),
        "total": len(whale_messages_cache),
        "data": data,
        "last_update": last_update_time.isoformat() if last_update_time else None,
        "source": "Telegram Channel @BinanceWhaleVolumeAlerts"
    })

@app.route('/whale-alerts/latest')
def get_latest_whale():
    """Endpoint untuk mengambil alert terbaru"""
    if whale_messages_cache:
        return jsonify({
            "success": True,
            "data": whale_messages_cache[0]
        })
    return jsonify({
        "success": False,
        "error": "No whale alerts yet"
    }), 404

@app.route('/whale-alerts/stats')
def get_whale_stats():
    """Statistik whale alerts"""
    if not whale_messages_cache:
        return jsonify({"success": True, "data": {}})
    
    # Hitung statistik
    total = len(whale_messages_cache)
    long_count = sum(1 for msg in whale_messages_cache if msg['type'] == 'LONG')
    short_count = sum(1 for msg in whale_messages_cache if msg['type'] == 'SHORT')
    
    # Pair terpopuler
    pairs = {}
    for msg in whale_messages_cache:
        pairs[msg['pair']] = pairs.get(msg['pair'], 0) + 1
    
    top_pairs = sorted(pairs.items(), key=lambda x: x[1], reverse=True)[:5]
    
    return jsonify({
        "success": True,
        "data": {
            "total_messages": total,
            "long_signals": long_count,
            "short_signals": short_count,
            "long_short_ratio": round(long_count / short_count, 2) if short_count > 0 else 0,
            "top_pairs": [{"pair": p, "count": c} for p, c in top_pairs],
            "last_update": last_update_time.isoformat() if last_update_time else None
        }
    })

# ==================== FALLBACK DATA (Jika Telegram gagal) ====================
def get_dummy_whale_data():
    """Data dummy untuk testing jika Telegram offline"""
    return [
        {
            'pair': 'BTCUSDT',
            'type': 'SHORT',
            'volume': '31k',
            'volume_percent': '0.014',
            'price': 52400.50,
            'display_price': '$52,400.50',
            'confidence': 2,
            'timestamp': datetime.now().isoformat(),
            'timeString': datetime.now().strftime('%H:%M:%S')
        },
        {
            'pair': 'ETHUSDT',
            'type': 'LONG',
            'volume': '43k',
            'volume_percent': '0.005',
            'price': 327.02,
            'display_price': '$327.02',
            'confidence': 4,
            'timestamp': datetime.now().isoformat(),
            'timeString': datetime.now().strftime('%H:%M:%S')
        },
        {
            'pair': 'XRPUSDT',
            'type': 'SHORT',
            'volume': '59k',
            'volume_percent': '0.005',
            'price': 1.5343,
            'display_price': '$1.5343',
            'confidence': 2,
            'timestamp': datetime.now().isoformat(),
            'timeString': datetime.now().strftime('%H:%M:%S')
        }
    ]

# ==================== INITIALIZATION PERTAMA KALI ====================
@app.before_request
def initialize_once():
    """Jalanin sekali saat pertama kali request (menggantikan before_first_request)"""
    global app_initialized, whale_messages_cache
    
    if not app_initialized:
        print("🚀 First request - initializing Telegram...")
        
        # Cek apakah API credentials tersedia
        if not TELEGRAM_CONFIG['api_id'] or not TELEGRAM_CONFIG['api_hash']:
            print("⚠️ API_ID/API_HASH not set. Using dummy data for whale alerts.")
            whale_messages_cache = get_dummy_whale_data()
            app_initialized = True
            return
        
        # Inisialisasi Telegram
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Inisialisasi koneksi Telegram
            init_success = loop.run_until_complete(init_telegram())
            
            if init_success:
                # Ambil pesan pertama
                loop.run_until_complete(fetch_whale_messages(30))
                print(f"✅ Telegram initialized with {len(whale_messages_cache)} messages")
            else:
                # Fallback ke dummy data
                print("⚠️ Using dummy data as fallback")
                whale_messages_cache = get_dummy_whale_data()
                
        except Exception as e:
            print(f"❌ Initialization error: {e}")
            whale_messages_cache = get_dummy_whale_data()
        finally:
            loop.close()
        
        app_initialized = True

# ==================== MAIN ====================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    print(f"🚀 DylPredict API starting on port {port}")
    print(f"📊 Python version: {os.sys.version}")
    print(f"🔧 Debug mode: {debug_mode}")
    
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
