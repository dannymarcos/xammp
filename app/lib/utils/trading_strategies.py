import pandas as pd
from typing import Dict
import logging
logger = logging.getLogger(__name__)
from app.viewmodels.services.SimpleQTable import SimpleQTable
# ----------------------------
# Helper functions for manual indicator calculation
# ----------------------------


def calculate_rsi_series(series: pd.Series, period: int) -> pd.Series:
    """Helper to calculate Relative Strength Index on a single series."""
    if len(series) < period + 1:
        return pd.Series([pd.NA] * len(series), index=series.index)

    delta = series.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    # Use .fillna(0) for the initial periods before rolling mean is valid
    avg_gain = gain.rolling(period, min_periods=1).mean().fillna(0)
    avg_loss = loss.rolling(period, min_periods=1).mean().fillna(0)

    # Calculate RS, handle division by zero (infinity)
    rs = avg_gain / avg_loss
    # If avg_loss is 0, RS is infinite, RSI is 100
    rs = rs.replace([float("inf"), -float("inf")], 100).fillna(
        0
    )  # RSI is 100 if avg_loss is 0, 0 if both 0

    # Calculate RSI
    rsi = 100 - (100 / (1 + rs))
    return rsi


def is_bullish_engulfing_pattern(candle1: pd.Series, candle2: pd.Series) -> bool:
    """Checks if candle2 forms a bullish engulfing pattern with candle1."""
    # Candle 1 must be bearish (close < open)
    # Candle 2 must be bullish (close > open)
    # Candle 2's body must engulf Candle 1's body (open2 < close1, close2 > open1)
    # Optional: Check body sizes (abs(close2-open2) > abs(close1-open1)) - Skipping strict size check for simplicity

    is_c1_bearish = candle1["close"] < candle1["open"]
    is_c2_bullish = candle2["close"] > candle2["open"]
    engulfs = candle2["open"] < candle1["close"] and candle2["close"] > candle1["open"]

    # Also ensure neither candle is a doji (very small body)
    # doji_threshold = abs(candle1['open'] - candle1['close']) * 0.1 # Example threshold
    # not_doji = abs(candle1['open'] - candle1['close']) > doji_threshold and abs(candle2['open'] - candle2['close']) > doji_threshold

    # Basic check: C1 bearish, C2 bullish, C2 body engulfs C1 body
    return is_c1_bearish and is_c2_bullish and engulfs


def is_bearish_engulfing_pattern(candle1: pd.Series, candle2: pd.Series) -> bool:
    """Checks if candle2 forms a bearish engulfing pattern with candle1."""
    # Candle 1 must be bullish (close > open)
    # Candle 2 must be bearish (close < open)
    # Candle 2's body must engulf Candle 1's body (open2 > close1, close2 < open1)
    # Optional: Check body sizes

    is_c1_bullish = candle1["close"] > candle1["open"]
    is_c2_bearish = candle2["close"] < candle2["open"]
    engulfs = candle2["open"] > candle1["close"] and candle2["close"] < candle1["open"]

    # Basic check: C1 bullish, C2 bearish, C2 body engulfs C1 body
    return is_c1_bullish and is_c2_bearish and engulfs


def is_martillo(candle: pd.Series) -> bool:
    """Checks if a candle is a Martillo (Hammer) pattern."""
    # Requires 'open', 'high', 'low', 'close'
    if not all(k in candle for k in ["open", "high", "low", "close"]):
        return False
    cuerpo = abs(candle["close"] - candle["open"])
    sombra_inferior = min(candle["open"], candle["close"]) - candle["low"]
    sombra_superior = candle["high"] - max(candle["open"], candle["close"])
    # Avoid division by zero if body is zero
    if cuerpo < 1e-9:  # Use a small threshold for zero body
        # A very small body might be considered Doji, not Hammer/Shooting Star
        # Or, if it has a long lower shadow and negligible upper, could still be hammer-like
        # Let's stick to the original logic: requires a body for the ratio.
        return False
    # Original logic: lower shadow > 2 * body AND upper shadow < body
    return sombra_inferior > 2 * cuerpo and sombra_superior < cuerpo


def is_estrella_fugaz(candle: pd.Series) -> bool:
    """Checks if a candle is an Estrella Fugaz (Shooting Star) pattern."""
    # Requires 'open', 'high', 'low', 'close'
    if not all(k in candle for k in ["open", "high", "low", "close"]):
        return False
    cuerpo = abs(candle["close"] - candle["open"])
    sombra_superior = candle["high"] - max(candle["close"], candle["open"])
    sombra_inferior = min(candle["close"], candle["open"]) - candle["low"]
    # Avoid division by zero if body is zero
    if cuerpo < 1e-9:  # Use a small threshold for zero body
        return False
    # Original logic: upper shadow > 2 * body AND lower shadow < body
    return sombra_superior > 2 * cuerpo and sombra_inferior < cuerpo


