#!/usr/bin/env python3
"""
🔥 BINANCE LIQUIDATION HUNTER V14 - CONFLICT RESOLUTION ENGINE
Optimized for Render & PythonAnywhere
Perspektif Market Maker: Follow the liquidity, not the price
"""

import requests
from datetime import datetime
import urllib3
import numpy as np
from typing import Optional, Dict, Tuple, Any, List
import os
import time

# Nonaktifkan SSL warning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ================= CONFIG =================
DEFAULT_TIMEOUT = 10  # Naikin timeout biar gak gampang gagal
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

class BinanceFetcher:
    """Centralized data fetching with error handling - Production Ready"""
    
    def __init__(self, symbol: str):
        self.symbol = symbol.upper()
        self.BASE_URL = "https://fapi.binance.com"  # Futures API
        self.TIMEOUT = DEFAULT_TIMEOUT
        
        # Buat session dengan konfigurasi optimal
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive"
        })
        self.session.verify = False  # Skip SSL verification untuk stability
        
    def fetch(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Any]:
        """
        Fetch data dari Binance dengan error handling komprehensif
        """
        try:
            url = f"{self.BASE_URL}{endpoint}"
            
            # Logging untuk debug (bisa diaktifkan kalau perlu)
            # print(f"🌐 Fetching: {url}")
            
            response = self.session.get(
                url, 
                params=params, 
                timeout=self.TIMEOUT,
                allow_redirects=True
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"❌ HTTP {response.status_code}: {url}")
                return None
                
        except requests.exceptions.Timeout:
            print(f"⏰ Timeout: {endpoint}")
            return None
        except requests.exceptions.ConnectionError:
            print(f"🔌 Connection Error: {endpoint}")
            return None
        except requests.exceptions.RequestException as e:
            print(f"❌ Request Exception: {e}")
            return None
        except Exception as e:
            print(f"💥 Unexpected Error: {e}")
            return None
    
    def get_price(self) -> Optional[float]:
        """Get current price"""
        try:
            data = self.fetch("/fapi/v1/ticker/price", {"symbol": self.symbol})
            return float(data["price"]) if data and "price" in data else None
        except:
            return None
    
    def get_24h_change(self) -> Optional[float]:
        """Get 24h price change percentage"""
        try:
            data = self.fetch("/fapi/v1/ticker/24hr", {"symbol": self.symbol})
            return float(data["priceChangePercent"]) if data and "priceChangePercent" in data else None
        except:
            return None
    
    def get_orderbook_ratio(self) -> Optional[float]:
        """
        Get bid/ask ratio dari orderbook
        TRUE interpretation: High ratio = BID dominant = BUY pressure
        """
        try:
            data = self.fetch("/fapi/v1/depth", {"symbol": self.symbol, "limit": 10})
            if not data or "bids" not in data or "asks" not in data:
                return None
            
            # Hitung volume 5 level teratas
            bid_vol = sum(float(quantity) for _, quantity in data["bids"][:5])
            ask_vol = sum(float(quantity) for _, quantity in data["asks"][:5])
            
            if ask_vol == 0:
                return 99.0
            if bid_vol == 0:
                return 0.01
            
            ratio = round(bid_vol / ask_vol, 2)
            return min(ratio, 99.0)  # Cap di 99 untuk menghindari nilai ekstrem
            
        except Exception as e:
            print(f"❌ Orderbook error: {e}")
            return None
    
    def get_trades_flow(self) -> Optional[Dict]:
        """Analyze last 20 trades - buy/sell flow"""
        try:
            data = self.fetch("/fapi/v1/trades", {"symbol": self.symbol, "limit": 20})
            if not data:
                return None
            
            # Hitung buyer vs seller (isBuyerMaker = True berarti seller)
            buys = sum(1 for trade in data if not trade.get("isBuyerMaker", True))
            sells = len(data) - buys
            
            buy_ratio = buys / sells if sells > 0 else 99.0
            
            return {
                "buys": buys,
                "sells": sells,
                "ratio": round(buy_ratio, 2)
            }
        except Exception as e:
            print(f"❌ Trades flow error: {e}")
            return None
    
    def get_funding_premium(self) -> Optional[Dict]:
        """
        Get funding rate dan premium index
        Premium = WHERE THE CROWD IS POSITIONED
        """
        try:
            data = self.fetch("/fapi/v1/premiumIndex", {"symbol": self.symbol})
            if not data:
                return None
            
            mark_price = float(data.get("markPrice", 0))
            index_price = float(data.get("indexPrice", 0))
            
            # Hindari division by zero
            if index_price == 0:
                premium_basis = 0
            else:
                premium_basis = ((mark_price - index_price) / index_price) * 100
            
            return {
                "mark": mark_price,
                "index": index_price,
                "premium": round(premium_basis, 4),
                "funding": float(data.get("lastFundingRate", 0)) * 100
            }
        except Exception as e:
            print(f"❌ Funding premium error: {e}")
            return None
    
    def get_klines(self, limit: int = 20) -> Optional[Dict]:
        """Get candlestick data for analysis"""
        try:
            data = self.fetch("/fapi/v1/klines", {
                "symbol": self.symbol,
                "interval": "1m",
                "limit": limit
            })
            
            if not data:
                return None
            
            return {
                "highs": [float(k[2]) for k in data if len(k) > 2],
                "lows": [float(k[3]) for k in data if len(k) > 3],
                "closes": [float(k[4]) for k in data if len(k) > 4],
                "volumes": [float(k[5]) for k in data if len(k) > 5]
            }
        except Exception as e:
            print(f"❌ Klines error: {e}")
            return None
    
    def get_depth(self) -> Optional[Dict]:
        """Get orderbook depth"""
        return self.fetch("/fapi/v1/depth", {"symbol": self.symbol, "limit": 20})


