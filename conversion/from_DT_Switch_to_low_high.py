def from_DT_Switch_to_low_high(x):
    # low - high translated to 0 - 1
    if int(x) == 0:
        return "low"
    else:
        return "high"

