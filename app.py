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
TELEGRAM_CONFIG = {
    'api_id': 1234567,  # 🔥 GANTI DENGAN API_ID-mu (dari my.telegram.org)
    'api_hash': 'your_api_hash_here',  # 🔥 GANTI DENGAN API_HASH-mu
    'channel_username': 'BinanceWhaleVolumeAlerts',
    'channel_id': None,  # Akan diisi otomatis
    'session_file': 'whale_scraper_session'
}

# Inisialisasi client Telegram (akan di-start nanti)
telegram_client = None
whale_messages_cache = []
last_update_time = None

# ==================== FUNGSI TELEGRAM SCRAPER ====================
async def init_telegram():
    """Inisialisasi koneksi Telegram"""
    global telegram_client, TELEGRAM_CONFIG
    
    try:
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
            if msg.text and ('LONG' in msg.text or 'SHORT' in msg.text):
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
        
        return {
            'id': hash(text + str(date)),
            'pair': pair_match.group(1),
            'type': type_match.group(0),
            'volume': volume_match.group(1) if volume_match else 'N/A',
            'volume_percent': volume_match.group(2) if volume_match else 'N/A',
            'price': float(price_match.group(1)) if price_match else 0,
            'sequence': int(seq_match.group(1)) if seq_match else 0,
            'confidence': confidence,
            'timestamp': date.isoformat() if date else datetime.now().isoformat(),
            'display_price': f"${float(price_match.group(1)):.2f}" if price_match and float(price_match.group(1)) > 1 else f"${float(price_match.group(1)):.6f}" if price_match else '$0.00',
            'raw': text[:100] + '...'
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
    finally:
        loop.close()

# ==================== SCHEDULER UNTUK UPDATE OTOMATIS ====================
scheduler = BackgroundScheduler()
scheduler.add_job(func=run_async_fetch, trigger="interval", minutes=5)  # Update setiap 5 menit
scheduler.start()

# Shutdown scheduler saat app stop
atexit.register(lambda: scheduler.shutdown())

# ==================== ROUTES YANG SUDAH ADA ====================
@app.route('/')
def home():
    return jsonify({
        "name": "DylPredict - Liquidation Hunter API",
        "version": "V14 - Conflict Resolution Engine + Whale Alerts",
        "status": "online",
        "telegram": "connected" if telegram_client else "disconnected",
        "endpoints": {
            "/analyze/<symbol>": "Analyze specific symbol",
            "/analyze": "Analyze all popular symbols",
            "/whale-alerts": "Get latest whale alerts from Telegram",
            "/health": "Health check"
        }
    })

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy", 
        "timestamp": datetime.now().isoformat(),
        "telegram": "connected" if telegram_client else "disconnected",
        "whale_messages": len(whale_messages_cache)
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
    
    return jsonify({
        "success": True,
        "count": min(len(whale_messages_cache), limit),
        "data": whale_messages_cache[:limit],
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

# ==================== INITIALIZATION SAAT STARTUP ====================
@app.before_first_request
def startup():
    """Jalanin sekali saat pertama kali request"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        # Inisialisasi koneksi Telegram
        loop.run_until_complete(init_telegram())
        # Ambil pesan pertama
        loop.run_until_complete(fetch_whale_messages(30))
    finally:
        loop.close()

# ==================== MAIN ====================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