class TechnicalAnalyzer:
    """Technical analysis dengan threshold-based filtering"""
    
    @staticmethod
    def get_ema_trend(closes: List[float], threshold: float = 0.0005) -> Tuple[float, str]:
        """EMA dengan THRESHOLD untuk noise elimination"""
        try:
            if len(closes) < 10:
                return 0, "FLAT"
            
            ema_short = float(np.mean(closes[-5:]))
            ema_long = float(np.mean(closes[-10:]))
            
            if ema_long == 0:
                return 0, "FLAT"
                
            slope = (ema_short - ema_long) / ema_long
            
            if slope > threshold:
                return slope, "UP"
            elif slope < -threshold:
                return slope, "DOWN"
            return slope, "FLAT"
        except:
            return 0, "FLAT"
    
    @staticmethod
    def get_price_changes(closes: List[float]) -> Dict:
        """Calculate price changes untuk berbagai timeframe"""
        changes = {
            "1m": 0.0,
            "5m": 0.0,
            "15m": 0.0
        }
        
        try:
            if len(closes) >= 2 and closes[-2] != 0:
                changes["1m"] = ((closes[-1] - closes[-2]) / closes[-2]) * 100
            
            if len(closes) >= 5 and closes[-5] != 0:
                changes["5m"] = ((closes[-1] - closes[-5]) / closes[-5]) * 100
            
            if len(closes) >= 15 and closes[-15] != 0:
                changes["15m"] = ((closes[-1] - closes[-15]) / closes[-15]) * 100
        except:
            pass
            
        return changes
    
    @staticmethod
    def get_liquidation_zones(highs: List[float], lows: List[float], current_price: float) -> Dict:
        """Deteksi zona likuidasi"""
        try:
            if not highs or not lows or current_price == 0:
                return {
                    "near_long_liq": False,
                    "near_short_liq": False,
                    "recent_high": 0,
                    "recent_low": 0,
                    "long_liq_distance": 0,
                    "short_liq_distance": 0
                }
            
            recent_high = max(highs[-10:]) if len(highs) >= 10 else max(highs)
            recent_low = min(lows[-10:]) if len(lows) >= 10 else min(lows)
            
            long_liq_distance = ((current_price - recent_low) / recent_low) * 100 if recent_low != 0 else 0
            short_liq_distance = ((recent_high - current_price) / current_price) * 100 if current_price != 0 else 0
            
            return {
                "near_long_liq": current_price <= recent_low * 1.02,
                "near_short_liq": current_price >= recent_high * 0.98,
                "recent_high": recent_high,
                "recent_low": recent_low,
                "long_liq_distance": long_liq_distance,
                "short_liq_distance": short_liq_distance
            }
        except:
            return {
                "near_long_liq": False,
                "near_short_liq": False,
                "recent_high": 0,
                "recent_low": 0,
                "long_liq_distance": 0,
                "short_liq_distance": 0
            }


