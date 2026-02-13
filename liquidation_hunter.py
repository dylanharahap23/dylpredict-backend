#!/usr/bin/env python3
"""
🔥 BINANCE LIQUIDATION HUNTER V14 - CONFLICT RESOLUTION ENGINE
Optimized for API integration
"""

import requests
from datetime import datetime
import urllib3
import numpy as np
from typing import Optional, Dict, Tuple, Any, List
import os

urllib3.disable_warnings()

class BinanceFetcher:
    """Centralized data fetching with error handling"""
    
    def __init__(self, symbol):
        self.symbol = symbol.upper()
        self.BASE_URL = "https://fapi.binance.com"
        self.TIMEOUT = 3
        
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json"
        })
        self.session.verify = False
    
    def fetch(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Any]:
        try:
            r = self.session.get(f"{self.BASE_URL}{endpoint}", params=params, timeout=self.TIMEOUT)
            return r.json() if r.status_code == 200 else None
        except Exception:
            return None
    
    def get_price(self) -> Optional[float]:
        d = self.fetch("/fapi/v1/ticker/price", {"symbol": self.symbol})
        return float(d["price"]) if d else None
    
    def get_24h_change(self) -> Optional[float]:
        d = self.fetch("/fapi/v1/ticker/24hr", {"symbol": self.symbol})
        return float(d["priceChangePercent"]) if d else None
    
    def get_orderbook_ratio(self) -> Optional[float]:
        d = self.fetch("/fapi/v1/depth", {"symbol": self.symbol, "limit": 10})
        if not d:
            return None
        
        bid_vol = sum(float(q) for _, q in d["bids"][:5])
        ask_vol = sum(float(q) for _, q in d["asks"][:5])
        
        if ask_vol == 0:
            return 99.0
        if bid_vol == 0:
            return 0.01
        
        ratio = round(bid_vol / ask_vol, 2)
        return ratio
    
    def get_trades_flow(self) -> Optional[Dict]:
        d = self.fetch("/fapi/v1/trades", {"symbol": self.symbol, "limit": 20})
        if not d:
            return None
        
        buys = sum(1 for t in d if not t["isBuyerMaker"])
        sells = len(d) - buys
        buy_ratio = buys / sells if sells > 0 else 99.0
        
        return {
            "buys": buys,
            "sells": sells,
            "ratio": round(buy_ratio, 2)
        }
    
    def get_funding_premium(self) -> Optional[Dict]:
        d = self.fetch("/fapi/v1/premiumIndex", {"symbol": self.symbol})
        if not d:
            return None
        
        mark_price = float(d["markPrice"])
        index_price = float(d["indexPrice"])
        premium_basis = ((mark_price - index_price) / index_price) * 100
        
        return {
            "mark": mark_price,
            "index": index_price,
            "premium": round(premium_basis, 4),
            "funding": float(d["lastFundingRate"]) * 100
        }
    
    def get_klines(self, limit: int = 20) -> Optional[Dict]:
        d = self.fetch("/fapi/v1/klines", {
            "symbol": self.symbol,
            "interval": "1m",
            "limit": limit
        })
        
        if not d:
            return None
        
        return {
            "highs": [float(k[2]) for k in d],
            "lows": [float(k[3]) for k in d],
            "closes": [float(k[4]) for k in d],
            "volumes": [float(k[5]) for k in d]
        }
    
    def get_depth(self) -> Optional[Dict]:
        return self.fetch("/fapi/v1/depth", {"symbol": self.symbol, "limit": 20})