def is_doji(candle: pd.Series) -> bool:
    """Checks if a candle is a Doji pattern."""
    # Requires 'open', 'high', 'low', 'close'
    if not all(k in candle for k in ["open", "high", "low", "close"]):
        return False
    cuerpo = abs(candle["close"] - candle["open"])
    rango_total = candle["high"] - candle["low"]
    # Avoid division by zero if range is zero (flat candle)
    if rango_total < 1e-9:
        return True  # A flat candle is essentially a Doji
    # Original logic: body is less than 10% of the total range
    return cuerpo < (rango_total * 0.1)


# ----------------------------
# Indicator Calculation Function
# ----------------------------


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates necessary indicators and adds them to the DataFrame.
    Assumes 'open', 'high', 'low', 'close', 'volume' columns exist.
    Calculates EMA, RSI, and Engulfing patterns manually.
    Returns a new DataFrame with indicator columns.
    Calculates EMA, RSI, Engulfing patterns, Martillo, Estrella Fugaz, and Doji manually.
    Returns a new DataFrame with indicator columns.
    """
    if df.empty or not all(
        col in df.columns for col in ["open", "high", "low", "close", "volume"]
    ):
        logger.warning(
            "Input DataFrame is empty or missing required OHLCV columns for indicator calculation."
        )
        # Return an empty DataFrame with expected columns to avoid downstream errors
        expected_cols = [
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "EMA12",
            "EMA26",
            "RSI",
            "bullish_engulfing",
            "bearish_engulfing",
            "martillo",
            "estrella_fugaz",
            "doji",
        ]
        return pd.DataFrame(columns=expected_cols)

    df_copy = df.copy()  # Work on a copy

    # Calculate EMAs - need at least 12 or 26 data points respectively
    if len(df_copy) >= 12:
        df_copy["EMA12"] = df_copy["close"].ewm(span=12, adjust=False).mean()
    else:
        df_copy["EMA12"] = pd.NA

    if len(df_copy) >= 26:
        df_copy["EMA26"] = df_copy["close"].ewm(span=26, adjust=False).mean()
    else:
        df_copy["EMA26"] = pd.NA

    # --- RSI Calculation (Using manual helper) ---
    df_copy["RSI"] = calculate_rsi_series(df_copy["close"], 14)

    # --- Manual Candlestick Pattern Calculation ---
    df_copy["bullish_engulfing"] = False
    df_copy["bearish_engulfing"] = False
    df_copy["martillo"] = False
    df_copy["estrella_fugaz"] = False
    df_copy["doji"] = False

    # Iterate through candles to calculate patterns
    # Engulfing requires looking at the previous candle (start from index 1)
    # Martillo, Estrella Fugaz, Doji only need the current candle (can start from index 0)
    for i in range(len(df_copy)):
        current_candle = df_copy.iloc[i]

        # Calculate single-candle patterns
        if is_martillo(current_candle):
            df_copy.loc[df_copy.index[i], "martillo"] = True
        if is_estrella_fugaz(current_candle):
            df_copy.loc[df_copy.index[i], "estrella_fugaz"] = True
        if is_doji(current_candle):
            df_copy.loc[df_copy.index[i], "doji"] = True

        # Calculate two-candle patterns (Engulfing)
        if i > 0:  # Need a previous candle
            prev_candle = df_copy.iloc[i - 1]
            if is_bullish_engulfing_pattern(prev_candle, current_candle):
                df_copy.loc[df_copy.index[i], "bullish_engulfing"] = True
            if is_bearish_engulfing_pattern(prev_candle, current_candle):
                df_copy.loc[df_copy.index[i], "bearish_engulfing"] = True

    # Drop rows where primary indicators (like EMA26 or RSI) are NaN due to insufficient data
    # Keep original columns + calculated indicators
    initial_cols = ["timestamp", "open", "high", "low", "close", "volume"]
    indicator_cols_to_check_na = [
        "EMA26",
        "RSI",
    ]  # Use indicators that require more data for dropping rows
    calculated_indicator_cols = [
        "EMA12",
        "EMA26",
        "RSI",
        "bullish_engulfing",
        "bearish_engulfing",
        "martillo",
        "estrella_fugaz",
        "doji",
    ]
    all_cols = initial_cols + [
        col for col in calculated_indicator_cols if col in df_copy.columns
    ]

    # Drop NA only in the specified indicator columns to keep valid rows where calculations were possible
    # df_copy.dropna(subset=indicator_cols_to_check_na, inplace=True)

    return df_copy[all_cols]  # Return with a consistent column order and cleaned data


# ----------------------------
# Strategy Functions
# Each function takes a DataFrame and returns {'buy': bool, 'sell': bool}
# ----------------------------


def strategy_ema_crossover(df: pd.DataFrame) -> Dict[str, bool]:
    """
    Generates signals based on EMA 12 and EMA 26 crossover.
    Requires 'EMA12' and 'EMA26' columns in the DataFrame with at least 2 rows.
    """
    signals = {"buy": False, "sell": False}

    # Need at least 2 rows and valid EMA values for the last two rows
    if len(df) < 2 or df[["EMA12", "EMA26"]].iloc[-2:].isna().any().any():
        return signals

    last = df.iloc[-1]
    prev = df.iloc[-2]

    # Check for Buy Crossover (EMA12 crosses above EMA26)
    if last["EMA12"] > last["EMA26"] and prev["EMA12"] <= prev["EMA26"]:
        signals["buy"] = True

    # Check for Sell Crossover (EMA12 crosses below EMA26)
    if last["EMA12"] < last["EMA26"] and prev["EMA26"] >= prev["EMA26"]:
        signals["sell"] = True

    return signals


def strategy_rsi(df: pd.DataFrame) -> Dict[str, bool]:
    """
    Generates signals based on RSI overbought/oversold levels.
    Requires 'RSI' column in the DataFrame with at least 1 row.
    """
    signals = {"buy": False, "sell": False}

    if df.empty or df["RSI"].iloc[-1:].isna().any():
        return signals

    last_rsi = df["RSI"].iloc[-1]

    # Check for Buy Signal (RSI below 30 - Oversold)
    if last_rsi < 30:
        signals["buy"] = True

    # Check for Sell Signal (RSI above 70 - Overbought)
    if last_rsi > 70:
        signals["sell"] = True

    return signals


def strategy_q_learning(df: pd.DataFrame, q_table: SimpleQTable) -> Dict[str, bool]:
    """
    Generates signals based on a Q-learning table and current market state.
    Requires 'EMA12', 'EMA26', and 'RSI' columns in the DataFrame with at least 1 row.
    Needs access to the SimpleQTable instance.
    Returns signals dictionary and the state string.
    """
    signals = {"buy": False, "sell": False}

    # Need valid indicator values for the last row
    if df.empty or df[["EMA12", "EMA26", "RSI"]].iloc[-1:].isna().any().any():
        # Return a state that indicates insufficient data, but no signal
        return signals, "state_indicators_missing"

    last = df.iloc[-1]

    # Create state representation based on current indicators
    # Using last candle's data for the state
    ema_cross = "up" if last["EMA12"] > last["EMA26"] else "down"
    rsi_state = "low" if last["RSI"] < 30 else "high" if last["RSI"] > 70 else "mid"
    current_state = f"ema_{ema_cross}_rsi_{rsi_state}"

    # Get action from Q-learning table
    q_action = q_table.get_action(current_state)

    if q_action == "buy":
        signals["buy"] = True
    elif q_action == "sell":
        signals["sell"] = True
    else:
        pass  # No signal

    # Return signals and the state string for later use (e.g., updating Q-table)
    return signals, current_state


def strategy_manual_engulfing_threshold(df: pd.DataFrame) -> Dict[str, bool]:
    """
    Generates signals based on manually calculated Engulfing patterns
    combined with price thresholds relative to the first candle's close
    in the current DataFrame window.
    Requires 'bullish_engulfing' and 'bearish_engulfing' columns calculated.
    Requires at least 2 rows in the DataFrame.
    NOTE: Using df.iloc[0] as reference is an adaptation from a backtesting concept
          and may not be strategically sound for live trading with a sliding data window.
    """
    signals = {"buy": False, "sell": False}

    # Need at least 2 rows for engulfing pattern and reference price comparison
    # Also ensure the pattern columns exist and are boolean type
    if (
        len(df) < 2
        or "bullish_engulfing" not in df.columns
        or "bearish_engulfing" not in df.columns
    ):
        return signals

    precio_referencia = df["close"].iloc[
        0
    ]  # Price of the first candle in the current window
    precio_actual = df["close"].iloc[-1]  # Price of the last candle

    is_bullish_engulfing = df["bullish_engulfing"].iloc[-1]
    is_bearish_engulfing = df["bearish_engulfing"].iloc[-1]

    # ESTRATEGIA ALCISTA adaptada: Bullish Engulfing + Precio actual >= Precio referencia * 1.02
    if is_bullish_engulfing and precio_actual >= precio_referencia * 1.02:
        signals["buy"] = True

    # ESTRATEGIA BAJISTA adaptada: Bearish Engulfing + Precio actual <= Precio referencia * 0.98
    # Note: This is a signal to 'sell' or go 'short'. In a spot bot that only buys/sells owned assets,
    # a 'sell' signal usually means exit a buy position. Adjust logic if this strategy is for shorting.
    # Assuming for now it's a signal to initiate a bearish position/idea if allowed.
    if is_bearish_engulfing and precio_actual <= precio_referencia * 0.98:
        signals["sell"] = True

    return signals


def strategy_basic_candlesticks(df: pd.DataFrame) -> Dict[str, bool]:
    """
    Generates signals based on simple candlestick patterns (Martillo, Estrella Fugaz).
    Requires 'martillo', 'estrella_fugaz' columns in the DataFrame.
    """
    signals = {"buy": False, "sell": False}

    # Need at least 1 row and valid pattern columns for the last row
    if df.empty or not all(col in df.columns for col in ["martillo", "estrella_fugaz"]):
        return signals

    last = df.iloc[-1]

    # Check for Buy Signal (Martillo)
    if last["martillo"]:
        signals["buy"] = True

    # Check for Sell Signal (Estrella Fugaz)
    if last["estrella_fugaz"]:
        signals["sell"] = True

    # Doji currently generates no signal in this basic strategy

    return signals
