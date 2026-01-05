class RiskManager:
    def __init__(self, account_size=10000, risk_per_trade=0.01, max_drawdown=0.20):
        self.account_size = account_size
        self.risk_per_trade = risk_per_trade # 1%
        self.max_drawdown = max_drawdown

    def calculate_position_size(self, entry_price, stop_loss_price, custom_account_size=None, step_size=0.001):
        """
        Calculate amount to buy/sell based on risk amount, respecting exchange step size.
        """
        acc_size = custom_account_size if custom_account_size is not None else self.account_size
        
        if entry_price == stop_loss_price:
            return 0
        
        risk_amount = acc_size * self.risk_per_trade
        price_diff = abs(entry_price - stop_loss_price)
        
        if price_diff == 0:
            return 0
            
        size = risk_amount / price_diff
        
        # Round down to the nearest multiple of step_size
        import math
        precision = len(str(step_size).split('.')[-1]) if '.' in str(step_size) else 0
        rounded_size = math.floor(size / step_size) * step_size
        
        return round(rounded_size, precision)

    def get_stop_targets(self, entry_price, atr, side='long', structure_stop=None,
                         tp_multipliers=None, sl_multiplier=None):
        """Calculate Stop Loss and Take Profit levels using configurable multipliers.

        
        Parameters:
            entry_price (float): Entry price.
            atr (float): Current ATR value.
            side (str): 'long' or 'short'.
            structure_stop (float|None): Optional stop derived from recent swing.
            tp_multipliers (list|None): List of multipliers for TP levels (default [2,3,4]).
            sl_multiplier (float|None): Multiplier for SL based on ATR (default 1.5).
        """
        stops = {}
        # Stop Loss
        if structure_stop is not None:
            sl = structure_stop
        else:
            mult = sl_multiplier if sl_multiplier is not None else 1.5
            sl = entry_price - (mult * atr) if side == 'long' else entry_price + (mult * atr)
        stops['sl'] = sl
        # Take Profits
        tp_mults = tp_multipliers if tp_multipliers is not None else [2, 3, 4]
        for idx, m in enumerate(tp_mults, start=1):
            # ATR Method: Target is a multiple of ATR from entry
            dist = m * atr
            if side == 'long':
                stops[f'tp{idx}'] = entry_price + dist
            else:
                stops[f'tp{idx}'] = entry_price - dist
        return stops

    def check_trailing_stop(self, current_price, current_sl, side, trail_amount, trail_step):
        """
        Check if the Stop Loss should be moved according to Trailing Stop rules.
        """
        new_sl = current_sl
        
        if side == 'long':
            # Price moved up, potential SL moved up
            potential_sl = current_price - trail_amount
            if potential_sl > current_sl + trail_step:
                new_sl = potential_sl
        else: # short
            # Price moved down, potential SL moved down
            potential_sl = current_price + trail_amount
            if potential_sl < current_sl - trail_step:
                new_sl = potential_sl
                
        return new_sl if new_sl != current_sl else None

    def check_breakeven(self, current_price, open_price, current_sl, side, breakeven_trigger):
        """
        Check if the position is profitable enough to move SL to Breakeven (entry price).
        """
        if side == 'long':
            # Is price above (entry + trigger)? And is current SL still below entry?
            if current_price >= open_price + breakeven_trigger and current_sl < open_price:
                return open_price
        else: # short
            # Is price below (entry - trigger)? And is current SL still above entry?
            if current_price <= open_price - breakeven_trigger and current_sl > open_price:
                return open_price
                
        return None
