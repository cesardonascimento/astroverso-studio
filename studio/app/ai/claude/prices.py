PRICES_PER_MILLION = {
    "claude-fable-5-2": (8.00, 40.00),
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    input_price, output_price = PRICES_PER_MILLION.get(model, (0.0, 0.0))
    return round(input_tokens / 1e6 * input_price + output_tokens / 1e6 * output_price, 5)