class MarketStructureAnalyzer:
    """Market structure and pattern recognition"""
    
    @staticmethod
    def get_orderbook_sentiment(ratio: float) -> Dict:
        """Interpretasi orderbook yang BENAR"""
        if ratio > 2.0:
            return {"bias": "STRONG_BID", "sentiment": "BULLISH", "score": 40}
        elif ratio > 1.2:
            return {"bias": "BID", "sentiment": "BULLISH_BIAS", "score": 20}
        elif ratio < 0.5:
            return {"bias": "STRONG_ASK", "sentiment": "BEARISH", "score": -40}
        elif ratio < 0.8:
            return {"bias": "ASK", "sentiment": "BEARISH_BIAS", "score": -20}
        else:
            return {"bias": "NEUTRAL", "sentiment": "NEUTRAL", "score": 0}
    
    @staticmethod
    def get_premium_sentiment(premium: float) -> Dict:
        """Interpretasi premium yang BENAR"""
        if premium > 0.1:
            return {"bias": "LONG_DOMINANT", "risk": "SHORT_SQUEEZE", "score": 30}
        elif premium > 0.03:
            return {"bias": "LONG_BIAS", "risk": "POTENTIAL_SQUEEZE", "score": 15}
        elif premium < -0.1:
            return {"bias": "SHORT_DOMINANT", "risk": "LONG_SQUEEZE", "score": -30}
        elif premium < -0.03:
            return {"bias": "SHORT_BIAS", "risk": "POTENTIAL_LIQUIDATION", "score": -15}
        else:
            return {"bias": "NEUTRAL", "risk": "NO_SQUEEZE", "score": 0}
    
    @staticmethod
    def detect_squeeze_setups(trades: Dict, premium: float, change_5m: float) -> Dict:
        """Deteksi squeeze buildup"""
        if not trades:
            return {"short_squeeze": False, "long_squeeze": False}
            
        buy_sell_ratio = trades.get("ratio", 1.0)
        buys = trades.get("buys", 0)
        sells = trades.get("sells", 0)
        
        return {
            "short_squeeze": (
                buy_sell_ratio > 3.0 and
                premium > 0.05 and
                change_5m > -0.5
            ),
            "long_squeeze": (
                sells > buys * 3 and
                premium < -0.05 and
                change_5m < 0.5
            )
        }
    
    @staticmethod
    def detect_liquidity_bait(ob_sentiment: str, trades: Dict, 
                             change_5m: float, raw_breakdown: bool, 
                             failed_high: bool) -> Dict:
        """Deteksi trap pattern"""
        if not trades:
            return {"bait_buy": False, "bait_sell": False}
            
        buy_sell_ratio = trades.get("ratio", 1.0)
        buys = trades.get("buys", 0)
        sells = trades.get("sells", 0)
        
        return {
            "bait_buy": (
                ob_sentiment == "BULLISH" and
                buy_sell_ratio > 2.0 and
                change_5m < 0 and
                not raw_breakdown
            ),
            "bait_sell": (
                ob_sentiment == "BEARISH" and
                sells > buys * 2 and
                change_5m > 0 and
                not failed_high
            )
        }
    
    @staticmethod
    def detect_reversal_patterns(change_24h: float, raw_breakdown: bool, 
                                near_long_liq: bool, near_short_liq: bool,
                                premium: float, ob_bias: str, premium_bias: str,
                                price_change_5m: float) -> Dict:
        """Deteksi reversal dan conflict patterns"""
        
        return {
            "overbought_reversal": (
                change_24h > 30 and
                raw_breakdown and
                near_long_liq and
                premium < -0.2
            ),
            "oversold_reversal": (
                change_24h < -20 and
                not raw_breakdown and
                near_short_liq and
                premium > 0.2
            ),
            "bid_liquidity_trap": (
                ob_bias == "STRONG_BID" and
                premium_bias in ["SHORT_DOMINANT", "SHORT_BIAS"] and
                price_change_5m < 0 and
                (raw_breakdown or near_long_liq)
            ),
            "ask_liquidity_trap": (
                ob_bias == "STRONG_ASK" and
                premium_bias in ["LONG_DOMINANT", "LONG_BIAS"] and
                price_change_5m > 0 and
                (not raw_breakdown or near_short_liq)
            ),
            "bid_vs_premium_conflict": (
                ob_bias in ["STRONG_BID", "BID"] and
                premium_bias in ["SHORT_DOMINANT", "SHORT_BIAS"]
            ),
            "ask_vs_premium_conflict": (
                ob_bias in ["STRONG_ASK", "ASK"] and
                premium_bias in ["LONG_DOMINANT", "LONG_BIAS"]
            ),
            "extreme_overbought_cascade": (
                change_24h > 50 and
                raw_breakdown and
                near_long_liq and
                premium < -0.5
            ),
            "extreme_oversold_cascade": (
                change_24h < -40 and
                not raw_breakdown and
                near_short_liq and
                premium > 0.5
            )
        }


