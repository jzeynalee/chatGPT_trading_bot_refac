
def apply_slippage_and_commission(entry_price, exit_price, slippage_pct=0.001, commission_pct=0.001):
    # Apply slippage
    adjusted_entry = entry_price * (1 + slippage_pct)
    adjusted_exit = exit_price * (1 - slippage_pct)

    # Apply commission (entry and exit)
    total_commission = (adjusted_entry + adjusted_exit) * commission_pct

    # Net return with adjustments
    gross_return = (adjusted_exit - adjusted_entry) / adjusted_entry
    net_return = gross_return - (2 * commission_pct)  # entry + exit

    return {
        "entry_price": adjusted_entry,
        "exit_price": adjusted_exit,
        "net_return": net_return,
        "gross_return": gross_return,
        "commission_paid": total_commission
    }