class TechnicalAnalyzer:
    """Technical analysis with threshold-based filtering"""
    
    @staticmethod
    def get_ema_trend(closes: list, threshold: float = 0.0005) -> Tuple[float, str]:
        if len(closes) < 10:
            return 0, "FLAT"
        
        ema_short = np.mean(closes[-5:])
        ema_long = np.mean(closes[-10:])
        slope = (ema_short - ema_long) / ema_long
        
        if slope > threshold:
            return slope, "UP"
        elif slope < -threshold:
            return slope, "DOWN"
        return slope, "FLAT"
    
    @staticmethod
    def get_price_changes(closes: list) -> Dict:
        changes = {}
        
        if len(closes) >= 5:
            changes["5m"] = ((closes[-1] - closes[-5]) / closes[-5]) * 100
        else:
            changes["5m"] = 0
        
        if len(closes) >= 15:
            changes["15m"] = ((closes[-1] - closes[-15]) / closes[-15]) * 100
        else:
            changes["15m"] = 0
        
        if len(closes) >= 2:
            changes["1m"] = ((closes[-1] - closes[-2]) / closes[-2]) * 100
        else:
            changes["1m"] = 0
        
        return changes
    
    @staticmethod
    def get_liquidation_zones(highs: list, lows: list, current_price: float) -> Dict:
        recent_high = max(highs[-10:])
        recent_low = min(lows[-10:])
        
        return {
            "near_long_liq": current_price <= recent_low * 1.02,
            "near_short_liq": current_price >= recent_high * 0.98,
            "recent_high": recent_high,
            "recent_low": recent_low,
            "long_liq_distance": ((current_price - recent_low) / recent_low) * 100,
            "short_liq_distance": ((recent_high - current_price) / current_price) * 100
        }


