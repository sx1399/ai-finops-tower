"""
Static Pricing Module
Rates are stored as Cost per 1 Million Tokens (USD).
"""

PRICING = {
    "gpt-4o": {
        "input": 5.00,
        "output": 15.00
    },
    "gpt-4o-mini": {
        "input": 0.15,
        "output": 0.60
    },
    "deepseek-v4-flash": {
        "input": 0.14,
        "output": 0.28
    },
    "claude-3-opus": {
        "input": 15.00,
        "output": 75.00
    },
    "gemini-3.5-flash": {
        "input": 0.35,
        "output": 1.05
    },
    "unknown": {
        "input": 0.00,
        "output": 0.00
    }
}

def calculate_cost(model_name: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate the cost of a request based on the model and token usage."""
    rates = PRICING.get(model_name, PRICING["unknown"])
    input_cost = (input_tokens / 1_000_000) * rates["input"]
    output_cost = (output_tokens / 1_000_000) * rates["output"]
    return input_cost + output_cost