class DecisionEngine:
    """Probability-based decision engine dengan priority hierarchy"""
    
    def __init__(self):
        self.opinion = "NEUTRAL"
        self.reason = ""
        self.confidence = "LOW"
        self.liquidation_alert = "⚪ NO SIGNAL"
        self.valid_breakdown = False
        self.fake_breakdown = False
    
    def evaluate(self, data: Dict) -> Dict:
        """Evaluate all conditions with proper priority"""
        
        # ============================================
        # 🚨 PRIORITY 0: EXTREME REVERSAL & CONFLICT
        # ============================================
        
        if data['patterns'].get('extreme_overbought_cascade', False):
            self._set_decision("SHORT", "EXTREME_OVERBOUGHT_CASCADE_REVERSAL", "VERY_HIGH",
                              "💀 EXTREME OVERBOUGHT - MAJOR TOP", valid_breakdown=True)
        
        elif data['patterns'].get('extreme_oversold_cascade', False):
            self._set_decision("LONG", "EXTREME_OVERSOLD_CASCADE_REVERSAL", "VERY_HIGH",
                              "💀 EXTREME OVERSOLD - MAJOR BOTTOM", fake_breakdown=True)
        
        elif data['patterns'].get('overbought_reversal', False):
            self._set_decision("SHORT", "OVERBOUGHT_TOP_REVERSAL", "VERY_HIGH",
                              "🚨 TOP FORMATION - REVERSAL", valid_breakdown=True)
        
        elif data['patterns'].get('oversold_reversal', False):
            self._set_decision("LONG", "OVERSOLD_BOTTOM_REVERSAL", "VERY_HIGH",
                              "🚨 BOTTOM FORMATION - REVERSAL", fake_breakdown=True)
        
        elif data['patterns'].get('bid_liquidity_trap', False):
            self._set_decision("SHORT", "BID_LIQUIDITY_TRAP_DISTRIBUTION", "HIGH",
                              "🎯 BID DOMINANT TAPI PREMIUM NEGATIF - DISTRIBUTION", 
                              valid_breakdown=True)
        
        elif data['patterns'].get('ask_liquidity_trap', False):
            self._set_decision("LONG", "ASK_LIQUIDITY_TRAP_ABSORPTION", "HIGH",
                              "🎯 ASK DOMINANT TAPI PREMIUM POSITIF - ABSORPTION",
                              fake_breakdown=True)
        
        elif data['patterns'].get('bid_vs_premium_conflict', False):
            self._set_decision("SHORT", "CONFLICT_BID_VS_PREMIUM_PREMIUM_WINS", "MEDIUM",
                              "⚠️ BID DOMINANT TAPI SHORT PREMIUM - FOLLOW PREMIUM",
                              valid_breakdown=data['structure'].get('raw_breakdown', False))
        
        elif data['patterns'].get('ask_vs_premium_conflict', False):
            self._set_decision("LONG", "CONFLICT_ASK_VS_PREMIUM_PREMIUM_WINS", "MEDIUM",
                              "⚠️ ASK DOMINANT TAPI LONG PREMIUM - FOLLOW PREMIUM",
                              fake_breakdown=not data['structure'].get('raw_breakdown', False))
        
        # ============================================
        # 🚨 PRIORITY 1: SQUEEZE SETUPS
        # ============================================
        elif data['setups'].get('short_squeeze', False):
            self._set_decision("LONG", "SHORT_SQUEEZE_BUILDUP", "VERY_HIGH",
                              "🔥 SHORT SQUEEZE IMMINENT", fake_breakdown=True)
        
        elif data['setups'].get('long_squeeze', False):
            self._set_decision("SHORT", "LONG_SQUEEZE_BUILDUP", "VERY_HIGH",
                              "🔥 LONG SQUEEZE IMMINENT", valid_breakdown=True)
        
        # ============================================
        # 🚨 PRIORITY 2: LIQUIDITY BAIT
        # ============================================
        elif data['bait'].get('bait_buy', False):
            self._set_decision("LONG", "LIQUIDITY_BAIT_ABSORPTION", "HIGH",
                              "🎯 BUY LIQUIDITY BAIT DETECTED", fake_breakdown=True)
        
        elif data['bait'].get('bait_sell', False):
            self._set_decision("SHORT", "LIQUIDITY_BAIT_DISTRIBUTION", "HIGH",
                              "🎯 SELL LIQUIDITY BAIT DETECTED", valid_breakdown=True)
        
        # ============================================
        # 🚨 PRIORITY 3: ORDERBOOK DOMINANCE
        # ============================================
        elif data['ob'].get('bias') == "STRONG_BID":
            self._set_decision("LONG", "STRONG_BUY_PRESSURE", "HIGH",
                              "📊 EXTREME BID DOMINANCE")
        
        elif data['ob'].get('bias') == "STRONG_ASK":
            self._set_decision("SHORT", "STRONG_SELL_PRESSURE", "HIGH",
                              "📊 EXTREME ASK DOMINANCE")
        
        # ============================================
        # 🚨 PRIORITY 4: PREMIUM + ORDERBOOK CONFIRMATION
        # ============================================
        elif (data['premium'].get('bias') == "LONG_DOMINANT" and 
              data['ob'].get('sentiment') == "BULLISH"):
            self._set_decision("LONG", "PREMIUM_OB_CONFIRMATION", "HIGH",
                              "💰 LONG DOMINANT CONFIRMED")
        
        elif (data['premium'].get('bias') == "SHORT_DOMINANT" and 
              data['ob'].get('sentiment') == "BEARISH"):
            self._set_decision("SHORT", "PREMIUM_OB_CONFIRMATION", "HIGH",
                              "💰 SHORT DOMINANT CONFIRMED")
        
        # ============================================
        # 🚨 PRIORITY 5: EMA TREND
        # ============================================
        elif data['ema_trend'] == "UP" and data['ob'].get('sentiment') != "BEARISH":
            self._set_decision("LONG", "EMA_UPTREND_CONFIRMATION", "MEDIUM",
                              "📈 UPTREND STRUCTURE")
        
        elif data['ema_trend'] == "DOWN" and data['ob'].get('sentiment') != "BULLISH":
            self._set_decision("SHORT", "EMA_DOWNTREND_CONFIRMATION", "MEDIUM",
                              "📉 DOWNTREND STRUCTURE")
        
        # ============================================
        # 🚨 PRIORITY 6: LIQUIDATION ZONES
        # ============================================
        elif data['liq_zones'].get('near_long_liq', False) and data['ob'].get('sentiment') == "BEARISH":
            self._set_decision("SHORT", "LONG_LIQ_CASCADE", "MEDIUM",
                              "⚠️ LONG LIQUIDATION ZONE", valid_breakdown=True)
        
        elif data['liq_zones'].get('near_short_liq', False) and data['ob'].get('sentiment') == "BULLISH":
            self._set_decision("LONG", "SHORT_LIQ_CASCADE", "MEDIUM",
                              "⚠️ SHORT LIQUIDATION ZONE", fake_breakdown=True)
        
        # ============================================
        # 🚨 PRIORITY 7: ORDERBOOK BIAS
        # ============================================
        elif data['ob'].get('sentiment') == "BULLISH_BIAS":
            self._set_decision("LONG", "OB_BUY_PRESSURE", "LOW",
                              "📊 BID DOMINANT")
        
        elif data['ob'].get('sentiment') == "BEARISH_BIAS":
            self._set_decision("SHORT", "OB_SELL_PRESSURE", "LOW",
                              "📊 ASK DOMINANT")
        
        # Default
        else:
            self._set_decision("NEUTRAL", "NO_CLEAR_SIGNAL", "LOW", "⚪ NO SIGNAL")
        
        # Apply anti-countertrend filters
        self._apply_filters(data)
        
        return self._get_result()
    
    def _set_decision(self, opinion: str, reason: str, confidence: str,
                     alert: str, valid_breakdown: bool = False, 
                     fake_breakdown: bool = False):
        """Set decision parameters"""
        self.opinion = opinion
        self.reason = reason
        self.confidence = confidence
        self.liquidation_alert = alert
        self.valid_breakdown = valid_breakdown
        self.fake_breakdown = fake_breakdown
    
    def _apply_filters(self, data: Dict):
        """Anti-countertrend filters"""
        try:
            # Jangan SHORT di area oversold dengan bid dominant
            if (self.opinion == "SHORT" and 
                data.get('change_24h', 0) < -10 and 
                data['ob'].get('sentiment') == "BULLISH" and
                not data['structure'].get('raw_breakdown', False)):
                self.opinion = "LONG"
                self.reason = f"ANTI_OVERSOLD_SHORT_{self.reason}"
                self.fake_breakdown = True
            
            # Jangan LONG di area overbought dengan ask dominant
            if (self.opinion == "LONG" and 
                data.get('change_24h', 0) > 10 and 
                data['ob'].get('sentiment') == "BEARISH" and
                data['structure'].get('raw_breakdown', False)):
                self.opinion = "SHORT"
                self.reason = f"ANTI_OVERBOUGHT_LONG_{self.reason}"
                self.valid_breakdown = True
        except:
            pass
    
    def _get_result(self) -> Dict:
        """Return decision result"""
        return {
            "opinion": self.opinion,
            "reason": self.reason,
            "confidence": self.confidence,
            "liquidation_alert": self.liquidation_alert,
            "valid_breakdown": self.valid_breakdown,
            "fake_breakdown": self.fake_breakdown
        }