class MarketStructureAnalyzer:
    """Market structure and pattern recognition"""
    
    @staticmethod
    def get_orderbook_sentiment(ratio: float) -> Dict:
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
        buy_sell_ratio = trades["ratio"]
        
        return {
            "short_squeeze": (
                buy_sell_ratio > 3.0 and
                premium > 0.05 and
                change_5m > -0.5
            ),
            "long_squeeze": (
                trades["sells"] > trades["buys"] * 3 and
                premium < -0.05 and
                change_5m < 0.5
            )
        }
    
    @staticmethod
    def detect_liquidity_bait(ob_sentiment: str, trades: Dict, 
                             change_5m: float, raw_breakdown: bool, 
                             failed_high: bool) -> Dict:
        buy_sell_ratio = trades["ratio"]
        
        return {
            "bait_buy": (
                ob_sentiment == "BULLISH" and
                buy_sell_ratio > 2.0 and
                change_5m < 0 and
                not raw_breakdown
            ),
            "bait_sell": (
                ob_sentiment == "BEARISH" and
                trades["sells"] > trades["buys"] * 2 and
                change_5m > 0 and
                not failed_high
            )
        }
    
    @staticmethod
    def detect_reversal_patterns(change_24h: float, raw_breakdown: bool, 
                                near_long_liq: bool, near_short_liq: bool,
                                premium: float, ob_bias: str, premium_bias: str,
                                price_change_5m: float) -> Dict:
        
        overbought_reversal = (
            change_24h > 30 and
            raw_breakdown and
            near_long_liq and
            premium < -0.2
        )
        
        oversold_reversal = (
            change_24h < -20 and
            not raw_breakdown and
            near_short_liq and
            premium > 0.2
        )
        
        bid_liquidity_trap = (
            ob_bias == "STRONG_BID" and
            premium_bias in ["SHORT_DOMINANT", "SHORT_BIAS"] and
            price_change_5m < 0 and
            (raw_breakdown or near_long_liq)
        )
        
        ask_liquidity_trap = (
            ob_bias == "STRONG_ASK" and
            premium_bias in ["LONG_DOMINANT", "LONG_BIAS"] and
            price_change_5m > 0 and
            (not raw_breakdown or near_short_liq)
        )
        
        bid_vs_premium_conflict = (
            ob_bias in ["STRONG_BID", "BID"] and
            premium_bias in ["SHORT_DOMINANT", "SHORT_BIAS"]
        )
        
        ask_vs_premium_conflict = (
            ob_bias in ["STRONG_ASK", "ASK"] and
            premium_bias in ["LONG_DOMINANT", "LONG_BIAS"]
        )
        
        extreme_overbought_cascade = (
            change_24h > 50 and
            raw_breakdown and
            near_long_liq and
            premium < -0.5
        )
        
        extreme_oversold_cascade = (
            change_24h < -40 and
            not raw_breakdown and
            near_short_liq and
            premium > 0.5
        )
        
        return {
            "overbought_reversal": overbought_reversal,
            "oversold_reversal": oversold_reversal,
            "bid_liquidity_trap": bid_liquidity_trap,
            "ask_liquidity_trap": ask_liquidity_trap,
            "bid_vs_premium_conflict": bid_vs_premium_conflict,
            "ask_vs_premium_conflict": ask_vs_premium_conflict,
            "extreme_overbought_cascade": extreme_overbought_cascade,
            "extreme_oversold_cascade": extreme_oversold_cascade
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
        
        # PRIORITY 0: EXTREME REVERSAL & CONFLICT
        if data['patterns']['extreme_overbought_cascade']:
            self._set_decision("SHORT", "EXTREME_OVERBOUGHT_CASCADE_REVERSAL", "VERY_HIGH",
                              "💀 EXTREME OVERBOUGHT - MAJOR TOP", valid_breakdown=True)
        
        elif data['patterns']['extreme_oversold_cascade']:
            self._set_decision("LONG", "EXTREME_OVERSOLD_CASCADE_REVERSAL", "VERY_HIGH",
                              "💀 EXTREME OVERSOLD - MAJOR BOTTOM", fake_breakdown=True)
        
        elif data['patterns']['overbought_reversal']:
            self._set_decision("SHORT", "OVERBOUGHT_TOP_REVERSAL", "VERY_HIGH",
                              "🚨 TOP FORMATION - REVERSAL", valid_breakdown=True)
        
        elif data['patterns']['oversold_reversal']:
            self._set_decision("LONG", "OVERSOLD_BOTTOM_REVERSAL", "VERY_HIGH",
                              "🚨 BOTTOM FORMATION - REVERSAL", fake_breakdown=True)
        
        elif data['patterns']['bid_liquidity_trap']:
            self._set_decision("SHORT", "BID_LIQUIDITY_TRAP_DISTRIBUTION", "HIGH",
                              "🎯 BID DOMINANT TAPI PREMIUM NEGATIF - DISTRIBUTION", 
                              valid_breakdown=True)
        
        elif data['patterns']['ask_liquidity_trap']:
            self._set_decision("LONG", "ASK_LIQUIDITY_TRAP_ABSORPTION", "HIGH",
                              "🎯 ASK DOMINANT TAPI PREMIUM POSITIF - ABSORPTION",
                              fake_breakdown=True)
        
        elif data['patterns']['bid_vs_premium_conflict']:
            self._set_decision("SHORT", "CONFLICT_BID_VS_PREMIUM_PREMIUM_WINS", "MEDIUM",
                              "⚠️ BID DOMINANT TAPI SHORT PREMIUM - FOLLOW PREMIUM",
                              valid_breakdown=True if data['structure']['raw_breakdown'] else False)
        
        elif data['patterns']['ask_vs_premium_conflict']:
            self._set_decision("LONG", "CONFLICT_ASK_VS_PREMIUM_PREMIUM_WINS", "MEDIUM",
                              "⚠️ ASK DOMINANT TAPI LONG PREMIUM - FOLLOW PREMIUM",
                              fake_breakdown=True if not data['structure']['raw_breakdown'] else False)
        
        # PRIORITY 1: SQUEEZE SETUPS
        elif data['setups']['short_squeeze']:
            self._set_decision("LONG", "SHORT_SQUEEZE_BUILDUP", "VERY_HIGH",
                              "🔥 SHORT SQUEEZE IMMINENT", fake_breakdown=True)
        
        elif data['setups']['long_squeeze']:
            self._set_decision("SHORT", "LONG_SQUEEZE_BUILDUP", "VERY_HIGH",
                              "🔥 LONG SQUEEZE IMMINENT", valid_breakdown=True)
        
        # PRIORITY 2: LIQUIDITY BAIT
        elif data['bait']['bait_buy']:
            self._set_decision("LONG", "LIQUIDITY_BAIT_ABSORPTION", "HIGH",
                              "🎯 BUY LIQUIDITY BAIT DETECTED", fake_breakdown=True)
        
        elif data['bait']['bait_sell']:
            self._set_decision("SHORT", "LIQUIDITY_BAIT_DISTRIBUTION", "HIGH",
                              "🎯 SELL LIQUIDITY BAIT DETECTED", valid_breakdown=True)
        
        # PRIORITY 3: ORDERBOOK DOMINANCE
        elif data['ob']['bias'] == "STRONG_BID":
            self._set_decision("LONG", "STRONG_BUY_PRESSURE", "HIGH",
                              "📊 EXTREME BID DOMINANCE")
        
        elif data['ob']['bias'] == "STRONG_ASK":
            self._set_decision("SHORT", "STRONG_SELL_PRESSURE", "HIGH",
                              "📊 EXTREME ASK DOMINANCE")
        
        # PRIORITY 4: PREMIUM + ORDERBOOK CONFIRMATION
        elif (data['premium']['bias'] == "LONG_DOMINANT" and 
              data['ob']['sentiment'] == "BULLISH"):
            self._set_decision("LONG", "PREMIUM_OB_CONFIRMATION", "HIGH",
                              "💰 LONG DOMINANT CONFIRMED")
        
        elif (data['premium']['bias'] == "SHORT_DOMINANT" and 
              data['ob']['sentiment'] == "BEARISH"):
            self._set_decision("SHORT", "PREMIUM_OB_CONFIRMATION", "HIGH",
                              "💰 SHORT DOMINANT CONFIRMED")
        
        # PRIORITY 5: EMA TREND
        elif data['ema_trend'] == "UP" and data['ob']['sentiment'] != "BEARISH":
            self._set_decision("LONG", "EMA_UPTREND_CONFIRMATION", "MEDIUM",
                              "📈 UPTREND STRUCTURE")
        
        elif data['ema_trend'] == "DOWN" and data['ob']['sentiment'] != "BULLISH":
            self._set_decision("SHORT", "EMA_DOWNTREND_CONFIRMATION", "MEDIUM",
                              "📉 DOWNTREND STRUCTURE")
        
        # PRIORITY 6: LIQUIDATION ZONES
        elif data['liq_zones']['near_long_liq'] and data['ob']['sentiment'] == "BEARISH":
            self._set_decision("SHORT", "LONG_LIQ_CASCADE", "MEDIUM",
                              "⚠️ LONG LIQUIDATION ZONE", valid_breakdown=True)
        
        elif data['liq_zones']['near_short_liq'] and data['ob']['sentiment'] == "BULLISH":
            self._set_decision("LONG", "SHORT_LIQ_CASCADE", "MEDIUM",
                              "⚠️ SHORT LIQUIDATION ZONE", fake_breakdown=True)
        
        # PRIORITY 7: ORDERBOOK BIAS
        elif data['ob']['sentiment'] == "BULLISH_BIAS":
            self._set_decision("LONG", "OB_BUY_PRESSURE", "LOW",
                              "📊 BID DOMINANT")
        
        elif data['ob']['sentiment'] == "BEARISH_BIAS":
            self._set_decision("SHORT", "OB_SELL_PRESSURE", "LOW",
                              "📊 ASK DOMINANT")
        
        # Apply anti-countertrend filters
        self._apply_filters(data)
        
        return self._get_result()
    
    def _set_decision(self, opinion: str, reason: str, confidence: str,
                     alert: str, valid_breakdown: bool = False, 
                     fake_breakdown: bool = False):
        self.opinion = opinion
        self.reason = reason
        self.confidence = confidence
        self.liquidation_alert = alert
        self.valid_breakdown = valid_breakdown
        self.fake_breakdown = fake_breakdown
    
    def _apply_filters(self, data: Dict):
        if (self.opinion == "SHORT" and 
            data['change_24h'] < -10 and 
            data['ob']['sentiment'] == "BULLISH" and
            not data['structure']['raw_breakdown']):
            self.opinion = "LONG"
            self.reason = f"ANTI_OVERSOLD_SHORT_{self.reason}"
            self.fake_breakdown = True
        
        if (self.opinion == "LONG" and 
            data['change_24h'] > 10 and 
            data['ob']['sentiment'] == "BEARISH" and
            data['structure']['raw_breakdown']):
            self.opinion = "SHORT"
            self.reason = f"ANTI_OVERBOUGHT_LONG_{self.reason}"
            self.valid_breakdown = True
    
    def _get_result(self) -> Dict:
        return {
            "opinion": self.opinion,
            "reason": self.reason,
            "confidence": self.confidence,
            "liquidation_alert": self.liquidation_alert,
            "valid_breakdown": self.valid_breakdown,
            "fake_breakdown": self.fake_breakdown
        }


def analyze_symbol(symbol: str) -> Optional[Dict]:
    """Main analysis function - returns snapshot dict"""
    
    fetcher = BinanceFetcher(symbol)
    
    price = fetcher.get_price()
    change_24h = fetcher.get_24h_change()
    ob_ratio = fetcher.get_orderbook_ratio()
    trades = fetcher.get_trades_flow()
    premium_data = fetcher.get_funding_premium()
    klines = fetcher.get_klines(20)
    depth = fetcher.get_depth()
    
    if None in (price, change_24h, ob_ratio, trades, premium_data, klines, depth):
        return None
    
    highs = klines["highs"]
    lows = klines["lows"]
    closes = klines["closes"]
    current_close = closes[-1]
    
    prev_high = max(highs[-10:-1]) if len(highs) > 10 else max(highs[:-1])
    prev_low = min(lows[-10:-1]) if len(lows) > 10 else min(lows[:-1])
    
    tech_analyzer = TechnicalAnalyzer()
    price_changes = tech_analyzer.get_price_changes(closes)
    ema_slope, ema_trend = tech_analyzer.get_ema_trend(closes)
    liq_zones = tech_analyzer.get_liquidation_zones(highs, lows, current_close)
    
    struct_analyzer = MarketStructureAnalyzer()
    ob_sentiment = struct_analyzer.get_orderbook_sentiment(ob_ratio)
    premium_sentiment = struct_analyzer.get_premium_sentiment(premium_data["premium"])
    
    squeeze_setups = struct_analyzer.detect_squeeze_setups(
        trades, premium_data["premium"], price_changes["5m"]
    )
    
    bait_patterns = struct_analyzer.detect_liquidity_bait(
        ob_sentiment["sentiment"], trades, price_changes["5m"],
        current_close < prev_low, current_close < prev_high
    )
    
    reversal_patterns = struct_analyzer.detect_reversal_patterns(
        change_24h, current_close < prev_low,
        liq_zones["near_long_liq"], liq_zones["near_short_liq"],
        premium_data["premium"], ob_sentiment["bias"], premium_sentiment["bias"],
        price_changes["5m"]
    )
    
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
            "price_change_5m": price_changes["5m"]
        }
    }
    
    engine = DecisionEngine()
    decision = engine.evaluate(decision_data)
    
    snapshot = {
        "time": datetime.now().strftime("%H:%M:%S"),
        "symbol": symbol,
        "price": price,
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
        "ema_slope": ema_slope,
        "ema_trend": ema_trend,
        "change_24h": round(change_24h, 2),
        "change_1m": round(price_changes["1m"], 2),
        "change_5m": round(price_changes["5m"], 2),
        "change_15m": round(price_changes["15m"], 2),
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


# Popular symbols list
POPULAR_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "BTRUSDT", "SOLUSDT", "DOGEUSDT"]