def analyze_symbol(symbol: str) -> Optional[Dict]:
    """
    Main analysis function - returns snapshot dict
    Production ready dengan error handling
    """
    try:
        fetcher = BinanceFetcher(symbol)
        
        # Fetch semua data dengan timeout total
        price = fetcher.get_price()
        change_24h = fetcher.get_24h_change()
        ob_ratio = fetcher.get_orderbook_ratio()
        trades = fetcher.get_trades_flow()
        premium_data = fetcher.get_funding_premium()
        klines = fetcher.get_klines(20)
        depth = fetcher.get_depth()
        
        # Validasi data minimal
        if price is None:
            print(f"❌ Failed to fetch price for {symbol}")
            return None
        
        # Gunakan default value untuk data yang mungkin None
        change_24h = change_24h or 0.0
        ob_ratio = ob_ratio or 1.0
        trades = trades or {"buys": 0, "sells": 0, "ratio": 1.0}
        premium_data = premium_data or {"premium": 0.0, "funding": 0.0, "mark": price, "index": price}
        klines = klines or {"highs": [price*1.01, price], "lows": [price*0.99, price], "closes": [price, price]}
        depth = depth or {}
        
        # Extract data dari klines
        highs = klines.get("highs", [price*1.01])
        lows = klines.get("lows", [price*0.99])
        closes = klines.get("closes", [price, price])
        current_close = closes[-1] if closes else price
        
        # Hitung prev high/low
        prev_high = max(highs[-10:]) if len(highs) >= 10 else max(highs)
        prev_low = min(lows[-10:]) if len(lows) >= 10 else min(lows)
        
        # Technical analysis
        tech_analyzer = TechnicalAnalyzer()
        price_changes = tech_analyzer.get_price_changes(closes)
        ema_slope, ema_trend = tech_analyzer.get_ema_trend(closes)
        liq_zones = tech_analyzer.get_liquidation_zones(highs, lows, current_close)
        
        # Market structure analysis
        struct_analyzer = MarketStructureAnalyzer()
        ob_sentiment = struct_analyzer.get_orderbook_sentiment(ob_ratio)
        premium_sentiment = struct_analyzer.get_premium_sentiment(premium_data["premium"])
        
        # Pattern detection
        squeeze_setups = struct_analyzer.detect_squeeze_setups(
            trades, premium_data["premium"], price_changes.get("5m", 0)
        )
        
        bait_patterns = struct_analyzer.detect_liquidity_bait(
            ob_sentiment["sentiment"], trades, price_changes.get("5m", 0),
            current_close < prev_low, current_close < prev_high
        )
        
        reversal_patterns = struct_analyzer.detect_reversal_patterns(
            change_24h, current_close < prev_low,
            liq_zones["near_long_liq"], liq_zones["near_short_liq"],
            premium_data["premium"], ob_sentiment["bias"], premium_sentiment["bias"],
            price_changes.get("5m", 0)
        )
        
        # Compile decision data
        decision_data = {
            "change_24h": change_24h,
            "ob": ob_sentiment,
            "premium": premium_sentiment,
            "setups": squeeze_setups,
            "bait": bait_patterns,
            "patterns": reversal_patterns,
            "ema_trend": ema_trend,
            "liq_zones": liq_zones,
            "structure": {
                "raw_breakdown": current_close < prev_low,
                "failed_high": current_close < prev_high,
                "price_change_5m": price_changes.get("5m", 0)
            }
        }
        
        # Make decision
        engine = DecisionEngine()
        decision = engine.evaluate(decision_data)
        
        # Build snapshot
        snapshot = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "symbol": symbol,
            "price": round(price, 2) if price else 0,
            "ob_ratio": ob_ratio,
            "ob_bias": ob_sentiment["bias"],
            "ob_sentiment": ob_sentiment["sentiment"],
            "buy_sell_ratio": trades["ratio"],
            "buys": trades["buys"],
            "sells": trades["sells"],
            "premium": premium_data["premium"],
            "premium_bias": premium_sentiment["bias"],
            "premium_risk": premium_sentiment["risk"],
            "funding_rate": premium_data["funding"],
            "ema_slope": round(ema_slope, 6),
            "ema_trend": ema_trend,
            "change_24h": round(change_24h, 2),
            "change_1m": round(price_changes.get("1m", 0), 2),
            "change_5m": round(price_changes.get("5m", 0), 2),
            "change_15m": round(price_changes.get("15m", 0), 2),
            "failed_high": current_close < prev_high,
            "raw_breakdown": current_close < prev_low,
            "near_long_liq": liq_zones["near_long_liq"],
            "near_short_liq": liq_zones["near_short_liq"],
            "long_liq_distance": round(liq_zones["long_liq_distance"], 2),
            "short_liq_distance": round(liq_zones["short_liq_distance"], 2),
            "is_short_squeeze": squeeze_setups["short_squeeze"],
            "is_long_squeeze": squeeze_setups["long_squeeze"],
            "liquidity_bait_buy": bait_patterns["bait_buy"],
            "liquidity_bait_sell": bait_patterns["bait_sell"],
            "overbought_reversal": reversal_patterns["overbought_reversal"],
            "oversold_reversal": reversal_patterns["oversold_reversal"],
            "bid_liquidity_trap": reversal_patterns["bid_liquidity_trap"],
            "ask_liquidity_trap": reversal_patterns["ask_liquidity_trap"],
            "bid_vs_premium_conflict": reversal_patterns["bid_vs_premium_conflict"],
            "ask_vs_premium_conflict": reversal_patterns["ask_vs_premium_conflict"],
            "extreme_overbought_cascade": reversal_patterns["extreme_overbought_cascade"],
            "extreme_oversold_cascade": reversal_patterns["extreme_oversold_cascade"],
            "opinion": decision["opinion"],
            "reason": decision["reason"],
            "confidence": decision["confidence"],
            "liquidation_alert": decision["liquidation_alert"],
            "valid_breakdown": decision["valid_breakdown"],
            "fake_breakdown": decision["fake_breakdown"]
        }
        
        return snapshot
        
    except Exception as e:
        print(f"❌ analyze_symbol error for {symbol}: {e}")
        return None


# Popular symbols list - Wajib ada untuk endpoint /analyze
POPULAR_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "BTRUSDT", "SOLUSDT", "DOGEUSDT"]


# Untuk testing langsung
if __name__ == "__main__":
    print("🧪 Testing liquidation_hunter.py...")
    test_symbol = "BTCUSDT"
    result = analyze_symbol(test_symbol)
    
    if result:
        print(f"✅ Success for {test_symbol}")
        print(f"Price: ${result['price']}")
        print(f"Opinion: {result['opinion']} ({result['confidence']})")
        print(f"Reason: {result['reason']}")
    else:
        print(f"❌ Failed for {test_symbol}")
        
    print(f"\n📊 Popular symbols: {POPULAR_SYMBOLS}")